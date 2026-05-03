from __future__ import annotations
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class CandidatesReport:
    total: int = 0
    above_threshold: dict[str, int] = field(default_factory=dict)
    all_counts: dict[str, int] = field(default_factory=dict)


def log_candidates(
    candidates_path: Path | str = Path("data/task_type_candidates.jsonl"),
    min_count: int = 5,
) -> CandidatesReport:
    candidates_path = Path(candidates_path)
    report = CandidatesReport()

    if not candidates_path.exists():
        return report

    labels: list[str] = []
    for line in candidates_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        label = _normalize(rec.get("llm_suggested", ""))
        if label:
            labels.append(label)

    counts = Counter(labels)
    report.total = len(labels)
    report.all_counts = dict(counts)
    report.above_threshold = {k: v for k, v in counts.items() if v >= min_count}

    if report.above_threshold:
        log.warning(
            "[candidates] %d type(s) above min_count=%d: %s",
            len(report.above_threshold), min_count, report.above_threshold,
        )
    else:
        log.info("[candidates] no candidates above min_count=%d (total=%d)", min_count, report.total)

    return report


def _normalize(label: str) -> str:
    label = label.lower().strip()
    label = re.sub(r"[^a-z0-9]+", "_", label)
    label = re.sub(r"_+", "_", label).strip("_")
    return label
