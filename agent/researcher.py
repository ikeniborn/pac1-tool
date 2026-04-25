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

# FIX-376f: dynamic refusal budget — instead of a fixed cap, scale retries
# with cycles_remaining so refusals can never pre-empt the full max_cycles
# allotment. Last-chance injection additionally pulls top-K bullets from
# _load_negative_warnings to ground the alternative-interpretation suggestion.
_REFUSAL_DYNAMIC = os.environ.get("RESEARCHER_REFUSAL_DYNAMIC", "0") == "1"
_REFUSAL_MIN_CYCLES_LEFT = int(os.environ.get("RESEARCHER_REFUSAL_MIN_CYCLES_LEFT", "2"))

# FIX-376g: graph quarantine — drop low-confidence nodes and nodes that were
# poisoned in this trial from retrieve_relevant before they leak back into
# the next-cycle addendum and propagate the antipattern cascade.
_GRAPH_QUARANTINE = os.environ.get("RESEARCHER_GRAPH_QUARANTINE", "0") == "1"
_GRAPH_MIN_CONF = float(os.environ.get("RESEARCHER_GRAPH_MIN_CONF", "0.35"))

# FIX-376h: full-trace drift via LCS — extends the prefix-only check from FIX-372.
# Useful when the agent matches the opening of a successful pattern but diverges
# at step 10+. Prefix-check stays as a fast-path shortcut.
_DRIFT_FULL_TRACE = os.environ.get("RESEARCHER_DRIFT_FULL_TRACE", "0") == "1"
_DRIFT_LCS_MIN = float(os.environ.get("RESEARCHER_DRIFT_LCS_MIN", "0.4"))


def _lcs_ratio(a: list[str], b: list[str]) -> tuple[float, int]:
    """Compute LCS-length ratio and the index of first divergence.

    Returns (ratio, divergence_index). Ratio = LCS / max(len(a), len(b)),
    bounded [0, 1]. Divergence_index = first i where a[i] != b[i] (or shorter
    list end). Both empty → (1.0, 0). O(n·m) DP — n,m ≤ 30 so it's cheap.
    """
    if not a or not b:
        return (0.0, 0)
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n):
        for j in range(m):
            if a[i] == b[j]:
                dp[i + 1][j + 1] = dp[i][j] + 1
            else:
                dp[i + 1][j + 1] = max(dp[i][j + 1], dp[i + 1][j])
    lcs = dp[n][m]
    ratio = lcs / max(n, m)
    div_idx = 0
    while div_idx < n and div_idx < m and a[div_idx] == b[div_idx]:
        div_idx += 1
    return (ratio, div_idx)


def _detect_drift_lcs(
    step_facts: list, patterns: list[dict], lcs_min: float,
) -> str:
    """Full-trajectory drift hint via LCS. Returns '' when at least one pattern
    keeps an LCS-ratio ≥ lcs_min against the current trajectory.
    """
    if not step_facts or not patterns:
        return ""
    current = [(getattr(f, "kind", "") or "?").lower() for f in step_facts]
    if not any(current):
        return ""
    best_ratio = -1.0
    best_pattern = None
    best_div = 0
    for p in patterns:
        ref = [t.lower() for t in (p.get("trajectory_tools") or []) if t]
        if not ref:
            continue
        ratio, div_idx = _lcs_ratio(current, ref)
        if ratio > best_ratio:
            best_ratio = ratio
            best_pattern = p
            best_div = div_idx
    if best_pattern is None or best_ratio >= lcs_min:
        return ""
    ref_tools = " → ".join((best_pattern.get("trajectory_tools") or [])[:8]) or "?"
    return (
        f"DRIFT(full-trace, lcs={best_ratio:.2f}<{lcs_min:.2f}): your trajectory "
        f"diverges from verified pattern (task {best_pattern.get('task_id')}) at "
        f"step {best_div + 1}; reference opens with `{ref_tools}`."
    )

