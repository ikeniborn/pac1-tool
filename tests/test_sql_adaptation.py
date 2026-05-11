"""Tests for SQL-first few-shot and prephase sql_schema field."""
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch


def _make_mock_pre(sql_schema: str = "CREATE TABLE products (sku TEXT)", agents_md: str = "# Agents"):
    pre = MagicMock()
    pre.sql_schema = sql_schema
    pre.agents_md_content = agents_md
    pre.log = [{"role": "user", "content": f"TASK: test\n{agents_md}"}]
    pre.preserve_prefix = pre.log[:]
    return pre


def test_dry_run_returns_dry_run_outcome(tmp_path, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "1")
    monkeypatch.setenv("MODEL", "test-model")

    import importlib
    import agent.orchestrator as orch
    importlib.reload(orch)

    monkeypatch.setattr(orch, "_DRY_RUN_LOG", tmp_path / "dry_run_analysis.jsonl")
    mock_pre = _make_mock_pre()

    with patch("agent.orchestrator.PcmRuntimeClientSync"), \
         patch("agent.orchestrator.run_prephase", return_value=mock_pre):
        stats = orch.run_agent({}, "http://test", "test task", task_id="t01")

    assert stats["outcome"] == "DRY_RUN"
    assert stats["input_tokens"] == 0
    assert stats["output_tokens"] == 0


def test_dry_run_writes_jsonl(tmp_path, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "1")
    monkeypatch.setenv("MODEL", "test-model")

    import importlib
    import agent.orchestrator as orch
    importlib.reload(orch)

    log_path = tmp_path / "dry_run_analysis.jsonl"
    monkeypatch.setattr(orch, "_DRY_RUN_LOG", log_path)
    mock_pre = _make_mock_pre(sql_schema="CREATE TABLE products (sku TEXT)", agents_md="# AG")

    with patch("agent.orchestrator.PcmRuntimeClientSync"), \
         patch("agent.orchestrator.run_prephase", return_value=mock_pre):
        orch.run_agent({}, "http://test", "task text here", task_id="t42")

    assert log_path.exists()
    entry = json.loads(log_path.read_text().strip())
    assert entry["task_id"] == "t42"
    assert entry["task_text"] == "task text here"
    assert entry["sql_schema"] == "CREATE TABLE products (sku TEXT)"
    assert entry["agents_md"] == "# AG"
    assert "timestamp" in entry


def test_normal_mode_calls_loop(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "0")
    monkeypatch.setenv("MODEL", "test-model")

    import importlib
    import agent.orchestrator as orch
    importlib.reload(orch)

    mock_pre = _make_mock_pre()
    mock_stats = {"input_tokens": 10, "output_tokens": 5}

    with patch("agent.orchestrator.PcmRuntimeClientSync"), \
         patch("agent.orchestrator.run_prephase", return_value=mock_pre), \
         patch("agent.orchestrator.run_loop", return_value=mock_stats) as mock_loop:
        orch.run_agent({}, "http://test", "normal task")

    mock_loop.assert_called_once()


def test_few_shot_user_is_sql_task():
    from agent.prephase import _FEW_SHOT_USER
    assert "lawn mower" in _FEW_SHOT_USER.lower() or "catalogue" in _FEW_SHOT_USER.lower()
    assert "notes" not in _FEW_SHOT_USER.lower(), "few-shot must not reference notes folder"


def test_few_shot_assistant_uses_sql_exec():
    from agent.prephase import _FEW_SHOT_ASSISTANT
    assert '"tool":"exec"' in _FEW_SHOT_ASSISTANT.replace(" ", "")
    assert "/bin/sql" in _FEW_SHOT_ASSISTANT
    assert "EXPLAIN" in _FEW_SHOT_ASSISTANT
    assert "list" not in _FEW_SHOT_ASSISTANT.lower().split('"tool"')[0]


def test_prephase_result_has_sql_schema_field():
    from agent.prephase import PrephaseResult
    r = PrephaseResult(log=[], preserve_prefix=[])
    assert hasattr(r, "sql_schema")
    assert r.sql_schema == ""


def test_system_prompt_has_catalogue_strategy_section():
    from agent.prompt import SYSTEM_PROMPT
    assert "## CATALOGUE STRATEGY" in SYSTEM_PROMPT


def test_catalogue_strategy_has_hard_rule():
    from agent.prompt import SYSTEM_PROMPT
    assert "list" in SYSTEM_PROMPT and "/proc/catalog" in SYSTEM_PROMPT
    # Hard rule: no list/find/read on /proc/catalog
    idx = SYSTEM_PROMPT.find("## CATALOGUE STRATEGY")
    assert idx != -1
    section = SYSTEM_PROMPT[idx:]
    assert "HARD RULE" in section or "Never use" in section


def test_catalogue_strategy_has_step_order():
    from agent.prompt import SYSTEM_PROMPT
    idx = SYSTEM_PROMPT.find("## CATALOGUE STRATEGY")
    section = SYSTEM_PROMPT[idx:]
    assert "EXPLAIN" in section
    assert "DISTINCT" in section


def test_catalogue_strategy_has_question_patterns():
    from agent.prompt import SYSTEM_PROMPT
    idx = SYSTEM_PROMPT.find("## CATALOGUE STRATEGY")
    section = SYSTEM_PROMPT[idx:]
    assert "COUNT(*)" in section
    assert "LIMIT 1" in section


def test_model_env_var_name_is_MODEL():
    """main.py must read MODEL, not MODEL_DEFAULT."""
    import ast
    from pathlib import Path
    root = Path(__file__).parent.parent
    src = (root / "main.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == "MODEL_DEFAULT":
            raise AssertionError("main.py still references MODEL_DEFAULT literal")
