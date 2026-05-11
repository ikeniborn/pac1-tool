"""Tests for SQL-first few-shot and prephase sql_schema field."""


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