# FIX-375b/C: hard guard against agent looping on consecutive OUTCOME_OK with
# same final_answer. After N consecutive OK with identical final answer (after
# trimming/lowercasing), short-circuit with pending_refusal. This is the last
# resort when evaluator gate + flip-hint + reflector outcome-history all fail
# to break the loop (observed t43: 15× OUTCOME_OK same answer, all rejected).
_OK_LOOP_LIMIT = int(os.environ.get("RESEARCHER_OK_LOOP_LIMIT", "5"))

# FIX-376a: evaluator fail-closed — on LLM/parse error inside the gate, return
# inconclusive instead of silent approve. Researcher continues to next cycle
# without injecting a misleading EVAL_REJECTED hint and without short-circuit.
_EVAL_FAIL_CLOSED = os.environ.get("RESEARCHER_EVAL_FAIL_CLOSED", "0") == "1"

# FIX-376d: reflector diversification. Pass last N raw hypotheses to reflector
# so it cannot lazily repeat the same idea, and tighten the monotonicity
# detector (mean pairwise Jaccard, lower threshold). Default OFF.
_REFLECTOR_DIVERSIFY = os.environ.get("RESEARCHER_REFLECTOR_DIVERSIFY", "0") == "1"
_REFLECTOR_PRIOR_WINDOW = int(os.environ.get("RESEARCHER_REFLECTOR_PRIOR_WINDOW", "3"))
_REFLECTOR_DIVERSIFY_SIM_THRESHOLD = 0.45

# FIX-376b: hint forcing — when consecutive cycles inject the same hint type
# (FLIP/REJECTED/DRIFT/REFUSAL_RETRY) and the agent ignores it, escalate from
# passive system-addendum to a mandatory user-message reminder.
_HINT_FORCING = os.environ.get("RESEARCHER_HINT_FORCING", "0") == "1"
_HINT_MAX_INJECTIONS = int(os.environ.get("RESEARCHER_HINT_MAX_INJECTIONS", "2"))
_HINT_TYPE_PATTERNS = (
    ("OUTCOME_FLIP_HINT", "FLIP"),
    ("EVAL_REJECTED", "REJECTED"),
    ("DRIFT", "DRIFT"),
    ("REFUSAL_RETRY", "REFUSAL_RETRY"),
    ("MIDCYCLE_ABORTED", "MIDCYCLE"),
)


# FIX-376e: adaptive per-cycle step budget + global step cap (escape ladder).
# Cycles 1-2 keep RESEARCHER_STEPS_PER_CYCLE; from cycle 3 onward, if the prior
# outcome was stuck and the agent burned ≥80% of its budget, expand by 1.5×
# (capped at RESEARCHER_STEPS_MAX). RESEARCHER_TOTAL_STEP_BUDGET caps the sum
# across all cycles — when hit, the outer loop accepts best-known and exits.
_STEPS_ADAPTIVE = os.environ.get("RESEARCHER_STEPS_ADAPTIVE", "0") == "1"
_STEPS_MAX = int(os.environ.get("RESEARCHER_STEPS_MAX", "30"))
_TOTAL_STEP_BUDGET = int(os.environ.get("RESEARCHER_TOTAL_STEP_BUDGET", "180"))
# RESEARCHER_SOFT_STALL is read inside agent/loop.py at runtime — keeping a
# reference here for documentation completeness only.

# FIX-376c: mid-cycle breakout — checkpoint inner-loop every N steps and abort
# early when the agent is clearly looping on the same (tool, path) or has
# stopped producing new step_fact kinds. Frees step budget for the next cycle.
_MIDCYCLE_BREAKOUT = os.environ.get("RESEARCHER_MIDCYCLE_BREAKOUT", "0") == "1"
_MIDCYCLE_CHECK_EVERY = int(os.environ.get("RESEARCHER_MIDCYCLE_CHECK_EVERY", "5"))
_MIDCYCLE_REPEAT_THRESHOLD = int(os.environ.get("RESEARCHER_MIDCYCLE_REPEAT_THRESHOLD", "3"))


