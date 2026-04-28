"""Distill per-type default contracts from successful negotiated examples.

Reads data/dspy_contract_examples.jsonl, groups by task_type, selects top-N
most frequent field elements from score=1.0 examples.

Usage:
    uv run python scripts/distill_contracts.py                   # dry-run: print results
    uv run python scripts/distill_contracts.py --apply           # write files
    uv run python scripts/distill_contracts.py --min-examples 5  # lower threshold
    uv run python scripts/distill_contracts.py --task-type email # single type
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
_DEFAULT_EXAMPLES_PATH = _BASE / "data" / "dspy_contract_examples.jsonl"
_DEFAULT_CONTRACTS_DIR = _BASE / "data" / "default_contracts"

_TOP_N = {
    "plan_steps": 6,
    "success_criteria": 4,
    "required_evidence": 3,
    "failure_conditions": 4,
}


def _normalize(text: str) -> str:
    return text.lower().strip()


def distill_task_type(
    examples: list[dict],
    min_examples: int = 10,
) -> dict | None:
    """Distill a single task_type's examples into a default contract dict.

    Returns None if fewer than min_examples pass score filter.
    """
    good = [
        ex for ex in examples
        if float(ex.get("score", 0)) >= 1.0 and not ex.get("is_default", False)
    ]
    if len(good) < min_examples:
        return None

    result = {}
    for field, top_n in _TOP_N.items():
        counter: Counter = Counter()
        for ex in good:
            fc = ex.get("final_contract", {})
            for item in fc.get(field, []):
                counter[_normalize(str(item))] += 1
        result[field] = [item for item, _ in counter.most_common(top_n)]

    return result


def run_distillation(
    examples_path: Path,
    contracts_dir: Path,
    apply: bool,
    min_examples: int,
    task_type_filter: str | None,
) -> None:
    if not examples_path.exists():
        print(f"[distill] {examples_path} not found — nothing to do")
        return

    all_examples: dict[str, list[dict]] = {}
    with examples_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            tt = rec.get("task_type", "default")
            all_examples.setdefault(tt, []).append(rec)

    types_to_process = (
        [task_type_filter] if task_type_filter else sorted(all_examples.keys())
    )

    for tt in types_to_process:
        examples = all_examples.get(tt, [])
        result = distill_task_type(examples, min_examples=min_examples)
        if result is None:
            good_count = sum(
                1 for ex in examples
                if float(ex.get("score", 0)) >= 1.0 and not ex.get("is_default", True)
            )
            print(f"[distill] {tt}: {good_count} good examples < {min_examples} — skipping")
            continue

        print(f"[distill] {tt}: {len(examples)} total → distilled")
        for field, items in result.items():
            print(f"  {field}: {items}")

        if apply:
            if tt == "default":
                print(f"  [distill] skipping {tt} — default.json is reserved")
                continue
            contracts_dir.mkdir(parents=True, exist_ok=True)
            out_path = contracts_dir / f"{tt}.json"
            out_path.write_text(
                json.dumps({**result, "is_default": True, "rounds_taken": 0},
                           ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"  → written to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Distill per-type default contracts from collected examples."
    )
    parser.add_argument("--apply", action="store_true",
                        help="Write files (default: dry-run)")
    parser.add_argument("--min-examples", type=int, default=10,
                        dest="min_examples",
                        help="Minimum score=1.0 examples per type (default: 10)")
    parser.add_argument("--task-type", default=None, dest="task_type",
                        help="Process single task type only")
    args = parser.parse_args()

    run_distillation(
        examples_path=_DEFAULT_EXAMPLES_PATH,
        contracts_dir=_DEFAULT_CONTRACTS_DIR,
        apply=args.apply,
        min_examples=args.min_examples,
        task_type_filter=args.task_type,
    )


if __name__ == "__main__":
    main()
