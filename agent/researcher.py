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
import re
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
# FIX-369: gate per-cycle debug logs under logs/researcher/<task_id>/cycle_N.jsonl.
_LOG_ENABLED = os.environ.get("RESEARCHER_LOG_ENABLED", "1") == "1"

# FIX-370: pre-flight negatives awareness — surface past failures for this task_type.
_NEGATIVES_ENABLED = os.environ.get("RESEARCHER_NEGATIVES_ENABLED", "1") == "1"
_NEGATIVES_TOP_K = int(os.environ.get("RESEARCHER_NEGATIVES_TOP_K", "3"))

# FIX-371: offline-only short-circuit — skip execution when a Successful pattern
# matches the current task's goal shape. PAC-1 benchmark checks real side-effects,
# so short-circuit will score 0 there — default OFF, opt-in for dev/exploration.
_SHORT_CIRCUIT = os.environ.get("RESEARCHER_SHORT_CIRCUIT", "0") == "1"
_SHORT_CIRCUIT_THRESHOLD = float(os.environ.get("RESEARCHER_SHORT_CIRCUIT_THRESHOLD", "0.4"))

# FIX-372: post-cycle trajectory drift detection — if cycle failed and prefix
# shape differs from known Successful patterns, inject hint into next addendum.
_DRIFT_HINTS = os.environ.get("RESEARCHER_DRIFT_HINTS", "1") == "1"
_DRIFT_PREFIX_LEN = int(os.environ.get("RESEARCHER_DRIFT_PREFIX_LEN", "3"))

# FIX-374: evaluator gate between outer cycles. Proxy for benchmark score
# (unavailable mid-trial). Agent self-OUTCOME_OK or terminal refusal go through
# evaluator first; on reject + cycles_remaining > 0, continue instead of short-
# circuit. Wiki promotion remains gated by real benchmark score in main.py.
_EVAL_GATED = os.environ.get("RESEARCHER_EVAL_GATED", "0") == "1"
_EVAL_SKEPTICISM = os.environ.get("RESEARCHER_EVAL_SKEPTICISM", "high")
_EVAL_EFFICIENCY = os.environ.get("RESEARCHER_EVAL_EFFICIENCY", "mid")
_REFUSAL_MAX_RETRIES = int(os.environ.get("RESEARCHER_REFUSAL_MAX_RETRIES", "3"))

# FIX-375: OUTCOME_FLIP_HINT + diversification detector. When the agent keeps
# proposing the same outcome (OK rejected repeatedly with similar reason, OR
# hypotheses monotonic), inject a hint suggesting the opposite outcome. Also
# gives one last-chance cycle after refusal cap, with the flip hint, to give
# the agent a chance to find an answerable interpretation before final accept.
_FLIP_HINT_ENABLED = os.environ.get("RESEARCHER_FLIP_HINT_ENABLED", "1") == "1"
_FLIP_REASON_SIM_THRESHOLD = float(
    os.environ.get("RESEARCHER_FLIP_REASON_SIMILARITY_THRESHOLD", "0.5")
)
_FLIP_HYP_MONOTONIC_K = int(os.environ.get("RESEARCHER_FLIP_HYP_MONOTONIC_K", "2"))
_FLIP_HYP_SIM_THRESHOLD = float(
    os.environ.get("RESEARCHER_FLIP_HYP_SIMILARITY_THRESHOLD", "0.6")
)
_REFUSAL_LAST_CHANCE = os.environ.get("RESEARCHER_REFUSAL_LAST_CHANCE", "1") == "1"

_LOG_DIR = Path(__file__).parent.parent / "logs" / "researcher"
_NEGATIVES_DIR = Path(__file__).parent.parent / "data" / "wiki" / "archive" / "research_negatives"
_PAGES_DIR = Path(__file__).parent.parent / "data" / "wiki" / "pages"
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    union = ta | tb
    return len(ta & tb) / len(union) if union else 0.0


def _is_monotonic_hypothesis(history: list[str], k: int, threshold: float) -> bool:
    """True if the last k+1 entries are pairwise similar above threshold.

    Used to detect reflector getting stuck in one interpretation.
    """
    if len(history) < k + 1:
        return False
    recent = history[-(k + 1):]
    for i in range(len(recent)):
        for j in range(i + 1, len(recent)):
            if _jaccard(recent[i], recent[j]) < threshold:
                return False
    return True


