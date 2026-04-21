"""Example collector for DSPy COPRO/MIPRO optimization (Variant 4).

Builder examples: (task_text, task_type, addendum, score) → data/dspy_examples.jsonl
Evaluator examples: (evaluator inputs, score) → data/dspy_eval_examples.jsonl

When ≥ THRESHOLD real examples accumulate, prints a hint to run optimize_prompts.py.
Synthetic cold-start examples live in data/dspy_synthetic.jsonl and are used
by optimize_prompts.py when fewer than THRESHOLD real examples are available.
"""
from __future__ import annotations

import json
from pathlib import Path

_DATA = Path(__file__).parent.parent / "data"
_EXAMPLES_PATH = _DATA / "dspy_examples.jsonl"
_EVAL_EXAMPLES_PATH = _DATA / "dspy_eval_examples.jsonl"
_SYNTHETIC_PATH = _DATA / "dspy_synthetic.jsonl"
_THRESHOLD = 30
_EVAL_THRESHOLD = 20


# ---------------------------------------------------------------------------
# Write — builder
# ---------------------------------------------------------------------------

def record_example(
    task_text: str,
    task_type: str,
    addendum: str,
    score: float,
) -> None:
    """Append one (task, addendum, score) tuple to the JSONL example log.

    vault_tree and agents_md are intentionally NOT persisted: in a fixed-vault
    setup (PAC-1) they are near-constant (agents_md had 4 unique values across
    366 examples) and inflate examples 4–5x with redundant context, which
    pressures the meta-LLM during COPRO to paraphrase task values and drop
    trailing punctuation. Vault semantics belong in Signature instructions.

    Prints a hint to run the optimizer when the count first reaches THRESHOLD.
    """
    _DATA.mkdir(parents=True, exist_ok=True)
    entry = {
        "task_text": task_text,
        "task_type": task_type,
        "addendum": addendum,
        "score": score,
    }
    with _EXAMPLES_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    count = _count_examples()
    if count == _THRESHOLD:
        print(
            f"[dspy] {_THRESHOLD} real builder examples collected "
            "→ run: uv run python optimize_prompts.py --target builder"
        )


# ---------------------------------------------------------------------------
# Write — evaluator
# ---------------------------------------------------------------------------

def record_eval_example(
    task_text: str,
    task_type: str,
    proposed_outcome: str,
    agent_message: str,
    done_ops: str,
    completed_steps: str,
    skepticism_level: str,
    score: float,
) -> None:
    """Append one evaluator call with ground-truth score to dspy_eval_examples.jsonl.

    expected_approved_str is derived from the benchmark score:
      score == 1.0  →  "yes"  (agent was correct, evaluator should approve)
      score <  1.0  →  "no"   (agent was wrong, evaluator should reject)

    Prints a hint to run the optimizer when the count first reaches EVAL_THRESHOLD.
    """
    _DATA.mkdir(parents=True, exist_ok=True)
    entry = {
        "task_text": task_text,
        "task_type": task_type,
        "proposed_outcome": proposed_outcome,
        "agent_message": agent_message,
        "done_ops": done_ops,
        "completed_steps": completed_steps,
        "skepticism_level": skepticism_level,
        "expected_approved_str": "yes" if score == 1.0 else "no",
        "score": score,
    }
    with _EVAL_EXAMPLES_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    count = _count_eval_examples()
    if count == _EVAL_THRESHOLD:
        print(
            f"[dspy] {_EVAL_THRESHOLD} real evaluator examples collected "
            "→ run: uv run python optimize_prompts.py --target evaluator"
        )


# ---------------------------------------------------------------------------
# Read — builder
# ---------------------------------------------------------------------------

def load_examples(min_score: float = 0.8) -> list[dict]:
    """Return builder examples from the JSONL log with score >= min_score."""
    return _load_jsonl(_EXAMPLES_PATH, score_filter=min_score)


def load_synthetic() -> list[dict]:
    """Return cold-start synthetic examples from data/dspy_synthetic.jsonl."""
    return _load_jsonl(_SYNTHETIC_PATH)


def get_trainset(min_score: float = 0.8, max_per_type: int | None = None) -> list[dict]:
    """Return builder examples: real ones if ≥ THRESHOLD, else real + synthetic.

    max_per_type: if set, takes the last N examples per task_type (guarantees
    representation of all types; total = sum of min(N, available) per type).
    """
    real = _tail_per_type(load_examples(min_score), max_per_type)
    if len(real) >= _THRESHOLD:
        return real
    return real + load_synthetic()


# ---------------------------------------------------------------------------
# Read — evaluator
# ---------------------------------------------------------------------------

def load_eval_examples() -> list[dict]:
    """Return all accumulated evaluator examples (both approved and rejected)."""
    return _load_jsonl(_EVAL_EXAMPLES_PATH)


def get_eval_trainset(max_per_class: int | None = None) -> list[dict]:
    """Return evaluator examples if ≥ EVAL_THRESHOLD, else empty list (use hardcoded fallback).

    max_per_class: if set, takes last N per (task_type, approved_str) group — guarantees
    representation across all task types in both yes and no classes.
    """
    real = load_eval_examples()
    if len(real) < _EVAL_THRESHOLD:
        return []
    if max_per_class is None:
        return real
    return _tail_per_type(real, max(1, max_per_class), type_key="_eval_group")


def get_classifier_trainset(min_score: float = 0.8, max_per_type: int | None = None) -> list[dict]:
    """Return deduplicated (task_text, vault_hint, task_type) dicts from builder examples.

    max_per_type: if set, applies per-type cap before deduplication.
    """
    raw = _tail_per_type(load_examples(min_score), max_per_type)
    seen: set[tuple[str, str]] = set()
    result: list[dict] = []
    for ex in raw:
        key = (ex.get("task_text", ""), ex.get("task_type", "default"))
        if key not in seen:
            seen.add(key)
            agents_md = ex.get("agents_md", "")
            vault_tree = ex.get("vault_tree", "")
            parts = []
            if agents_md:
                parts.append(f"AGENTS.MD:\n{agents_md[:300]}")
            if vault_tree:
                parts.append(vault_tree[:200])
            result.append({
                "task_text": key[0],
                "task_type": key[1],
                "vault_hint": "\n".join(parts),
            })
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _tail_per_type(items: list, n: int | None, type_key: str = "task_type") -> list:
    """Return last N items per group. Preserves original order within each group.

    If n is None, returns items unchanged. If a group has fewer than N examples,
    all of them are included. Total size = sum(min(N, count_per_group)).

    type_key="_eval_group" is a special sentinel: groups by (task_type, approved_str).
    """
    if n is None:
        return items
    if n <= 0:
        return []
    groups: dict = {}
    for ex in items:
        if type_key == "_eval_group":
            t = (ex.get("task_type", "default"), ex.get("expected_approved_str", "yes"))
        else:
            t = ex.get(type_key, "default")
        groups.setdefault(t, []).append(ex)
    result = []
    for group in groups.values():
        result.extend(group[-n:])
    return result


def _load_jsonl(path: Path, score_filter: float | None = None) -> list[dict]:
    if not path.exists():
        return []
    result: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                ex = json.loads(line)
                if score_filter is None or ex.get("score", 0.0) >= score_filter:
                    result.append(ex)
            except json.JSONDecodeError:
                pass
    return result


def _count_examples() -> int:
    if not _EXAMPLES_PATH.exists():
        return 0
    with _EXAMPLES_PATH.open(encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


def _count_eval_examples() -> int:
    if not _EVAL_EXAMPLES_PATH.exists():
        return 0
    with _EVAL_EXAMPLES_PATH.open(encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())
