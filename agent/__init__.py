from __future__ import annotations

import os

from bitgn.vm.pcm_connect import PcmRuntimeClientSync

from .classifier import ModelRouter, TASK_PREJECT
from .loop import run_loop
from .prephase import run_prephase
from .prompt import build_system_prompt
from .prompt_builder import build_dynamic_addendum
from .wiki import load_wiki_base, load_wiki_patterns, format_fragment, write_fragment

_PROMPT_BUILDER_ENABLED = os.getenv("PROMPT_BUILDER_ENABLED", "1") == "1"
_WIKI_ENABLED = os.getenv("WIKI_ENABLED", "1") == "1"
try:
    _PROMPT_BUILDER_MAX_TOKENS = int(os.getenv("PROMPT_BUILDER_MAX_TOKENS", "500"))
except ValueError:
    _PROMPT_BUILDER_MAX_TOKENS = 500


def _inject_addendum(base_prompt: str, addendum: str) -> str:
    """Append task-specific guidance at the end of the system prompt."""
    if not addendum:
        return base_prompt
    return base_prompt + "\n\n## TASK-SPECIFIC GUIDANCE\n" + addendum


def _write_wiki_fragment(vm: "PcmRuntimeClientSync", task_text: str, task_type: str, stats: dict) -> None:
    """Write wiki fragments after task completion. Fail-open."""
    try:
        task_id = getattr(vm, "_task_id", task_text[:20].replace(" ", "_"))
        fragments = format_fragment(
            outcome=stats.get("outcome", ""),
            task_type=task_type,
            task_id=task_id,
            task_text=task_text,
            step_facts=stats.get("step_facts", []),
            done_ops=stats.get("done_ops", []),
            stall_hints=stats.get("stall_hints", []),
            eval_last_call=stats.get("eval_last_call"),
        )
        for content, category in fragments:
            if content and category:
                write_fragment(task_id, category, content)
    except Exception as e:
        print(f"[wiki] fragment write failed: {e}")


def run_agent(router: ModelRouter, harness_url: str, task_text: str) -> dict:
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
        if _WIKI_ENABLED:
            _write_wiki_fragment(vm, task_text, task_type, stats)
        return stats

    # Wiki-Memory stage B: inject base (errors/contacts/accounts) + task-type patterns (FIX-103, FIX-304)
    if _WIKI_ENABLED:
        _wiki_base = load_wiki_base(task_text)      # FIX-304: errors, contacts, accounts for all types
        _wiki_patterns = load_wiki_patterns(task_type)
        _wiki_inject = "\n\n".join(p for p in [_wiki_base, _wiki_patterns] if p)
        if _wiki_inject:
            for i in range(len(pre.preserve_prefix) - 1, -1, -1):
                if pre.preserve_prefix[i].get("role") == "user":
                    pre.preserve_prefix[i]["content"] += f"\n\n{_wiki_inject}"
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
    if _WIKI_ENABLED:
        _write_wiki_fragment(vm, task_text, task_type, stats)
    return stats
