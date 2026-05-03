import json
import pytest
from pathlib import Path
from agent.maintenance.candidates import log_candidates, CandidatesReport, _normalize


def test_normalize_lowercases_and_underscores():
    assert _normalize("Email Task") == "email_task"
    assert _normalize("LOOKUP--TYPE") == "lookup_type"
    assert _normalize("  crm  ") == "crm"
    assert _normalize("new-type-v2") == "new_type_v2"


def test_missing_file_returns_empty(tmp_path):
    report = log_candidates(candidates_path=tmp_path / "missing.jsonl", min_count=5)
    assert isinstance(report, CandidatesReport)
    assert report.total == 0
    assert report.above_threshold == {}


def test_below_threshold_not_in_above(tmp_path):
    path = tmp_path / "candidates.jsonl"
    path.write_text(
        "\n".join([json.dumps({"llm_suggested": "new_type"})] * 3),
        encoding="utf-8",
    )
    report = log_candidates(candidates_path=path, min_count=5)
    assert report.total == 3
    assert "new_type" not in report.above_threshold
    assert report.all_counts.get("new_type") == 3


def test_above_threshold_included(tmp_path):
    path = tmp_path / "candidates.jsonl"
    path.write_text(
        "\n".join([json.dumps({"llm_suggested": "new_type"})] * 7),
        encoding="utf-8",
    )
    report = log_candidates(candidates_path=path, min_count=5)
    assert report.total == 7
    assert report.above_threshold == {"new_type": 7}


def test_multiple_types(tmp_path):
    path = tmp_path / "candidates.jsonl"
    lines = (
        [json.dumps({"llm_suggested": "alpha"})] * 6 +
        [json.dumps({"llm_suggested": "beta"})] * 3
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    report = log_candidates(candidates_path=path, min_count=5)
    assert report.total == 9
    assert "alpha" in report.above_threshold
    assert "beta" not in report.above_threshold


def test_empty_file_returns_empty(tmp_path):
    path = tmp_path / "candidates.jsonl"
    path.write_text("", encoding="utf-8")
    report = log_candidates(candidates_path=path, min_count=5)
    assert report.total == 0
