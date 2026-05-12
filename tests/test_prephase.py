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
    assert fields == {"log", "preserve_prefix", "agents_md_content", "agents_md_path",
                      "db_schema"}


def test_normal_mode_reads_only_agents_md():
    """Normal mode: exactly 1 vm.read call (AGENTS.MD)."""
    vm = _make_vm()
    result = run_prephase(vm, "find products", "sys prompt")
    assert vm.read.call_count == 1
    assert result.agents_md_content == "AGENTS CONTENT"


def test_normal_mode_log_structure():
    """Log has system + prephase user."""
    vm = _make_vm()
    result = run_prephase(vm, "find products", "sys prompt")
    assert result.log[0]["role"] == "system"
    assert result.log[1]["role"] == "user"
    assert "find products" in result.log[1]["content"]
    assert "AGENTS CONTENT" in result.log[1]["content"]


def test_normal_mode_no_tree_no_context():
    """vm.tree and vm.context are never called."""
    vm = _make_vm()
    run_prephase(vm, "task", "sys")
    assert vm.tree.call_count == 0
    assert vm.context.call_count == 0


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


def test_prephase_result_has_db_schema_field():
    """PrephaseResult now has db_schema field."""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(PrephaseResult)}
    assert "db_schema" in fields


def test_normal_mode_reads_schema():
    """Normal mode still calls vm.exec for schema."""
    vm = MagicMock()
    agents_r = MagicMock(); agents_r.content = "AGENTS CONTENT"
    exec_r = MagicMock(); exec_r.stdout = "CREATE TABLE products ..."
    vm.read.return_value = agents_r
    vm.exec.return_value = exec_r
    result = run_prephase(vm, "find products", "sys prompt")
    assert vm.exec.call_count == 1
    assert result.db_schema == "CREATE TABLE products ..."


def test_schema_exec_fail_sets_empty_db_schema():
    """vm.exec exception → db_schema is empty string, no crash."""
    vm = MagicMock()
    agents_r = MagicMock(); agents_r.content = "AGENTS"
    vm.read.return_value = agents_r
    vm.exec.side_effect = Exception("exec failed")
    result = run_prephase(vm, "task", "sys")
    assert result.db_schema == ""


def test_schema_not_in_log():
    """db_schema content must NOT appear in LLM log messages."""
    vm = MagicMock()
    agents_r = MagicMock(); agents_r.content = "AGENTS"
    exec_r = MagicMock(); exec_r.stdout = "UNIQUE_SCHEMA_MARKER_XYZ"
    vm.read.return_value = agents_r
    vm.exec.return_value = exec_r
    result = run_prephase(vm, "task", "sys")
    for msg in result.log:
        assert "UNIQUE_SCHEMA_MARKER_XYZ" not in msg.get("content", "")


def test_no_few_shot_in_log():
    """prephase log must not contain the NextStep few-shot pair."""
    import agent.prephase as p
    assert not hasattr(p, "_FEW_SHOT_USER"), "_FEW_SHOT_USER should be removed"
    assert not hasattr(p, "_FEW_SHOT_ASSISTANT"), "_FEW_SHOT_ASSISTANT should be removed"
