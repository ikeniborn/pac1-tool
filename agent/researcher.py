"""Researcher mode orchestrator (FIX-362).

Runs an outer cycle on top of run_loop:

    for cycle in 1..N:
        inject addendum (previous reflections + relevant graph nodes)
        run_loop(researcher_mode=True, max_steps=K)   # no evaluator/stall/timeout
        reflection = reflector.reflect(...)            # one LLM call
        write_fragment("research/<type>", ...)         # accumulate raw trace
        if solved and agent reported done:
            promote_successful_pattern(...)            # pages/<type>.md
            merge graph deltas + save graph
            return
    # no success → degrade touched node confidence, archive negative attempt

Only evaluator.py is kept OFF here; it remains the blocker/skeptic for normal mode.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from bitgn.vm.pcm_connect import PcmRuntimeClientSync

from . import wiki_graph
from .loop import run_loop
from .prephase import run_prephase
from .prompt import build_system_prompt
from .reflector import Reflection, reflect, render_fragment
from .wiki import load_wiki_patterns, write_fragment

_TERMINAL_REFUSALS = {
    "OUTCOME_NONE_CLARIFICATION",
    "OUTCOME_NONE_UNSUPPORTED",
    "OUTCOME_DENIED_SECURITY",
}

_MAX_CYCLES = int(os.environ.get("RESEARCHER_MAX_CYCLES", "10"))
_STEPS_PER_CYCLE = int(os.environ.get("RESEARCHER_STEPS_PER_CYCLE", "15"))
_GRAPH_ENABLED = os.environ.get("WIKI_GRAPH_ENABLED", "1") == "1"
_GRAPH_TOP_K = int(os.environ.get("WIKI_GRAPH_TOP_K", "5"))
_GRAPH_EPSILON = float(os.environ.get("WIKI_GRAPH_CONFIDENCE_EPSILON", "0.05"))
_WIKI_PAGE_MAX_PATTERNS = int(os.environ.get("WIKI_PAGE_MAX_PATTERNS", "10"))

_LOG_DIR = Path(__file__).parent.parent / "logs" / "researcher"


def _render_addendum(
    cycle_reflections: list[Reflection],
    wiki_patterns: str,
    graph_section: str,
) -> str:
    """Compose the researcher-only addendum block injected on top of base prompt."""
    parts: list[str] = []

    def _as_str(x) -> str:
        if isinstance(x, dict):
            return str(x.get("text") or x.get("summary") or x)
        return str(x)

    if cycle_reflections:
        worked: list[str] = []
        failed: list[str] = []
        last = cycle_reflections[-1]
        for r in cycle_reflections:
            worked.extend(_as_str(x) for x in r.what_worked)
            failed.extend(_as_str(x) for x in r.what_failed)
        # dedup preserving order
        seen: set = set()
        worked = [w for w in worked if not (w in seen or seen.add(w))]
        seen.clear()
        failed = [f for f in failed if not (f in seen or seen.add(f))]
        parts.append("## RESEARCH CONTEXT (previous cycles)")
        if last.hypothesis_for_next:
            parts.append(f"Current hypothesis: {last.hypothesis_for_next}")
        if worked:
            parts.append("\nWhat already worked:\n" + "\n".join(f"- {w}" for w in worked[:8]))
        if failed:
            parts.append("\nWhat to avoid (already failed):\n" + "\n".join(f"- {f}" for f in failed[:8]))

    if graph_section:
        parts.append(graph_section)

    if wiki_patterns:
        parts.append(wiki_patterns)

    return "\n\n".join(parts)


def _inject_addendum(base_prompt: str, addendum: str) -> str:
    if not addendum:
        return base_prompt
    return base_prompt + "\n\n" + addendum


def _build_structured_trajectory(step_facts: list, limit: int = 12) -> list[dict]:
    """Convert the tail of step_facts into {tool, path, summary} dicts for wiki rendering."""
    out: list[dict] = []
    for f in (step_facts or [])[-limit:]:
        kind = getattr(f, "kind", "") or "?"
        path = getattr(f, "path", "") or ""
        summary = getattr(f, "summary", "") or ""
        out.append({"tool": kind, "path": path, "summary": summary})
    return out


def _log_cycle(task_id: str, cycle: int, payload: dict) -> None:
    try:
        d = _LOG_DIR / (task_id or "task")
        d.mkdir(parents=True, exist_ok=True)
        (d / f"cycle_{cycle}.jsonl").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[researcher] log write failed: {e}")


def _empty_stats() -> dict:
    return {
        "input_tokens": 0, "output_tokens": 0,
        "cache_creation_tokens": 0, "cache_read_tokens": 0,
        "llm_elapsed_ms": 0, "ollama_eval_count": 0, "ollama_eval_ms": 0,
        "step_count": 0, "llm_call_count": 0,
        "evaluator_calls": 0, "evaluator_rejections": 0, "evaluator_ms": 0,
        "eval_last_call": None, "outcome": "",
        "step_facts": [], "done_ops": [], "stall_hints": [],
    }


def _merge_stats(acc: dict, cur: dict) -> dict:
    for k in ("input_tokens", "output_tokens", "cache_creation_tokens",
              "cache_read_tokens", "llm_elapsed_ms", "ollama_eval_count",
              "ollama_eval_ms", "step_count", "llm_call_count",
              "evaluator_calls", "evaluator_rejections", "evaluator_ms"):
        acc[k] = acc.get(k, 0) + cur.get(k, 0)
    # latest trumps
    acc["outcome"] = cur.get("outcome", acc.get("outcome", ""))
    acc["step_facts"] = cur.get("step_facts", acc.get("step_facts", []))
    acc["done_ops"] = cur.get("done_ops", acc.get("done_ops", []))
    acc["stall_hints"] = cur.get("stall_hints", acc.get("stall_hints", []))
    return acc


def run_researcher(
    harness_url: str,
    task_text: str,
    task_id: str,
    task_type: str,
    model: str,
    cfg: dict,
    max_cycles: int | None = None,
    steps_per_cycle: int | None = None,
) -> dict:
    """Outer researcher cycle. Returns a stats dict compatible with run_loop."""
    max_cycles = max_cycles or _MAX_CYCLES
    steps_per_cycle = steps_per_cycle or _STEPS_PER_CYCLE

    stats = _empty_stats()
    stats["researcher_mode"] = True
    stats["researcher_cycles_used"] = 0
    stats["researcher_solved"] = False
    stats["model_used"] = model
    stats["task_type"] = task_type
    stats["builder_used"] = False
    stats["builder_in_tok"] = 0
    stats["builder_out_tok"] = 0
    stats["builder_addendum"] = ""

    graph = wiki_graph.load_graph() if _GRAPH_ENABLED else wiki_graph.Graph()
    cycle_reflections: list[Reflection] = []
    touched_node_ids: list[str] = []
    last_step_facts: list = []

    for cycle in range(1, max_cycles + 1):
        stats["researcher_cycles_used"] = cycle
        print(f"\n[researcher] ===== cycle {cycle}/{max_cycles} =====")

        # Fresh prephase each cycle — vault state may have shifted via writes.
        vm = PcmRuntimeClientSync(harness_url)
        pre = run_prephase(vm, task_text, "")

        # FIX-366: re-read graph at start of each cycle — picks up updates from
        # sibling tasks (when PARALLEL_TASKS=1 runs serially) and preserves
        # in-memory touched_node_ids/confidence changes by merging over the disk
        # snapshot. In-memory graph takes precedence on conflicts.
        if _GRAPH_ENABLED and cycle > 1:
            disk_graph = wiki_graph.load_graph()
            for nid, node in disk_graph.nodes.items():
                if nid not in graph.nodes:
                    graph.nodes[nid] = node
            _existing_edges = {(e.get("from"), e.get("rel"), e.get("to")) for e in graph.edges}
            for e in disk_graph.edges:
                key = (e.get("from"), e.get("rel"), e.get("to"))
                if all(key) and key not in _existing_edges:
                    graph.edges.append(e)
                    _existing_edges.add(key)

        wiki_patterns = load_wiki_patterns(task_type)
        graph_section = (
            wiki_graph.retrieve_relevant(graph, task_type, task_text, top_k=_GRAPH_TOP_K)
            if _GRAPH_ENABLED else ""
        )
        addendum = _render_addendum(cycle_reflections, wiki_patterns, graph_section)

        base_prompt = build_system_prompt(task_type)
        final_prompt = _inject_addendum(base_prompt, addendum)
        pre.log[0]["content"] = final_prompt
        pre.preserve_prefix[0]["content"] = final_prompt

        cycle_stats = run_loop(
            vm, model, task_text, pre, cfg,
            task_type=task_type,
            evaluator_model="",       # disabled in researcher mode regardless
            evaluator_cfg=None,
            researcher_mode=True,
            max_steps=steps_per_cycle,
        )
        stats = _merge_stats(stats, cycle_stats)

        agent_outcome = cycle_stats.get("outcome", "") or ""
        step_facts = cycle_stats.get("step_facts", []) or []
        done_ops = cycle_stats.get("done_ops", []) or []
        last_step_facts = step_facts

        reflection = reflect(
            task_text=task_text,
            task_type=task_type,
            cycle=cycle,
            step_facts=step_facts,
            done_ops=done_ops,
            agent_outcome=agent_outcome,
            model=model,
            cfg=cfg,
        )
        cycle_reflections.append(reflection)
        # FIX-365: fold reflector LLM tokens into the task totals.
        stats["input_tokens"] = stats.get("input_tokens", 0) + reflection.input_tokens
        stats["output_tokens"] = stats.get("output_tokens", 0) + reflection.output_tokens
        stats["llm_call_count"] = stats.get("llm_call_count", 0) + 1

        try:
            fragment_md = render_fragment(task_id, task_type, cycle, reflection)
            write_fragment(task_id, f"research/{task_type}", fragment_md)
        except Exception as e:
            print(f"[researcher] fragment write failed: {e}")

        _log_cycle(task_id, cycle, {
            "cycle": cycle,
            "agent_outcome": agent_outcome,
            "reflection": {
                "outcome": reflection.outcome,
                "what_worked": reflection.what_worked,
                "what_failed": reflection.what_failed,
                "hypothesis_for_next": reflection.hypothesis_for_next,
                "key_tool_calls": reflection.key_tool_calls,
            },
            "cycle_stats": {k: cycle_stats.get(k) for k in (
                "input_tokens", "output_tokens", "step_count", "llm_call_count"
            )},
        })

        if _GRAPH_ENABLED:
            touched = wiki_graph.merge_updates(graph, reflection.graph_deltas)
            touched_node_ids.extend(touched)

        # FIX-363a: score-gated promotion — defer write to pages until main.py
        # has the benchmark score. Researcher only prepares the payload.
        if reflection.is_solved and agent_outcome == "OUTCOME_OK":
            traj_hash = wiki_graph.hash_trajectory(step_facts)
            trajectory = _build_structured_trajectory(step_facts)
            stats["researcher_solved"] = True
            stats["researcher_pending_promotion"] = {
                "task_type": task_type,
                "task_id": task_id,
                "traj_hash": traj_hash,
                "trajectory": trajectory,
                "insights": list(reflection.what_worked),
                "goal_shape": reflection.goal_shape,
                "final_answer": reflection.final_answer,
                "touched_node_ids": list(touched_node_ids),
            }
            if _GRAPH_ENABLED:
                wiki_graph.save_graph(graph)
            print(f"[researcher] solved on cycle {cycle}; promotion deferred to score-gate")
            return stats

        # FIX-363b: terminal refusal — stop early. Repeating the loop risks the
        # agent "trying harder" and polluting the vault (observed on t08).
        if agent_outcome in _TERMINAL_REFUSALS:
            stats["researcher_early_stop"] = agent_outcome
            # FIX-366: defer refusal promotion to score-gate in main.py — only
            # correct refusals (benchmark score=1) should become wiki guidance.
            trajectory = _build_structured_trajectory(step_facts)
            _reason = reflection.hypothesis_for_next or (
                reflection.what_failed[0] if reflection.what_failed else ""
            )
            stats["researcher_pending_refusal"] = {
                "task_type": task_type,
                "task_id": task_id,
                "outcome": agent_outcome,
                "goal_shape": reflection.goal_shape,
                "refusal_reason": _reason,
                "trajectory": trajectory,
            }
            if _GRAPH_ENABLED:
                wiki_graph.save_graph(graph)
            print(f"[researcher] terminal refusal {agent_outcome} on cycle {cycle} — early stop")
            return stats

    # Exhausted cycles — archive the negative attempt + decay touched nodes.
    traj_hash = wiki_graph.hash_trajectory(last_step_facts)
    print(f"[researcher] exhausted {max_cycles} cycles — no success (traj_hash={traj_hash})")

    neg_note = {
        "task_id": task_id,
        "task_type": task_type,
        "traj_hash": traj_hash,
        "cycles": max_cycles,
        "last_reflection": {
            "outcome": cycle_reflections[-1].outcome if cycle_reflections else "stuck",
            "what_failed": cycle_reflections[-1].what_failed if cycle_reflections else [],
        } if cycle_reflections else {},
    }
    try:
        archive_dir = Path(__file__).parent.parent / "data" / "wiki" / "archive" / "research_negatives"
        archive_dir.mkdir(parents=True, exist_ok=True)
        (archive_dir / f"{task_id}_{traj_hash}.json").write_text(
            json.dumps(neg_note, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as e:
        print(f"[researcher] negative archive failed: {e}")

    if _GRAPH_ENABLED and touched_node_ids:
        archived = wiki_graph.degrade_confidence(graph, touched_node_ids, _GRAPH_EPSILON)
        wiki_graph.save_graph(graph)
        if archived:
            print(f"[researcher] archived {len(archived)} low-confidence nodes")

    return stats
