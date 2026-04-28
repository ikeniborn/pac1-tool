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
# FIX-389: graph injection into the agent's system prompt + DSPy addendum.
# Controlled by the same WIKI_GRAPH_ENABLED flag the evaluator already uses.
_GRAPH_READ_ENABLED = os.getenv("WIKI_GRAPH_ENABLED", "1") == "1"
try:
    _GRAPH_TOP_K = int(os.getenv("WIKI_GRAPH_TOP_K", "5"))
except ValueError:
    _GRAPH_TOP_K = 5
try:
    _PROMPT_BUILDER_MAX_TOKENS = int(os.getenv("PROMPT_BUILDER_MAX_TOKENS", "500"))
except ValueError:
    _PROMPT_BUILDER_MAX_TOKENS = 500
# FIX-392: contract negotiation phase
_CONTRACT_ENABLED = os.getenv("CONTRACT_ENABLED", "0") == "1"
try:
    _CONTRACT_MAX_ROUNDS = int(os.getenv("CONTRACT_MAX_ROUNDS", "3"))
except ValueError:
    _CONTRACT_MAX_ROUNDS = 3


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
    _wiki_patterns = ""
    if _WIKI_ENABLED:
        _wiki_patterns = load_wiki_patterns(task_type)
        if _wiki_patterns:
            for i in range(len(pre.preserve_prefix) - 1, -1, -1):
                if pre.preserve_prefix[i].get("role") == "user":
                    pre.preserve_prefix[i]["content"] += f"\n\n{_wiki_patterns}"
                    pre.log[i]["content"] = pre.preserve_prefix[i]["content"]
                    break

    base_prompt = build_system_prompt(task_type)

    # FIX-389: inject KNOWLEDGE GRAPH section + capture node ids the agent saw,
    # so main.py can reinforce/degrade them after end_trial().
    graph_section = ""
    graph_node_ids: list[str] = []
    if _GRAPH_READ_ENABLED:
        try:
            from . import wiki_graph
            _g = wiki_graph.load_graph()
            if _g.nodes:
                graph_section, graph_node_ids = wiki_graph.retrieve_relevant_with_ids(
                    _g, task_type, task_text, top_k=_GRAPH_TOP_K,
                )
        except Exception as _exc:
            print(f"[wiki-graph] retrieval failed ({_exc}) — skipping injection")
    if graph_section:
        base_prompt = base_prompt + "\n\n" + graph_section

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
            graph_context=graph_section,
        )

    final_prompt = _inject_addendum(base_prompt, addendum)
    pre.log[0]["content"] = final_prompt
    pre.preserve_prefix[0]["content"] = final_prompt

    evaluator_model = router.evaluator or model
    evaluator_cfg = router._adapt_config(router.configs.get(evaluator_model, {}), "evaluator")

    contract = None
    contract_in_tok = contract_out_tok = 0
    if _CONTRACT_ENABLED:
        from .contract_phase import negotiate_contract
        try:
            contract, contract_in_tok, contract_out_tok, _rounds = negotiate_contract(
                task_text=task_text,
                task_type=task_type,
                agents_md=getattr(pre, "agents_md_content", "") or "",
                wiki_context=_wiki_patterns,
                graph_context=graph_section,
                model=model,
                cfg=cfg,
                max_rounds=_CONTRACT_MAX_ROUNDS,
            )
        except Exception as _ce:
            print(f"[contract] negotiation failed ({_ce}) — proceeding without contract")
            contract = None

    stats = run_loop(vm, model, task_text, pre, cfg, task_type=task_type,
                     evaluator_model=evaluator_model, evaluator_cfg=evaluator_cfg,
                     contract=contract)
    stats["model_used"] = model
    stats["task_type"] = task_type
    stats["builder_used"] = bool(addendum)
    stats["builder_in_tok"] = builder_in_tok
    stats["builder_out_tok"] = builder_out_tok
    stats["builder_addendum"] = addendum
    stats["graph_injected_node_ids"] = graph_node_ids  # FIX-389
    stats["graph_context"] = graph_section  # for DSPy example collection
    stats["contract_rounds_taken"] = getattr(contract, "rounds_taken", 0) if contract else 0
    stats["contract_is_default"] = getattr(contract, "is_default", True) if contract else True
    stats["contract_in_tok"] = contract_in_tok
    stats["contract_out_tok"] = contract_out_tok
    # FIX-358: wiki fragment write deferred to main.py (score-gated)
    return stats