def _midcycle_breakout(step_facts: list, _cycle: int) -> str:
    """Decide whether to abort the inner cycle early.

    Returns 'continue' (default), 'abort_cycle' (caller breaks the loop), or
    'force_report' (reserved — currently treated identically to abort_cycle).
    Triggers:
      - same (tool, path) ≥ _MIDCYCLE_REPEAT_THRESHOLD times in the recent window
      - no new step_fact.kind seen in the last _MIDCYCLE_CHECK_EVERY steps
    """
    if not step_facts:
        return "continue"
    window_size = max(_MIDCYCLE_CHECK_EVERY, _MIDCYCLE_REPEAT_THRESHOLD)
    window = step_facts[-window_size:]
    # Trigger 1: tight (tool, path) repeat
    pair_counts: dict[tuple[str, str], int] = {}
    for f in window:
        key = (str(getattr(f, "kind", "")), str(getattr(f, "path", "")))
        pair_counts[key] = pair_counts.get(key, 0) + 1
        if pair_counts[key] >= _MIDCYCLE_REPEAT_THRESHOLD:
            return "abort_cycle"
    # Trigger 2: no new kinds in the trailing slice
    if len(step_facts) >= _MIDCYCLE_CHECK_EVERY * 2:
        recent_kinds = {str(getattr(f, "kind", "")) for f in step_facts[-_MIDCYCLE_CHECK_EVERY:]}
        prior_kinds = {str(getattr(f, "kind", "")) for f in step_facts[-_MIDCYCLE_CHECK_EVERY * 2:-_MIDCYCLE_CHECK_EVERY]}
        if recent_kinds and recent_kinds.issubset(prior_kinds):
            return "abort_cycle"
    return "continue"


def _compute_step_budget(
    cycle: int,
    base_budget: int,
    prior_outcome: str,
    prior_steps_used: int,
    prior_budget: int,
) -> int:
    """Return budget for this cycle. Default OFF → always returns base_budget."""
    if not _STEPS_ADAPTIVE or cycle <= 2:
        return base_budget
    if prior_outcome == "stuck" and prior_budget > 0 and prior_steps_used >= int(0.8 * prior_budget):
        return min(_STEPS_MAX, max(base_budget, int(prior_steps_used * 1.5)))
    return base_budget