# ---------------------------------------------------------------------------
# FIX-370: research_negatives/ — "avoid these patterns" warnings
# ---------------------------------------------------------------------------

def _load_negative_warnings(task_type: str, task_text: str, top_k: int) -> str:
    """Render top-K most-relevant past-failure blobs for this task_type.

    Scoring: token overlap between task_text and concatenated what_failed entries.
    Fail-open → '' on any IO or parse error.
    """
    if not _NEGATIVES_ENABLED or top_k <= 0:
        return ""
    if not _NEGATIVES_DIR.exists():
        return ""
    task_tokens = _tokenize(task_text)
    candidates: list[tuple[int, str, list[str]]] = []
    for f in _NEGATIVES_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("task_type") != task_type:
            continue
        last = data.get("last_reflection") or {}
        failed = [str(x) for x in (last.get("what_failed") or []) if x]
        if not failed:
            continue
        fail_tokens = _tokenize(" ".join(failed))
        overlap = len(task_tokens & fail_tokens)
        candidates.append((overlap, str(data.get("task_id", "?")), failed))
    if not candidates:
        return ""
    candidates.sort(key=lambda x: -x[0])
    top = candidates[:top_k]
    lines = ["## PAST FAILURES FOR THIS TYPE (avoid repeating)"]
    for _, tid, failed in top:
        lines.append(f"- from {tid}:")
        for fail in failed[:3]:
            lines.append(f"  - {fail}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# FIX-371/372: parse pages/<type>.md — extract Successful patterns
# ---------------------------------------------------------------------------

_MARKER_RE = re.compile(r"<!--\s*researcher:\s*([^\s:]+):([0-9a-f]+)\s*-->")
_GOAL_RE = re.compile(r"\*\*Goal shape:\*\*\s*(.+)")
_ANSWER_RE = re.compile(r"\*\*Final answer:\*\*\s*(.+)")
_TRAJ_STEP_RE = re.compile(r"^\s*\d+\.\s+([a-zA-Z_][\w]*)\s*(?:\(([^)]*)\))?")
# Canonical PCM tool names — guard against LLM-prose ("1. Treat every file...")
# leaking non-tool words into trajectory_tools.
_VALID_TOOLS = {
    "tree", "find", "search", "list", "read",
    "write", "delete", "mkdir", "move", "report_completion",
}

# Task type → wiki page name. Duplicates wiki._TYPE_TO_PAGE, kept local to avoid
# importing private symbol. Falls back to task_type unchanged when not mapped.
_PAGE_NAME_MAP = {
    "think": "think", "distill": "distill", "email": "email",
    "lookup": "lookup", "inbox": "inbox", "queue": "queue",
    "capture": "capture", "crm": "crm", "temporal": "temporal",
    "preject": "preject", "default": "default",
}


def _parse_page_patterns(task_type: str) -> list[dict]:
    """Parse pages/<task_type>.md Successful patterns. Returns structured dicts."""
    page_name = _PAGE_NAME_MAP.get(task_type, task_type)
    page_path = _PAGES_DIR / f"{page_name}.md"
    if not page_path.exists():
        return []
    try:
        content = page_path.read_text(encoding="utf-8")
    except Exception:
        return []
    sections = re.split(r"(?m)^## Successful pattern: ", content)
    out: list[dict] = []
    for sec in sections[1:]:  # [0] is preamble
        marker = _MARKER_RE.search(sec)
        if not marker:
            continue
        task_id, traj_hash = marker.group(1), marker.group(2)
        goal_m = _GOAL_RE.search(sec)
        goal = goal_m.group(1).strip() if goal_m else ""
        answer_m = _ANSWER_RE.search(sec)
        answer = answer_m.group(1).strip() if answer_m else ""
        traj_tools: list[str] = []
        traj_block_match = re.search(
            r"\*\*Trajectory:\*\*\s*\n((?:.+\n?)*?)(?=\n\*\*|$)", sec
        )
        if traj_block_match:
            for line in traj_block_match.group(1).splitlines():
                m = _TRAJ_STEP_RE.match(line)
                if m and m.group(1).lower() in _VALID_TOOLS:
                    traj_tools.append(m.group(1).lower())
        out.append({
            "task_id": task_id,
            "traj_hash": traj_hash,
            "goal_shape": goal,
            "final_answer": answer,
            "trajectory_tools": traj_tools,
        })
    return out


def _find_matching_pattern(
    patterns: list[dict], task_text: str, threshold: float,
) -> tuple[dict, float] | None:
    """Best-overlap match between task_text and pattern.goal_shape."""
    if not patterns:
        return None
    task_tokens = _tokenize(task_text)
    if not task_tokens:
        return None
    best: tuple[dict, float] | None = None
    for p in patterns:
        goal_tokens = _tokenize(p.get("goal_shape", ""))
        if not goal_tokens:
            continue
        # Jaccard similarity — symmetric, bounded [0,1].
        inter = len(task_tokens & goal_tokens)
        union = len(task_tokens | goal_tokens)
        score = inter / union if union else 0.0
        if score >= threshold and (best is None or score > best[1]):
            best = (p, score)
    return best


def _detect_drift(
    step_facts: list, patterns: list[dict], prefix_len: int,
) -> str:
    """If current step-fact prefix doesn't match any known pattern's prefix, emit hint.

    Compares sequences of tool-kind names only (no paths/args) — stable across entity
    redaction. Empty step_facts or empty patterns → '' (nothing to say).
    """
    if not step_facts or not patterns or prefix_len <= 0:
        return ""
    current_prefix = [
        (getattr(f, "kind", "") or "?").lower() for f in step_facts[:prefix_len]
    ]
    if not any(current_prefix):
        return ""
    for p in patterns:
        pattern_prefix = [t.lower() for t in (p.get("trajectory_tools") or [])[:prefix_len]]
        if pattern_prefix and pattern_prefix == current_prefix:
            return ""  # a pattern matches — no drift
    # No pattern prefix matched — closest by overlap count becomes the reference.
    best_p, best_overlap = None, -1
    for p in patterns:
        pattern_prefix = [t.lower() for t in (p.get("trajectory_tools") or [])[:prefix_len]]
        if not pattern_prefix:
            continue
        overlap = sum(1 for a, b in zip(current_prefix, pattern_prefix) if a == b)
        if overlap > best_overlap:
            best_overlap, best_p = overlap, p
    if not best_p:
        return ""
    ref_prefix = " → ".join((best_p.get("trajectory_tools") or [])[:prefix_len]) or "?"
    cur_prefix = " → ".join(current_prefix) or "?"
    return (
        f"DRIFT: your trajectory starts with `{cur_prefix}`, "
        f"but the verified pattern (task {best_p.get('task_id')}) starts with "
        f"`{ref_prefix}`. Consider realigning the opening tool sequence."
    )


def _render_addendum(
    cycle_reflections: list[Reflection],
    wiki_patterns: str,
    graph_section: str,
    negatives_section: str = "",
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

    # FIX-370: negatives last — rendered as an explicit AVOID block after
    # patterns so the agent reads "here's what works" before "here's what failed".
    if negatives_section:
        parts.append(negatives_section)

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


def _reset_task_log_dir(task_id: str) -> None:
    """Wipe logs/researcher/<task_id>/ before a new run.

    Prevents stale cycle_N.jsonl files from a previous run (which had more
    cycles) masquerading as part of the current run. Fail-open.
    """
    if not _LOG_ENABLED:
        return
    try:
        import shutil
        d = _LOG_DIR / (task_id or "task")
        if d.exists():
            shutil.rmtree(d)
    except Exception as e:
        print(f"[researcher] log reset failed: {e}")


def _log_cycle(task_id: str, cycle: int, payload: dict) -> None:
    if not _LOG_ENABLED:
        return
    try:
        d = _LOG_DIR / (task_id or "task")
        d.mkdir(parents=True, exist_ok=True)
        (d / f"cycle_{cycle}.jsonl").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[researcher] log write failed: {e}")


# ---------------------------------------------------------------------------
# FIX-374: evaluator gate — proxy-score between outer cycles
# ---------------------------------------------------------------------------


def _evaluator_gate(
    *,
    task_text: str,
    task_type: str,
    report,
    done_ops: list[str],
    step_facts: list,
    model: str,
    cfg: dict,
    stats: dict,
) -> tuple[bool, list[str], str]:
    """Call evaluator as a benchmark-score proxy. Fail-open on any error.

    Returns: (approved, issues, correction_hint).
    Side-effect: on successful call, stores DSPy sample in stats["eval_last_call"]
    and bumps stats["evaluator_calls"] so main.py can feed it to record_eval_example
    after end_trial (benchmark score becomes the ground truth label).
    """
    if report is None:
        return (True, [], "")
    try:
        from .evaluator import evaluate_completion  # lazy — avoid DSPy import when disabled
        from .log_compaction import build_digest
    except Exception as exc:
        print(f"[researcher] evaluator gate import failed ({exc}) — fail-open")
        return (True, [], "")

    digest = ""
    try:
        if _EVAL_EFFICIENCY == "high" and step_facts:
            digest = build_digest(step_facts)
    except Exception:
        digest = ""

    try:
        verdict = evaluate_completion(
            task_text=task_text,
            task_type=task_type,
            report=report,
            done_ops=done_ops,
            digest_str=digest,
            model=model,
            cfg=cfg,
            skepticism=_EVAL_SKEPTICISM,
            efficiency=_EVAL_EFFICIENCY,
        )
    except Exception as exc:
        print(f"[researcher] evaluator gate failed ({exc}) — fail-open")
        return (True, [], "")

    # DSPy sample: mirror the shape loop.py:2131 uses so main.py's existing
    # record_eval_example path picks it up unchanged. Last gate call wins —
    # it's the one tied to the cycle that produced the final benchmark score.
    _steps_list = getattr(report, "completed_steps_laconic", []) or []
    _steps_str = "\n".join(f"- {s}" for s in _steps_list)
    stats["eval_last_call"] = {
        "task_text": task_text,
        "task_type": task_type,
        "proposed_outcome": getattr(report, "outcome", "") or "",
        "agent_message": getattr(report, "message", "") or "",
        "done_ops": "\n".join(f"- {op}" for op in done_ops) or "(none)",
        "completed_steps": _steps_str or "(none)",
        "skepticism_level": _EVAL_SKEPTICISM,
    }
    stats["evaluator_calls"] = stats.get("evaluator_calls", 0) + 1

    return (
        bool(getattr(verdict, "approved", True)),
        list(getattr(verdict, "issues", []) or []),
        str(getattr(verdict, "correction_hint", "") or ""),
    )


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
    # FIX-373: reflector token usage tracked separately from agent totals.
    # stats["input_tokens"]/["output_tokens"] keep aggregating everything
    # (inner-loop agent + reflector) — these two isolate the reflector overhead.
    stats["researcher_in_tok"] = 0
    stats["researcher_out_tok"] = 0
    stats["model_used"] = model
    stats["task_type"] = task_type
    stats["builder_used"] = False
    stats["builder_in_tok"] = 0
    stats["builder_out_tok"] = 0
    stats["builder_addendum"] = ""

    # Wipe stale cycle files from a prior run of this task — otherwise a
    # shorter new run leaves cycle_N.jsonl files from the previous, longer run.
    _reset_task_log_dir(task_id)

    graph = wiki_graph.load_graph() if _GRAPH_ENABLED else wiki_graph.Graph()
    cycle_reflections: list[Reflection] = []
    touched_node_ids: list[str] = []
    last_step_facts: list = []

    # FIX-371: offline-only short-circuit. Before any inner-loop execution,
    # check if pages/<type>.md holds a Successful pattern whose goal_shape
    # closely overlaps the task. If so, skip execution entirely and return
    # the cached final_answer. WARNING: no real vault mutations happen, so
    # PAC-1 benchmark will score 0. Intended for dev/offline exploration only.
    page_patterns = _parse_page_patterns(task_type)
    if _SHORT_CIRCUIT and page_patterns:
        match = _find_matching_pattern(page_patterns, task_text, _SHORT_CIRCUIT_THRESHOLD)
        if match is not None:
            matched_pattern, score = match
            print(
                f"[researcher] SHORT-CIRCUIT: matched pattern {matched_pattern['task_id']} "
                f"(score={score:.2f} ≥ {_SHORT_CIRCUIT_THRESHOLD}). Skipping execution. "
                f"PAC-1 benchmark WILL score 0 — set RESEARCHER_SHORT_CIRCUIT=0 for real runs."
            )
            stats["researcher_short_circuited"] = True
            stats["researcher_matched_pattern"] = matched_pattern["task_id"]
            stats["researcher_short_circuit_score"] = score
            stats["outcome"] = "OUTCOME_OK"
            stats["researcher_cached_answer"] = matched_pattern.get("final_answer", "")
            return stats

    # FIX-375: state for diversification detector + flip-hint logic.
    _hypothesis_history: list[str] = []
    _eval_reject_reasons: list[str] = []

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
        # FIX-370: pre-flight negatives awareness — surface past failures.
        negatives_section = _load_negative_warnings(
            task_type, task_text, _NEGATIVES_TOP_K,
        )
        addendum = _render_addendum(
            cycle_reflections, wiki_patterns, graph_section, negatives_section,
        )

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
        # FIX-375: capture RAW reflector hypothesis before any hint mutations
        # (drift/refusal_retry/eval_rejected/flip). Detector measures reflector
        # monotonicity, not our own injected suffixes.
        _hypothesis_history.append(reflection.hypothesis_for_next or "")
        # FIX-365: fold reflector LLM tokens into the task totals.
        stats["input_tokens"] = stats.get("input_tokens", 0) + reflection.input_tokens
        stats["output_tokens"] = stats.get("output_tokens", 0) + reflection.output_tokens
        stats["llm_call_count"] = stats.get("llm_call_count", 0) + 1
        # FIX-373: isolate reflector tokens so the summary can show researcher
        # overhead alongside the task total.
        stats["researcher_in_tok"] = stats.get("researcher_in_tok", 0) + reflection.input_tokens
        stats["researcher_out_tok"] = stats.get("researcher_out_tok", 0) + reflection.output_tokens

        # FIX-372: post-cycle drift detection. If reflector says not solved and
        # the agent's trajectory prefix differs from all known Successful patterns,
        # append a DRIFT hint onto reflection.hypothesis_for_next. The addendum
        # builder reads `last.hypothesis_for_next` verbatim, so the hint reaches
        # the next cycle's system prompt without any extra plumbing.
        if _DRIFT_HINTS and not reflection.is_solved and page_patterns and step_facts:
            drift = _detect_drift(step_facts, page_patterns, _DRIFT_PREFIX_LEN)
            if drift:
                existing = (reflection.hypothesis_for_next or "").strip()
                reflection.hypothesis_for_next = (
                    f"{existing} | {drift}" if existing else drift
                )
                print(f"[researcher] drift hint queued for cycle {cycle + 1}")

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

        # FIX-374: terminal refusals in researcher mode retry up to
        # RESEARCHER_REFUSAL_MAX_RETRIES times (default 3). Beyond that, the
        # agent has clearly converged on refusal — wasting remaining cycles is
        # pointless. Evaluator is not consulted: observed false-approve on t11.
        if agent_outcome in _TERMINAL_REFUSALS and cycle < max_cycles:
            _retries = stats.get("researcher_refusal_retries", 0)
            if _retries < _REFUSAL_MAX_RETRIES:
                stats["researcher_refusal_retries"] = _retries + 1
                _reason = (
                    (reflection.what_failed[0] if reflection.what_failed else "")
                    or "refusal retry — search harder for actionable path"
                )
                _existing = (reflection.hypothesis_for_next or "").strip()
                reflection.hypothesis_for_next = (
                    f"{_existing} | REFUSAL_RETRY: {_reason}" if _existing
                    else f"REFUSAL_RETRY: {_reason}"
                )
                print(
                    f"[researcher] terminal refusal {agent_outcome} on cycle {cycle} "
                    f"— retrying ({_retries + 1}/{_REFUSAL_MAX_RETRIES})"
                )
                continue
            # FIX-375: refusal last-chance — one extra cycle with flip hint
            # before final accept. Gives the agent a chance to find an
            # answerable interpretation after exhausting retry budget.
            if (
                _REFUSAL_LAST_CHANCE
                and _FLIP_HINT_ENABLED
                and not stats.get("researcher_refusal_last_chance_used")
            ):
                stats["researcher_refusal_last_chance_used"] = True
                stats["researcher_flip_hints_injected"] = (
                    stats.get("researcher_flip_hints_injected", 0) + 1
                )
                _last_reason = (
                    (reflection.what_failed[0] if reflection.what_failed else "")
                    or "refused with same reasoning"
                )[:200]
                _flip = (
                    f"OUTCOME_FLIP_HINT: You've refused {_REFUSAL_MAX_RETRIES} times "
                    f"citing '{_last_reason}'. If there's ANY plausible interpretation "
                    f"where the task IS answerable (different tool semantics, different "
                    f"target folder, different definition of the verb), attempt it now. "
                    f"This is your last cycle before final accept."
                )
                _existing = (reflection.hypothesis_for_next or "").strip()
                reflection.hypothesis_for_next = (
                    f"{_existing} | {_flip}" if _existing else _flip
                )
                print(
                    f"[researcher] terminal refusal {agent_outcome} on cycle {cycle} "
                    f"— last-chance cycle with OUTCOME_FLIP_HINT"
                )
                continue
            print(
                f"[researcher] terminal refusal {agent_outcome} on cycle {cycle} "
                f"— retry limit {_REFUSAL_MAX_RETRIES} reached, accepting refusal"
            )

        # FIX-374: evaluator gate on self-OUTCOME_OK — decide whether to trust
        # the cycle outcome before short-circuiting. On reject + cycles remaining,
        # inject verdict as a hint for the next cycle and continue.
        _gate_relevant = (
            _EVAL_GATED
            and cycle < max_cycles
            and reflection.is_solved
            and agent_outcome == "OUTCOME_OK"
        )
        if _gate_relevant:
            _report = cycle_stats.get("report")
            _approved, _issues, _hint = _evaluator_gate(
                task_text=task_text,
                task_type=task_type,
                report=_report,
                done_ops=done_ops,
                step_facts=step_facts,
                model=model,
                cfg=cfg,
                stats=stats,
            )
            stats["researcher_eval_calls"] = stats.get("researcher_eval_calls", 0) + 1
            if not _approved:
                stats["researcher_eval_rejections"] = stats.get("researcher_eval_rejections", 0) + 1
                _reason = "; ".join(_issues[:3]) or _hint or "evaluator rejected outcome"
                _eval_reject_reasons.append(_reason)
                # FIX-375: OK-flip hint — if evaluator rejects OK with similar
                # reason ≥2 times in a row, OR reflector hypotheses are
                # monotonic, suggest OUTCOME flip as escape from local minimum.
                _should_flip = False
                if _FLIP_HINT_ENABLED:
                    if len(_eval_reject_reasons) >= 2 and _jaccard(
                        _eval_reject_reasons[-1], _eval_reject_reasons[-2]
                    ) >= _FLIP_REASON_SIM_THRESHOLD:
                        _should_flip = True
                    elif _is_monotonic_hypothesis(
                        _hypothesis_history, _FLIP_HYP_MONOTONIC_K, _FLIP_HYP_SIM_THRESHOLD
                    ):
                        _should_flip = True
                _flip_suffix = ""
                if _should_flip:
                    _flip_suffix = (
                        " | OUTCOME_FLIP_HINT: You've proposed OUTCOME_OK multiple times "
                        "and evaluator rejected each with similar concerns. The task may "
                        "be unanswerable as stated — consider OUTCOME_NONE_CLARIFICATION "
                        "or OUTCOME_NONE_UNSUPPORTED as a valid answer."
                    )
                    stats["researcher_flip_hints_injected"] = (
                        stats.get("researcher_flip_hints_injected", 0) + 1
                    )
                    print(f"[researcher] OK-flip hint injected on cycle {cycle}")
                _existing = (reflection.hypothesis_for_next or "").strip()
                reflection.hypothesis_for_next = (
                    f"{_existing} | EVAL_REJECTED: {_reason}{_flip_suffix}" if _existing
                    else f"EVAL_REJECTED: {_reason}{_flip_suffix}"
                )
                print(
                    f"[researcher] evaluator rejected cycle {cycle} "
                    f"(OUTCOME_OK): {_reason} — continuing"
                )
                continue
            else:
                print(
                    f"[researcher] evaluator approved cycle {cycle} "
                    f"(OUTCOME_OK) — proceeding to short-circuit"
                )

        # FIX-363a: score-gated promotion — defer write to pages until main.py
        # has the benchmark score. Researcher only prepares the payload.
        if reflection.is_solved and agent_outcome == "OUTCOME_OK":
            # FIX-374: expose the reflector-built addendum used in the winning
            # cycle as a builder example. main.py:300 records it with the real
            # benchmark score; optimize_prompts filters by score >= 0.8.
            stats["builder_used"] = True
            stats["builder_addendum"] = addendum
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
