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
