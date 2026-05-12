from unittest.mock import MagicMock
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
    assert fields == {
        "log", "preserve_prefix", "agents_md_content", "agents_md_path",
        "db_schema", "agents_md_index", "schema_digest",
    }


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
    """Normal mode calls vm.exec for schema and digest queries."""
    vm = MagicMock()
    agents_r = MagicMock(); agents_r.content = "AGENTS CONTENT"
    exec_r = MagicMock(); exec_r.stdout = "CREATE TABLE products ..."
    vm.read.return_value = agents_r
    vm.exec.return_value = exec_r
    result = run_prephase(vm, "find products", "sys prompt")
    # Called for .schema + PRAGMA table_info (4 tables) + PRAGMA foreign_key_list (4) + SELECT key
    assert vm.exec.call_count >= 1
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


def _make_vm_with_schema(agents_md="## Brand Aliases\nheco = Heco", schema="CREATE TABLE products"):
    """VM mock that handles read (AGENTS.MD) and exec (.schema + PRAGMA + SELECT)."""
    vm = MagicMock()
    agents_r = MagicMock()
    agents_r.content = agents_md

    def _read(req):
        if req.path in ("/AGENTS.MD", "/AGENTS.md"):
            return agents_r
        raise Exception(f"unexpected read: {req.path}")

    def _exec(req):
        r = MagicMock()
        r.stdout = ""
        if req.args and req.args[0] == ".schema":
            r.stdout = schema
        elif req.args and "PRAGMA" in req.args[0]:
            r.stdout = "cid,name,type,notnull,dflt_value,pk\n0,sku,TEXT,1,,1\n1,brand,TEXT,0,,0"
        elif req.args and "product_properties" in req.args[0] and "COUNT" in req.args[0]:
            r.stdout = "key,cnt,text_cnt,num_cnt\ndiameter_mm,100,0,100\nscrew_type,80,80,0"
        elif req.args and "foreign_key_list" in req.args[0]:
            r.stdout = ""
        return r

    vm.read.side_effect = _read
    vm.exec.side_effect = _exec
    return vm


def test_prephase_result_fields_updated():
    """PrephaseResult has agents_md_index and schema_digest fields."""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(PrephaseResult)}
    assert "agents_md_index" in fields
    assert "schema_digest" in fields


def test_agents_md_index_populated():
    """agents_md_index has parsed sections from AGENTS.MD."""
    vm = _make_vm_with_schema()
    result = run_prephase(vm, "find Heco screws", "sys")
    assert "brand_aliases" in result.agents_md_index
    assert result.agents_md_index["brand_aliases"] == ["heco = Heco"]


def test_agents_md_index_empty_when_no_agents_md():
    """agents_md_index is empty dict if AGENTS.MD not found."""
    vm = MagicMock()
    vm.read.side_effect = Exception("not found")
    exec_r = MagicMock(); exec_r.stdout = ""
    vm.exec.return_value = exec_r
    result = run_prephase(vm, "task", "sys")
    assert result.agents_md_index == {}


def test_schema_digest_has_tables():
    """schema_digest['tables'] has product-related tables."""
    vm = _make_vm_with_schema()
    result = run_prephase(vm, "task", "sys")
    assert "tables" in result.schema_digest
    assert "products" in result.schema_digest["tables"]


def test_schema_digest_has_top_keys():
    """schema_digest['top_keys'] lists top property keys."""
    vm = _make_vm_with_schema()
    result = run_prephase(vm, "task", "sys")
    assert "top_keys" in result.schema_digest
    assert "diameter_mm" in result.schema_digest["top_keys"]


def test_schema_digest_value_type_map():
    """schema_digest['value_type_map'] maps key to text/number."""
    vm = _make_vm_with_schema()
    result = run_prephase(vm, "task", "sys")
    vt = result.schema_digest.get("value_type_map", {})
    assert vt.get("diameter_mm") == "number"
    assert vt.get("screw_type") == "text"


def test_schema_digest_empty_on_exec_failure():
    """schema_digest is empty dict if all exec calls fail."""
    vm = MagicMock()
    agents_r = MagicMock(); agents_r.content = "## Brand Aliases\nheco = Heco"
    vm.read.return_value = agents_r
    vm.exec.side_effect = Exception("exec failed")
    result = run_prephase(vm, "task", "sys")
    assert result.schema_digest == {}
