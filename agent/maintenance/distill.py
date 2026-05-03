from __future__ import annotations
import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

_TOP_N = 5


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
        if ex.get("score", 0.0) < 1.0:
            continue
        by_type.setdefault(t, []).append(ex)

    for t in all_types_seen:
        examples = by_type.get(t, [])
        if len(examples) < min_examples:
            result.types_skipped.append(t)
            log.info("[distill] %s: %d examples < min_examples=%d, skipping", t, len(examples), min_examples)
            continue

        contract = _distill_one(examples)
        result.types_processed.append(t)

        if apply:
            contracts_dir.mkdir(parents=True, exist_ok=True)
            out = contracts_dir / f"{t}.json"
            out.write_text(json.dumps(contract, indent=2, ensure_ascii=False), encoding="utf-8")
            log.info("[distill] %s: wrote %s", t, out)

    return result


def _distill_one(examples: list[dict]) -> dict:
    def top_n(field_name: str) -> list[str]:
        items: list[str] = []
        for ex in examples:
            val = ex.get(field_name, [])
            if isinstance(val, list):
                items.extend(val)
        return [item for item, _ in Counter(items).most_common(_TOP_N)]

    return {
        "plan_steps": top_n("plan_steps"),
        "success_criteria": top_n("success_criteria"),
        "required_evidence": top_n("required_evidence"),
        "failure_conditions": top_n("failure_conditions"),
    }