def _classify_hint_type(hypothesis: str) -> str:
    """Return short tag of the dominant hint type in a hypothesis_for_next, or ''.

    First-match wins on the canonical patterns above so type is stable across cycles.
    """
    if not hypothesis:
        return ""
    text = hypothesis
    for marker, tag in _HINT_TYPE_PATTERNS:
        if marker in text:
            return tag
    return ""

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

    FIX-376d: under RESEARCHER_REFLECTOR_DIVERSIFY=1 the check switches from
    "all pairs ≥ threshold" to "mean pairwise Jaccard ≥ stricter threshold"
    AND treats k=2 identical hypotheses (Jaccard=1.0 between consecutive)
    as monotonic unconditionally — covers the t43-style reflector lock-in
    where the same hypothesis surfaces verbatim across cycles.
    """
    if len(history) < k + 1:
        return False
    recent = history[-(k + 1):]
    if _REFLECTOR_DIVERSIFY:
        # Unconditional trip: any two consecutive identical (Jaccard=1.0).
        for i in range(len(recent) - 1):
            if _jaccard(recent[i], recent[i + 1]) >= 0.999:
                return True
        sims: list[float] = []
        for i in range(len(recent)):
            for j in range(i + 1, len(recent)):
                sims.append(_jaccard(recent[i], recent[j]))
        if not sims:
            return False
        mean_sim = sum(sims) / len(sims)
        return mean_sim >= _REFLECTOR_DIVERSIFY_SIM_THRESHOLD
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
            fail_closed=_EVAL_FAIL_CLOSED,  # FIX-376a
        )
    except Exception as exc:
        # FIX-376a: even outer-level exceptions respect fail_closed semantics.
        if _EVAL_FAIL_CLOSED:
            print(f"[researcher] evaluator gate failed ({exc}) — inconclusive")
            return (False, ["evaluator_error"], "EVAL_ERROR")
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
    # FIX-376g: track node IDs poisoned during THIS trial so the next cycle's
    # retrieve_relevant skips them. Populated when reflection.outcome ∈ {stuck, error}.
    _degraded_this_session: set[str] = set()

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
    # FIX-375b: cross-cycle state for evaluator-primary gate + hard guard.
    _outcome_history: list[str] = []
    _consecutive_ok_count = 0
    _last_ok_answer = ""
    # FIX-376b: hint forcing state — track type and consecutive count of the
    # last hint that was injected via reflection.hypothesis_for_next.
    _last_hint_type = ""
    _consecutive_hint_count = 0
    # FIX-376e: adaptive budget bookkeeping + global cap (escape ladder).
    _total_steps_used = 0
    _prior_outcome = ""
    _prior_steps_used = 0
    _prior_budget = steps_per_cycle
    stats["researcher_step_budget_per_cycle"] = []
    # FIX-377: snapshot of cycle 1 for "first answer is final" short-circuit.
    # When cycle ≥ 2's run_loop fails with INVALID_ARGUMENT on
    # ReportTaskCompletion, the harness has already accepted cycle 1's answer
    # — we short-circuit using this snapshot rather than letting reflector
    # hallucinate rules from a degenerate cycle.
    _first_cycle_outcome: str = ""
    _first_cycle_step_facts: list = []
    _first_cycle_report = None
    _first_cycle_reflection = None

    for cycle in range(1, max_cycles + 1):
        stats["researcher_cycles_used"] = cycle

        # FIX-376e: compute this cycle's step budget (default = static), then
        # consult the global escape ladder. If the projected total would exceed
        # the cap, accept best-known and break out — runaway protection when
        # adaptive budgets stack up.
        _this_budget = _compute_step_budget(
            cycle, steps_per_cycle, _prior_outcome, _prior_steps_used, _prior_budget,
        )
        if _STEPS_ADAPTIVE and _total_steps_used + _this_budget > _TOTAL_STEP_BUDGET:
            _remaining = max(0, _TOTAL_STEP_BUDGET - _total_steps_used)
            if _remaining < max(3, steps_per_cycle // 3):
                stats["researcher_global_step_cap_hit"] = True
                stats["researcher_total_steps_used"] = _total_steps_used
                # Salvage best-known: previous cycle's reflection.final_answer
                # if any; otherwise let the post-loop archive path handle it.
                if cycle_reflections:
                    _last = cycle_reflections[-1]
                    stats["researcher_best_known_answer"] = _last.final_answer
                    stats["researcher_best_known_outcome"] = _last.outcome
                print(
                    f"[researcher] global step cap reached "
                    f"({_total_steps_used}/{_TOTAL_STEP_BUDGET}) — accepting best-known"
                )
                break
            # Trim to fit remaining quota rather than skip the cycle entirely.
            _this_budget = _remaining
        stats["researcher_step_budget_per_cycle"].append(_this_budget)
        print(
            f"\n[researcher] ===== cycle {cycle}/{max_cycles} (budget={_this_budget}) ====="
        )

        # FIX-376b: update hint-type tracker based on the previous cycle's final
        # hypothesis (after all suffix mutations). Same type for ≥2 consecutive
        # cycles → next inject becomes mandatory user-message via _HINT_FORCING.
        if _HINT_FORCING and cycle_reflections:
            _prev_type = _classify_hint_type(
                cycle_reflections[-1].hypothesis_for_next or ""
            )
            if _prev_type and _prev_type == _last_hint_type:
                _consecutive_hint_count += 1
            elif _prev_type:
                _last_hint_type = _prev_type
                _consecutive_hint_count = 1
            else:
                _last_hint_type = ""
                _consecutive_hint_count = 0

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
        # FIX-376g: pass quarantine knobs only when opted in; defaults preserve
        # normal-mode behaviour for any callers reaching this code path.
        if _GRAPH_ENABLED:
            if _GRAPH_QUARANTINE:
                graph_section = wiki_graph.retrieve_relevant(
                    graph, task_type, task_text, top_k=_GRAPH_TOP_K,
                    min_retrieve_confidence=_GRAPH_MIN_CONF,
                    degraded_this_session=_degraded_this_session,
                    quarantine_weak_antipatterns=True,
                )
            else:
                graph_section = wiki_graph.retrieve_relevant(
                    graph, task_type, task_text, top_k=_GRAPH_TOP_K,
                )
        else:
            graph_section = ""
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

        # FIX-376b: if the previous cycle's hypothesis injected the same hint
        # type for the second time in a row (and we're under the cap), promote
        # it to a mandatory user-message visible above the noise of the system
        # addendum. The previous-cycle hypothesis is already embedded in the
        # addendum's "Current hypothesis:" line; this duplicates the critical
        # bit as a fresh user turn so the agent cannot silently drop it.
        if (
            _HINT_FORCING
            and cycle_reflections
            and _last_hint_type
            and _consecutive_hint_count >= 2
            and _consecutive_hint_count <= _HINT_MAX_INJECTIONS + 1
        ):
            _force_msg = (
                f"[MANDATORY HINT — DO NOT IGNORE] The previous cycle flagged "
                f"`{_last_hint_type}` and you ignored it. This cycle you MUST "
                f"either act on this hint or explicitly justify why it does "
                f"not apply: {(cycle_reflections[-1].hypothesis_for_next or '').strip()}"
            )
            pre.log.append({"role": "user", "content": _force_msg})
            pre.preserve_prefix.append({"role": "user", "content": _force_msg})
            stats["researcher_hint_forcing_injected"] = (
                stats.get("researcher_hint_forcing_injected", 0) + 1
            )
            print(
                f"[researcher] hint forcing — injected mandatory user-message "
                f"for type={_last_hint_type} (consec={_consecutive_hint_count})"
            )

        # FIX-376c: pass mid-cycle breakout callback. Closure captures cycle.
        _breakout_cb = (
            (lambda sf, _c=cycle: _midcycle_breakout(sf, _c))
            if _MIDCYCLE_BREAKOUT else None
        )
        cycle_stats = run_loop(
            vm, model, task_text, pre, cfg,
            task_type=task_type,
            evaluator_model="",       # disabled in researcher mode regardless
            evaluator_cfg=None,
            researcher_mode=True,
            max_steps=_this_budget,  # FIX-376e: adaptive budget (default: steps_per_cycle)
            researcher_breakout_check=_breakout_cb,
        )
        # FIX-376c: track breakout aborts; if aborted, prepend MIDCYCLE_ABORTED
        # marker to next-cycle hypothesis after reflector returns.
        _midcycle_aborted = bool(cycle_stats.get("midcycle_aborted"))
        if _midcycle_aborted:
            stats["researcher_midcycle_aborts"] = (
                stats.get("researcher_midcycle_aborts", 0) + 1
            )
        stats = _merge_stats(stats, cycle_stats)

        agent_outcome = cycle_stats.get("outcome", "") or ""
        step_facts = cycle_stats.get("step_facts", []) or []
        done_ops = cycle_stats.get("done_ops", []) or []
        last_step_facts = step_facts

        # FIX-377: cycle ≥ 2 saw the harness reject ReportTaskCompletion with
        # INVALID_ARGUMENT — cycle 1 already locked in an answer. Short-circuit
        # using the cycle-1 snapshot. Reflector is NOT invoked, graph is NOT
        # merged. Prevents hallucinated rules from a degenerate trajectory.
        if (
            cycle > 1
            and cycle_stats.get("report_completion_attempted")
            and cycle_stats.get("report_completion_dispatch_error_code") == "INVALID_ARGUMENT"
        ):
            stats["researcher_first_answer_final"] = True
            stats["researcher_early_stop"] = "first_answer_final"
            _snap_outcome = _first_cycle_outcome
            _snap_facts = _first_cycle_step_facts
            _snap_report = _first_cycle_report
            _snap_refl = _first_cycle_reflection
            trajectory = _build_structured_trajectory(_snap_facts)
            if _snap_outcome == "OUTCOME_OK":
                traj_hash = wiki_graph.hash_trajectory(_snap_facts)
                stats["researcher_solved"] = True
                stats["researcher_pending_promotion"] = {
                    "task_type": task_type,
                    "task_id": task_id,
                    "traj_hash": traj_hash,
                    "trajectory": trajectory,
                    "insights": list(_snap_refl.what_worked) if _snap_refl else [],
                    "goal_shape": (_snap_refl.goal_shape if _snap_refl else ""),
                    "final_answer": (
                        getattr(_snap_report, "message", "") if _snap_report else ""
                    ),
                    "touched_node_ids": list(touched_node_ids),
                }
            elif _snap_outcome in _TERMINAL_REFUSALS:
                stats["researcher_pending_refusal"] = {
                    "task_type": task_type,
                    "task_id": task_id,
                    "outcome": _snap_outcome,
                    "goal_shape": (_snap_refl.goal_shape if _snap_refl else ""),
                    "refusal_reason": (
                        (_snap_refl.hypothesis_for_next if _snap_refl else "")
                        or "first answer was a refusal — harness locked it in"
                    ),
                    "trajectory": trajectory,
                }
            if _GRAPH_ENABLED:
                wiki_graph.save_graph(graph)
            print(
                f"[researcher] cycle {cycle} INVALID_ARGUMENT on report — "
                f"first answer is final, short-circuiting with snapshot "
                f"outcome={_snap_outcome}"
            )
            return stats

        # FIX-376e: track cumulative step usage for the global cap (escape ladder)
        # and feed the next cycle's adaptive budget calculation.
        _cycle_steps = int(cycle_stats.get("step_count", 0) or 0)
        _total_steps_used += _cycle_steps
        stats["researcher_total_steps_used"] = _total_steps_used
        _prior_steps_used = _cycle_steps
        _prior_budget = _this_budget
        # Count soft-stall advisories from this cycle (if loop.py emitted any).
        _soft_advisories = sum(
            1 for f in step_facts if getattr(f, "kind", "") == "stall_advisory"
        )
        if _soft_advisories:
            stats["researcher_soft_stall_hints"] = (
                stats.get("researcher_soft_stall_hints", 0) + _soft_advisories
            )

        # FIX-376d: feed prior raw hypotheses to reflector so it can avoid
        # repeating the same idea verbatim. Disabled → empty list, no behaviour change.
        _prior_hyps_for_reflector = (
            _hypothesis_history[-_REFLECTOR_PRIOR_WINDOW:]
            if _REFLECTOR_DIVERSIFY else []
        )
        reflection = reflect(
            task_text=task_text,
            task_type=task_type,
            cycle=cycle,
            step_facts=step_facts,
            done_ops=done_ops,
            agent_outcome=agent_outcome,
            model=model,
            cfg=cfg,
            # FIX-375b/B: cross-cycle memory so reflector can detect outcome looping.
            outcome_history=list(_outcome_history),
            prior_hypotheses=_prior_hyps_for_reflector,
        )
        # FIX-376d: reflector signalled stuck_converged → bump counter.
        if _REFLECTOR_DIVERSIFY and (reflection.hypothesis_for_next or "").strip().lower() == "stuck_converged":
            stats["researcher_stuck_converged_signaled"] = (
                stats.get("researcher_stuck_converged_signaled", 0) + 1
            )
        # FIX-375b: track outcome history + consecutive-OK counter AFTER reflect.
        _outcome_history.append(agent_outcome or "")
        if agent_outcome == "OUTCOME_OK":
            _ans = (cycle_stats.get("report") and getattr(
                cycle_stats["report"], "message", ""
            ) or "").strip().lower()
            if _ans and _ans == _last_ok_answer:
                _consecutive_ok_count += 1
            else:
                _consecutive_ok_count = 1
                _last_ok_answer = _ans
        else:
            _consecutive_ok_count = 0
            _last_ok_answer = ""
        cycle_reflections.append(reflection)
        # FIX-377: snapshot cycle 1 — needed if cycle 2's report dispatch fails
        # with INVALID_ARGUMENT (harness already accepted cycle 1's answer).
        if cycle == 1:
            _first_cycle_outcome = agent_outcome
            _first_cycle_step_facts = list(step_facts)
            _first_cycle_report = cycle_stats.get("report")
            _first_cycle_reflection = reflection
        # FIX-376c: surface mid-cycle abort marker to next cycle's hypothesis
        # so hint-forcing / classifiers can see it. Distinct token avoids
        # collision with other markers (FLIP/REJECTED/DRIFT/REFUSAL_RETRY).
        if _midcycle_aborted:
            _existing_h = (reflection.hypothesis_for_next or "").strip()
            _midcycle_msg = (
                "MIDCYCLE_ABORTED: previous cycle aborted early due to "
                "tight tool/path repeats — try a fundamentally different path"
            )
            reflection.hypothesis_for_next = (
                f"{_existing_h} | {_midcycle_msg}" if _existing_h else _midcycle_msg
            )
        # FIX-376e: feed reflector outcome into next-cycle budget calc.
        _prior_outcome = reflection.outcome or ""
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
            # FIX-376h: full-trace LCS fallback when prefix-check returns nothing.
            if not drift and _DRIFT_FULL_TRACE:
                drift = _detect_drift_lcs(step_facts, page_patterns, _DRIFT_LCS_MIN)
                if drift:
                    stats["researcher_drift_lcs_hints"] = (
                        stats.get("researcher_drift_lcs_hints", 0) + 1
                    )
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

        # FIX-377: skip graph merge when reflector saw a contaminated trajectory
        # (dispatch error on report, or self-reported error/stuck). Reflector
        # tends to hallucinate rules when the cycle was structurally broken.
        _skip_merge = (
            cycle_stats.get("report_completion_dispatch_error_code") is not None
            or reflection.outcome in ("error", "stuck")
        )
        if _GRAPH_ENABLED and not _skip_merge:
            touched = wiki_graph.merge_updates(graph, reflection.graph_deltas)
            touched_node_ids.extend(touched)
            # FIX-376g: cycle that reflector marked stuck/error → put its
            # touched nodes into session quarantine so the next cycle's
            # retrieve_relevant skips them.
            if _GRAPH_QUARANTINE and reflection.outcome in ("stuck", "error"):
                _degraded_this_session.update(touched)
                stats["researcher_graph_quarantined_nodes"] = len(_degraded_this_session)
        elif _GRAPH_ENABLED:
            stats["researcher_graph_merge_skipped"] = (
                stats.get("researcher_graph_merge_skipped", 0) + 1
            )

        # FIX-374: terminal refusals in researcher mode retry up to
        # RESEARCHER_REFUSAL_MAX_RETRIES times (default 3). Beyond that, the
        # agent has clearly converged on refusal — wasting remaining cycles is
        # pointless. Evaluator is not consulted: observed false-approve on t11.
        if agent_outcome in _TERMINAL_REFUSALS and cycle < max_cycles:
            _retries = stats.get("researcher_refusal_retries", 0)
            # FIX-376f: dynamic cap — scale with cycles_remaining so refusals
            # can never burn the full max_cycles budget by themselves. When
            # disabled, fall back to the static FIX-374 limit.
            if _REFUSAL_DYNAMIC:
                _cycles_remaining = max_cycles - cycle
                _refusal_cap = max(
                    _REFUSAL_MIN_CYCLES_LEFT,
                    _cycles_remaining - 1,
                )
            else:
                _refusal_cap = _REFUSAL_MAX_RETRIES
            if _retries < _refusal_cap:
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
                    f"— retrying ({_retries + 1}/{_refusal_cap})"
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
                # FIX-376f: ground the flip hint in observed past failures.
                _alt_section = ""
                if _REFUSAL_DYNAMIC:
                    _negatives = _load_negative_warnings(
                        task_type, task_text, top_k=2,
                    )
                    if _negatives:
                        # Strip header line, keep bullets; cap to 400 chars to
                        # avoid drowning the flip in noise.
                        _bullets = "\n".join(
                            ln for ln in _negatives.splitlines()
                            if ln.startswith("  - ") or ln.startswith("- ")
                        )[:400]
                        if _bullets:
                            _alt_section = (
                                f" Alternative interpretations seen on similar "
                                f"tasks:\n{_bullets}"
                            )
                _flip = (
                    f"OUTCOME_FLIP_HINT: You've refused {_retries} times "
                    f"citing '{_last_reason}'. If there's ANY plausible interpretation "
                    f"where the task IS answerable (different tool semantics, different "
                    f"target folder, different definition of the verb), attempt it now. "
                    f"This is your last cycle before final accept.{_alt_section}"
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
                f"— retry limit {_refusal_cap} reached, accepting refusal"
            )

        # FIX-375b/C: hard guard against runaway OUTCOME_OK loop. If the agent
        # has produced ≥_OK_LOOP_LIMIT consecutive OUTCOME_OK with the same
        # final_answer, evaluator/flip have already had their chance. Force-flip
        # to refusal: emit pending_refusal with OUTCOME_NONE_CLARIFICATION, the
        # benchmark rewards correct refusals (FIX-366) and on t43-class tasks
        # (real refusal expected) this hits the right answer.
        if (
            agent_outcome == "OUTCOME_OK"
            and _consecutive_ok_count >= _OK_LOOP_LIMIT
            and cycle < max_cycles
        ):
            stats["researcher_ok_loop_break"] = True
            stats["researcher_early_stop"] = "OUTCOME_NONE_CLARIFICATION"
            trajectory = _build_structured_trajectory(step_facts)
            stats["researcher_pending_refusal"] = {
                "task_type": task_type,
                "task_id": task_id,
                "outcome": "OUTCOME_NONE_CLARIFICATION",
                "goal_shape": reflection.goal_shape,
                "refusal_reason": (
                    f"hard-guard: agent produced OUTCOME_OK with same answer "
                    f"{_consecutive_ok_count} times in a row — task likely unanswerable"
                ),
                "trajectory": trajectory,
            }
            if _GRAPH_ENABLED:
                wiki_graph.save_graph(graph)
            print(
                f"[researcher] OK-loop hard-guard tripped on cycle {cycle} "
                f"(consec={_consecutive_ok_count}) — flipping to refusal"
            )
            return stats

        # FIX-374: evaluator gate on self-OUTCOME_OK — decide whether to trust
        # the cycle outcome before short-circuiting. On reject + cycles remaining,
        # inject verdict as a hint for the next cycle and continue.
        # FIX-375b/A: drop reflection.is_solved from gate trigger. Observed t43:
        # agent self-reports OUTCOME_OK 15 cycles in a row, but reflector keeps
        # outcome="stuck" → evaluator was never invoked, OK-flip detector dormant.
        # Now: agent says OK → evaluator decides; reflector verdict is context.
        _gate_relevant = (
            _EVAL_GATED
            and cycle < max_cycles
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
            # FIX-376a: inconclusive (evaluator error under fail-closed) — skip to
            # next cycle without injecting a misleading rejection hint.
            if _EVAL_FAIL_CLOSED and _hint == "EVAL_ERROR":
                stats["researcher_eval_inconclusive"] = (
                    stats.get("researcher_eval_inconclusive", 0) + 1
                )
                print(
                    f"[researcher] evaluator inconclusive on cycle {cycle} "
                    f"— skipping short-circuit, continuing to next cycle"
                )
                continue
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
                # FIX-375b/A: evaluator approved, even if reflector says stuck —
                # treat OK as solved for short-circuit purposes (is_solved is a
                # property derived from reflection.outcome, so mutate outcome).
                reflection.outcome = "solved"

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
