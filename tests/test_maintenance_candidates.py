import json
import logging
import pytest
from pathlib import Path
from agent.maintenance.candidates import log_candidates, CandidatesReport, _normalize


def test_normalize():
    assert _normalize("Email Task") == "email_task"
    assert _normalize("LOOKUP--TYPE") == "lookup_type"
    assert _normalize("  crm  ") == "crm"
    assert _normalize("new-type-v2") == "new_type_v2"


def test_missing_file(tmp_path):
    report = log_candidates(candidates_path=tmp_path / "missing.jsonl", min_count=5)
    assert isinstance(report, CandidatesReport)
    assert report.total == 0
    assert report.above_threshold == {}


def test_below_threshold_excluded_from_above(tmp_path):
    path = tmp_path / "candidates.jsonl"
    path.write_text(
        "\n".join([json.dumps({"llm_suggested": "new_type"})] * 3),
        encoding="utf-8",
    )
    report = log_candidates(candidates_path=path, min_count=5)
    assert report.total == 3
    assert "new_type" not in report.above_threshold
    assert report.all_counts.get("new_type") == 3


def test_counts_above_threshold(tmp_path):
    path = tmp_path / "candidates.jsonl"
    path.write_text(
        "\n".join([json.dumps({"llm_suggested": "new_type"})] * 7),
        encoding="utf-8",
    )
    report = log_candidates(candidates_path=path, min_count=5)
    assert report.total == 7
    assert report.above_threshold == {"new_type": 7}


def test_empty_file(tmp_path):
    path = tmp_path / "candidates.jsonl"
    path.write_text("", encoding="utf-8")
    report = log_candidates(candidates_path=path, min_count=5)
    assert report.total == 0


def test_logs_warning_when_above_threshold(tmp_path, caplog):
    path = tmp_path / "candidates.jsonl"
    lines = (
        [json.dumps({"llm_suggested": "alpha"})] * 6 +
        [json.dumps({"llm_suggested": "beta"})] * 3
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        report = log_candidates(candidates_path=path, min_count=5)
    assert "alpha" in report.above_threshold
    assert any("alpha" in msg for msg in caplog.messages)
