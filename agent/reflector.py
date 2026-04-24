"""Cycle reflector (FIX-362).

Runs ONCE per researcher cycle to condense the just-finished inner-loop trace
into a structured reflection — NOT a blocker. Unlike evaluator.py, the reflector
does not reject or re-route; it produces a journal entry that drives:

  1. the next cycle's addendum ('what to try next'),
  2. the research/ wiki fragment,
  3. knowledge-graph deltas (new insights / rules / antipatterns).

Uses agent.dispatch.call_llm_raw — routes through CC-tier automatically when
model is claude-code/*; same retry/fallback logic as the rest of the agent.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .dispatch import call_llm_raw

_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}")

_REFLECTOR_SYSTEM = (
    "You are a research journaler for an AI file-system agent.\n"
    "Given a task and the agent's recent trajectory, produce a compact, honest reflection.\n"
    "Do NOT invent successes. If the agent made no progress, say so.\n"
    "Output STRICT JSON matching the schema. No prose outside the JSON."
)

_REFLECTOR_SCHEMA_HINT = """
{
  "outcome": "solved" | "partial" | "stuck" | "error",
  "what_was_tried": ["<short bullet>", ...],
  "what_worked": ["<short bullet>", ...],
  "what_failed": ["<short bullet>", ...],
  "hypothesis_for_next": "<one sentence>",
  "key_tool_calls": ["<tool>(<path-or-args>)", ...],
  "new_insights": [{"text": "<statement>", "tags": ["<tag>", ...], "confidence": 0.7}],
  "new_rules":    [{"text": "<hard constraint>", "tags": ["<tag>", ...]}],
  "antipatterns": [{"text": "<what NOT to do>", "tags": ["<tag>", ...]}],
  "reused_patterns": []
}
""".strip()


@dataclass
class Reflection:
    outcome: str = "stuck"
    what_was_tried: list = field(default_factory=list)
    what_worked: list = field(default_factory=list)
    what_failed: list = field(default_factory=list)
    hypothesis_for_next: str = ""
    key_tool_calls: list = field(default_factory=list)
    graph_deltas: dict = field(default_factory=dict)  # new_insights/new_rules/antipatterns/reused_patterns

    @property
    def is_solved(self) -> bool:
        return self.outcome == "solved"


def _format_trace(step_facts: list, done_ops: list, agent_outcome: str) -> str:
    ops = "\n".join(f"- {op}" for op in (done_ops or [])) or "(none)"
    facts_lines: list[str] = []
    for f in (step_facts or [])[-30:]:
        kind = getattr(f, "kind", "")
        path = getattr(f, "path", "") or ""
        summary = getattr(f, "summary", "") or ""
        if kind:
            facts_lines.append(f"- {kind}: {path} → {summary[:160]}")
    facts = "\n".join(facts_lines) or "(no step facts)"
    return (
        f"AGENT_REPORTED_OUTCOME: {agent_outcome or '(none)'}\n\n"
        f"DONE_OPS:\n{ops}\n\n"
        f"STEP_FACTS (last 30):\n{facts}"
    )


def _parse_json(raw: str) -> dict:
    if not raw:
        return {}
    m = _JSON_BLOCK_RE.search(raw)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def reflect(
    task_text: str,
    task_type: str,
    cycle: int,
    step_facts: list,
    done_ops: list,
    agent_outcome: str,
    model: str,
    cfg: dict,
    max_tokens: int = 1500,
) -> Reflection:
    """Single LLM call that returns a Reflection. Fail-open: returns a stuck
    reflection with empty deltas if parsing fails."""
    trace = _format_trace(step_facts, done_ops, agent_outcome)
    user_msg = (
        f"TASK: {task_text}\n"
        f"TASK_TYPE: {task_type}\n"
        f"CYCLE: {cycle}\n\n"
        f"TRAJECTORY:\n{trace}\n\n"
        f"Output JSON matching this schema (fill every field; empty arrays allowed):\n"
        f"{_REFLECTOR_SCHEMA_HINT}"
    )
    raw = call_llm_raw(
        system=_REFLECTOR_SYSTEM,
        user_msg=user_msg,
        model=model,
        cfg=cfg,
        max_tokens=max_tokens,
        plain_text=True,
        max_retries=1,
    )
    data = _parse_json(raw or "")
    if not data:
        return Reflection(
            outcome="stuck",
            what_was_tried=[],
            what_worked=[],
            what_failed=["reflector returned unparseable output"],
            hypothesis_for_next="retry with more explicit framing",
            key_tool_calls=[],
            graph_deltas={},
        )
    outcome = data.get("outcome") or "stuck"
    if outcome not in ("solved", "partial", "stuck", "error"):
        outcome = "stuck"
    return Reflection(
        outcome=outcome,
        what_was_tried=list(data.get("what_was_tried", []) or []),
        what_worked=list(data.get("what_worked", []) or []),
        what_failed=list(data.get("what_failed", []) or []),
        hypothesis_for_next=str(data.get("hypothesis_for_next", "") or ""),
        key_tool_calls=list(data.get("key_tool_calls", []) or []),
        graph_deltas={
            "new_insights": data.get("new_insights", []) or [],
            "new_rules": data.get("new_rules", []) or [],
            "antipatterns": data.get("antipatterns", []) or [],
            "reused_patterns": data.get("reused_patterns", []) or [],
        },
    )


def render_fragment(task_id: str, task_type: str, cycle: int, reflection: Reflection) -> str:
    """Markdown rendering of a reflection for write_fragment()."""
    import datetime as _dt
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tried = "\n".join(f"- {x}" for x in reflection.what_was_tried) or "- (none)"
    worked = "\n".join(f"- {x}" for x in reflection.what_worked) or "- (none)"
    failed = "\n".join(f"- {x}" for x in reflection.what_failed) or "- (none)"
    calls = "\n".join(f"- {x}" for x in reflection.key_tool_calls) or "- (none)"
    return (
        f"---\n"
        f"task_id: {task_id}\n"
        f"task_type: {task_type}\n"
        f"cycle: {cycle}\n"
        f"outcome: {reflection.outcome}\n"
        f"timestamp: {ts}\n"
        f"---\n\n"
        f"# Cycle {cycle} — {reflection.outcome}\n\n"
        f"## What was tried\n{tried}\n\n"
        f"## What worked\n{worked}\n\n"
        f"## What failed\n{failed}\n\n"
        f"## Key tool calls\n{calls}\n\n"
        f"## Hypothesis for next\n{reflection.hypothesis_for_next or '(none)'}\n"
    )
