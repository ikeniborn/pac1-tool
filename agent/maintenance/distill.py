from __future__ import annotations
import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

_TOP_N: dict[str, int] = {
    "plan_steps": 6,
    "success_criteria": 4,
    "required_evidence": 3,
    "failure_conditions": 4,
}


@dataclass
class DistillResult:
    types_processed: list[str] = field(default_factory=list)
    types_skipped: list[str] = field(default_factory=list)
    applied: bool = False


def run_distill(
    min_examples: int = 10,
    task_type: str | None = None,
    examples_path: Path | str = Path("data/dspy_contract_examples.jsonl"),
    contracts_dir: Path | str = Path("data/default_contracts"),
    apply: bool = True,
) -> DistillResult:
    examples_path = Path(examples_path)
    contracts_dir = Path(contracts_dir)
    result = DistillResult(applied=apply)

    if not examples_path.exists():
        return result

    by_type: dict[str, list[dict]] = {}
    all_types_seen: set[str] = set()
    for line in examples_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ex = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = ex.get("task_type", "")
        if task_type and t != task_type:
            continue
        all_types_seen.add(t)
        if float(ex.get("score", 0.0)) < 1.0 or ex.get("is_default", False):
            continue
        by_type.setdefault(t, []).append(ex)

    for t in all_types_seen:
        examples = by_type.get(t, [])
        if len(examples) < min_examples:
            result.types_skipped.append(t)
            log.info("[distill] %s: %d good examples < min_examples=%d, skipping", t, len(examples), min_examples)
            continue

        contract = _distill_one(examples)
        result.types_processed.append(t)

        if apply:
            if t == "default":
                log.info("[distill] skipping default — default.json is reserved")
                continue
            contracts_dir.mkdir(parents=True, exist_ok=True)
            out = contracts_dir / f"{t}.json"
            payload = {**contract, "is_default": True, "rounds_taken": 0}
            out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            log.info("[distill] %s: wrote %s", t, out)

    return result


def _distill_one(examples: list[dict]) -> dict:
    def top_n(field_name: str, n: int) -> list[str]:
        counter: Counter = Counter()
        for ex in examples:
            fc = ex.get("final_contract", {})
            for item in fc.get(field_name, []):
                counter[str(item).lower().strip()] += 1
        return [item for item, _ in counter.most_common(n)]

    return {f: top_n(f, n) for f, n in _TOP_N.items()}
