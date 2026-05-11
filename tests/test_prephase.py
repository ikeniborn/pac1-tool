import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from agent.prephase import run_prephase, PrephaseResult


def _make_vm(agents_md="AGENTS CONTENT", bin_sql="SQL CONTENT"):
    vm = MagicMock()
    agents_r = MagicMock(); agents_r.content = agents_md
    bin_r = MagicMock(); bin_r.content = bin_sql
    def _read(req):
        if req.path in ("/AGENTS.MD", "/AGENTS.md"):
            return agents_r
        if req.path == "/bin/sql":
            return bin_r
        raise Exception(f"unexpected read: {req.path}")
    vm.read.side_effect = _read
    return vm


def test_prephase_result_fields():
    """PrephaseResult has exactly the expected fields."""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(PrephaseResult)}
    assert fields == {"log", "preserve_prefix", "agents_md_content", "agents_md_path", "bin_sql_content"}


def test_normal_mode_reads_only_agents_md():
    """Normal mode: exactly 1 vm.read call (AGENTS.MD)."""
    vm = _make_vm()
    result = run_prephase(vm, "find products", "sys prompt")
    assert vm.read.call_count == 1
    assert result.agents_md_content == "AGENTS CONTENT"
    assert result.bin_sql_content == ""


def test_normal_mode_log_structure():
    """Log has system + few-shot user + few-shot assistant + prephase user."""
    vm = _make_vm()
    result = run_prephase(vm, "find products", "sys prompt")
    assert result.log[0]["role"] == "system"
    assert result.log[1]["role"] == "user"
    assert result.log[2]["role"] == "assistant"
    assert result.log[3]["role"] == "user"
    assert "find products" in result.log[3]["content"]
    assert "AGENTS CONTENT" in result.log[3]["content"]


def test_normal_mode_no_tree_no_context():
    """vm.tree and vm.context are never called."""
    vm = _make_vm()
    run_prephase(vm, "task", "sys")
    assert vm.tree.call_count == 0
    assert vm.context.call_count == 0


def test_dry_run_reads_bin_sql():
    """dry_run=True: 2 vm.read calls, bin_sql_content populated."""
    vm = _make_vm()
    result = run_prephase(vm, "task", "sys", dry_run=True)
    assert vm.read.call_count == 2
    assert result.bin_sql_content == "SQL CONTENT"


def test_dry_run_bin_sql_not_in_log():
    """bin_sql content must NOT appear in LLM log messages."""
    vm = _make_vm(bin_sql="UNIQUE_BIN_SQL_MARKER")
    result = run_prephase(vm, "task", "sys", dry_run=True)
    for msg in result.log:
        assert "UNIQUE_BIN_SQL_MARKER" not in msg.get("content", "")


def test_agents_md_not_found():
    """If AGENTS.MD missing, agents_md_content is empty, no crash."""
    vm = MagicMock()
    vm.read.side_effect = Exception("not found")
    result = run_prephase(vm, "task", "sys")
    assert result.agents_md_content == ""
    assert result.agents_md_path == ""


def test_preserve_prefix_equals_log():
    """preserve_prefix is a copy of log at return time."""
    vm = _make_vm()
    result = run_prephase(vm, "task", "sys")
    assert result.preserve_prefix == result.log


def test_write_dry_run_format():
    """_write_dry_run writes correct JSON fields to jsonl."""
    from agent.orchestrator import _write_dry_run, _DRY_RUN_LOG
    pre = PrephaseResult(log=[], preserve_prefix=[], agents_md_content="AGENTS", bin_sql_content="SQL")
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "dry_run_analysis.jsonl"
        with patch("agent.orchestrator._DRY_RUN_LOG", log_path):
            _write_dry_run("t01", "find products", pre)
        line = json.loads(log_path.read_text().strip())
    assert line["task_id"] == "t01"
    assert line["task"] == "find products"
    assert line["agents_md"] == "AGENTS"
    assert line["bin_sql_content"] == "SQL"
    assert "sql_schema" not in line
