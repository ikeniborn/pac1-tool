from __future__ import annotations

import os

from bitgn.vm.pcm_connect import PcmRuntimeClientSync

from .classifier import ModelRouter, TASK_PREJECT, classify_task
from .loop import run_loop
from .prephase import run_prephase
from .prompt import build_system_prompt
from .prompt_builder import build_dynamic_addendum
from .wiki import load_wiki_patterns, format_fragment, write_fragment

_PROMPT_BUILDER_ENABLED = os.getenv("PROMPT_BUILDER_ENABLED", "1") == "1"
_WIKI_ENABLED = os.getenv("WIKI_ENABLED", "1") == "1"
# FIX-362: researcher mode master switch. When enabled, run_agent() bypasses
# the prompt_builder / evaluator / stall / timeout pipeline and delegates to
# agent.researcher.run_researcher, which drives a bounded outer cycle with
# reflection, wiki graph retrieval, and success-gated page promotion.
_RESEARCHER_MODE = os.getenv("RESEARCHER_MODE", "0") == "1"
try:
    _PROMPT_BUILDER_MAX_TOKENS = int(os.getenv("PROMPT_BUILDER_MAX_TOKENS", "500"))
except ValueError:
    _PROMPT_BUILDER_MAX_TOKENS = 500


def _inject_addendum(base_prompt: str, addendum: str) -> str:
    """Append task-specific guidance at the end of the system prompt."""
    if not addendum:
        return base_prompt
    return base_prompt + "\n\n## TASK-SPECIFIC GUIDANCE\n" + addendum


def write_wiki_fragment(
    task_text: str,
    task_type: str,
    stats: dict,
    task_id: str,
    score: float,
) -> None:
    """Write wiki fragments gated by benchmark score (FIX-358). Fail-open.

    Called by main.py AFTER client.end_trial() returns the benchmark score.
    score == 1.0 → success fragment in `fragments/<task_type>/`.
    score <  1.0 → error fragment in `fragments/errors/<task_type>/`.
    """
    outcome = stats.get("outcome", "")
    try:
        task_id = task_id or task_text[:20].replace(" ", "_")
        fragments = format_fragment(
            outcome=outcome,
            task_type=task_type,
            task_id=task_id,
            task_text=task_text,
            step_facts=stats.get("step_facts", []),
            done_ops=stats.get("done_ops", []),
            stall_hints=stats.get("stall_hints", []),
            eval_last_call=stats.get("eval_last_call"),
            score=score,
        )
        for content, category in fragments:
            if content and category:
                write_fragment(task_id, category, content)
    except Exception as e:
        print(f"[wiki] fragment write failed: {e}")


def run_agent(router: ModelRouter, harness_url: str, task_text: str, task_id: str = "") -> dict:
    """Execute a single PAC1 benchmark task and return token usage statistics.

    Flow:
    1. run_prephase() — connects to the vault, fetches tree + AGENTS.MD + docs preload.
    2. router.resolve_after_prephase() — classifies the task type, selects model.
    3. build_system_prompt(task_type) — assembles a task-type specific system prompt.
    4. build_dynamic_addendum() — calls a lightweight LLM to generate task-specific
       guidance (enabled by default; override with PROMPT_BUILDER_ENABLED=0).
    5. run_loop() — executes up to 30 agent steps: LLM → tool dispatch → stall detection.

    Returns a dict with keys: input_tokens, output_tokens, thinking_tokens, model_used,
    task_type.
    """
    # FIX-362: Researcher mode short-circuits the full pipeline. It classifies
    # via the fast regex path (no LLM voting), picks a single model, and runs
    # an outer cycle with reflection + graph retrieval. Evaluator/stall/timeout
    # all stay off. Normal mode is unaffected by this branch.
    if _RESEARCHER_MODE:
        from .researcher import run_researcher
        task_type = classify_task(task_text)
        researcher_model = os.getenv("RESEARCHER_MODEL") or router._select_model(task_type)
        researcher_cfg = router._adapt_config(
            router.configs.get(researcher_model, {}), task_type
        )
        return run_researcher(
            harness_url=harness_url,
            task_text=task_text,
            task_id=task_id or task_text[:20].replace(" ", "_"),
            task_type=task_type,
            model=researcher_model,
            cfg=researcher_cfg,
        )

    vm = PcmRuntimeClientSync(harness_url)

    pre = run_prephase(vm, task_text, "")

    model, cfg, task_type = router.resolve_after_prephase(task_text, pre)

    if task_type == TASK_PREJECT:
        pre.log[0]["content"] = build_system_prompt(task_type)
        pre.preserve_prefix[0]["content"] = pre.log[0]["content"]
        evaluator_model = router.evaluator or model
        evaluator_cfg = router._adapt_config(router.configs.get(evaluator_model, {}), "evaluator")
        stats = run_loop(vm, model, task_text, pre, cfg, task_type=task_type,
                         evaluator_model=evaluator_model, evaluator_cfg=evaluator_cfg)
        stats["model_used"] = model
        stats["task_type"] = task_type
        stats["builder_used"] = False
        stats["builder_in_tok"] = 0
        stats["builder_out_tok"] = 0
        stats["builder_addendum"] = ""
        # FIX-358: wiki fragment write deferred to main.py (score-gated)
        return stats

    # Wiki-Memory stage B (FIX-358): inject ONLY task-type patterns.
    # `load_wiki_base` (contacts.md + accounts.md) removed — entity-catalog
    # injection was redundant: FIX-346/FIX-350 enforce force-read-before-write
    # against the live vault for /accounts/ and /contacts/, so wiki-cached
    # entity data was both unnecessary and a staleness risk.
    if _WIKI_ENABLED:
        _wiki_patterns = load_wiki_patterns(task_type)
        if _wiki_patterns:
            for i in range(len(pre.preserve_prefix) - 1, -1, -1):
                if pre.preserve_prefix[i].get("role") == "user":
                    pre.preserve_prefix[i]["content"] += f"\n\n{_wiki_patterns}"
                    pre.log[i]["content"] = pre.preserve_prefix[i]["content"]
                    break

    base_prompt = build_system_prompt(task_type)

    addendum = ""
    builder_in_tok = builder_out_tok = 0
    if _PROMPT_BUILDER_ENABLED:
        builder_model = router.prompt_builder or router.classifier or model
        builder_cfg = router._adapt_config(
            router.configs.get(builder_model, {}), "classifier"
        )
        addendum, builder_in_tok, builder_out_tok = build_dynamic_addendum(
            task_text=task_text,
            task_type=task_type,
            model=builder_model,
            cfg=builder_cfg,
            max_tokens=_PROMPT_BUILDER_MAX_TOKENS,
        )

    final_prompt = _inject_addendum(base_prompt, addendum)
    pre.log[0]["content"] = final_prompt
    pre.preserve_prefix[0]["content"] = final_prompt

    evaluator_model = router.evaluator or model
    evaluator_cfg = router._adapt_config(router.configs.get(evaluator_model, {}), "evaluator")

    stats = run_loop(vm, model, task_text, pre, cfg, task_type=task_type,
                     evaluator_model=evaluator_model, evaluator_cfg=evaluator_cfg)
    stats["model_used"] = model
    stats["task_type"] = task_type
    stats["builder_used"] = bool(addendum)
    stats["builder_in_tok"] = builder_in_tok
    stats["builder_out_tok"] = builder_out_tok
    stats["builder_addendum"] = addendum
    # FIX-358: wiki fragment write deferred to main.py (score-gated)
    return stats
