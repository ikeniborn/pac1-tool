"""Verify main.py creates/closes TraceLogger and calls log_header + log_task_result."""
import json
from unittest.mock import MagicMock, patch
import pytest


def test_run_single_task_creates_jsonl_and_removes_log(tmp_path, monkeypatch):
    """After _run_single_task: .jsonl created, no .log file, log_header + log_task_result called."""
    import main as m

    monkeypatch.setattr(m, "_run_dir", tmp_path)

    fake_trial = MagicMock()
    fake_trial.task_id = "t01"
    fake_trial.trial_id = "trial-1"
    fake_trial.harness_url = "http://x"
    fake_trial.instruction = "find item"

    fake_end = MagicMock()
    fake_end.score = 1.0
    fake_end.score_detail = ["ok"]

    fake_client = MagicMock()
    fake_client.start_trial.return_value = fake_trial
    fake_client.end_trial.return_value = fake_end

    with patch("main.HarnessServiceClientSync", return_value=fake_client), \
         patch("main.run_agent", return_value={"input_tokens": 10, "output_tokens": 5,
                                                "outcome": "OUTCOME_OK", "cycles_used": 1,
                                                "task_type": "lookup", "model_used": "m"}):
        m._run_single_task("trial-1", [])

    jsonl_path = tmp_path / "t01.jsonl"
    assert jsonl_path.exists(), "t01.jsonl must be created"
    assert not (tmp_path / "t01.log").exists(), "t01.log must NOT be created"

    records = [json.loads(ln) for ln in jsonl_path.read_text().splitlines() if ln.strip()]
    types = [r["type"] for r in records]
    assert "header" in types
    assert "task_result" in types
