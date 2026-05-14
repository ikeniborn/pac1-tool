import json
import threading
from unittest.mock import MagicMock, patch, call
import pytest
from agent.pipeline import run_pipeline, _extract_discovery_results, _format_confirmed_values, _format_schema_digest
from agent.prephase import PrephaseResult
from pathlib import Path


def _make_pre(agents_md="AGENTS", db_schema="CREATE TABLE products(id INT, type TEXT, brand TEXT, sku TEXT, model TEXT)"):
    return PrephaseResult(
        agents_md_content=agents_md,
        agents_md_path="/AGENTS.MD",
        db_schema=db_schema,
    )


def _sql_plan_json(queries=None):
    return json.dumps({
        "reasoning": "products table has type column",
        "queries": queries or ["SELECT COUNT(*) FROM products WHERE type='Lawn Mower'"],
    })


def _answer_json(outcome="OUTCOME_OK", message="<YES> 3 found"):
    return json.dumps({
        "reasoning": "SQL returned 3 rows",
        "message": message,
        "outcome": outcome,
        "grounding_refs": ["/proc/catalog/ABC-001.json"],
        "completed_steps": ["ran SQL", "found products"],
    })


def _make_exec_result(stdout="[{\"count\":3}]"):
    r = MagicMock()
    r.stdout = stdout
    return r


def test_happy_path(tmp_path):
    """SQL_PLAN → VALIDATE ok → EXECUTE ok → ANSWER ok."""
    vm = MagicMock()
    # VALIDATE (EXPLAIN) returns no error
    # EXECUTE returns rows
    vm.exec.return_value = _make_exec_result('[{"count": 3}]')

    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    call_seq = [_sql_plan_json(), _answer_json()]
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None):
        stats, _thread = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "How many Lawn Mowers?", pre, {})

    assert stats["outcome"] == "OUTCOME_OK"
    vm.answer.assert_called_once()
    answer_req = vm.answer.call_args[0][0]
    assert answer_req.message == "<YES> 3 found"


def test_validate_error_triggers_learn_and_retry(tmp_path):
    """EXPLAIN returns error → LEARN called → SQL_PLAN retried → success."""
    vm = MagicMock()
    vm.exec.side_effect = [
        _make_exec_result("Error: no such table: produts"),
        _make_exec_result(""),
        _make_exec_result('[{"count": 1}]'),
    ]

    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    learn_json = json.dumps({
        "reasoning": "typo in table name",
        "conclusion": "Table is 'products' not 'produts'",
        "rule_content": "Always spell table name as 'products'.",
    })

    call_seq = [_sql_plan_json(["SELECT COUNT(*) FROM produts WHERE type='X'"]),
                learn_json,
                _sql_plan_json(),
                _answer_json()]
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None):
        stats, _thread = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "How many?", pre, {})

    assert stats["outcome"] == "OUTCOME_OK"


def test_max_cycles_exhausted_returns_clarification(tmp_path):
    """3 cycles all fail → OUTCOME_NONE_CLARIFICATION without ANSWER LLM call."""
    vm = MagicMock()
    vm.exec.return_value = _make_exec_result("Error: syntax error")

    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    learn_json = json.dumps({
        "reasoning": "x", "conclusion": "y", "rule_content": "z",
    })
    call_seq = [_sql_plan_json(), learn_json] * 3
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None), \
         patch("agent.pipeline._MAX_CYCLES", 3):
        stats, _thread = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "?", pre, {})

    assert stats["outcome"] == "OUTCOME_NONE_CLARIFICATION"
    vm.answer.assert_called_once()


def test_security_gate_ddl_triggers_learn(tmp_path):
    """DDL query → security gate blocks → LEARN → retry → success."""
    vm = MagicMock()
    vm.exec.side_effect = [
        _make_exec_result(""),
        _make_exec_result('[{"id": 1}]'),
    ]

    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    ddl_gate = [{"id": "sec-001", "pattern": "^\\s*(DROP|INSERT|UPDATE|DELETE|ALTER|CREATE)",
                 "action": "block", "message": "DDL/DML prohibited"}]

    learn_json = json.dumps({
        "reasoning": "used DROP", "conclusion": "only SELECT allowed",
        "rule_content": "Never use DDL statements.",
    })
    call_seq = [
        _sql_plan_json(["DROP TABLE products"]),
        learn_json,
        _sql_plan_json(),
        _answer_json(),
    ]
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=ddl_gate), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None):
        stats, _thread = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "drop test", pre, {})

    assert stats["outcome"] == "OUTCOME_OK"


def test_learn_does_not_persist_auto_rule(tmp_path):
    """LEARN updates session_rules but does not write rule files (append_rule removed)."""
    vm = MagicMock()
    vm.exec.side_effect = [
        _make_exec_result("Error: syntax error"),
        _make_exec_result(""),
        _make_exec_result('[{"count": 1}]'),
    ]
    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    learn_json = json.dumps({
        "reasoning": "x", "conclusion": "y", "rule_content": "Never do X.",
    })
    call_seq = [_sql_plan_json(), learn_json, _sql_plan_json(), _answer_json()]
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None):
        stats, _thread = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "count X", pre, {})

    assert stats["outcome"] == "OUTCOME_OK"
    # append_rule has been removed — no auto YAML files should be written
    assert not hasattr(__import__("agent.rules_loader", fromlist=["RulesLoader"]).RulesLoader, "append_rule")
    written_files = list(rules_dir.glob("*.yaml"))
    assert written_files == [], f"No rule files should be written, found: {written_files}"


def test_extract_discovery_results_basic():
    queries = ["SELECT DISTINCT brand FROM products WHERE brand ILIKE '%heco%' LIMIT 10"]
    results = ["brand\nHeco\nMaker"]
    cv: dict = {}
    _extract_discovery_results(queries, results, cv)
    assert cv.get("brand") == ["Heco", "Maker"]


def test_extract_discovery_results_skips_non_distinct():
    queries = ["SELECT sku FROM products WHERE brand = 'Heco'"]
    results = ["sku\nABC-001"]
    cv: dict = {}
    _extract_discovery_results(queries, results, cv)
    assert cv == {}


def test_extract_discovery_results_accumulates():
    cv = {"brand": ["Heco"]}
    queries = ["SELECT DISTINCT brand FROM products WHERE brand ILIKE '%maker%' LIMIT 10"]
    results = ["brand\nMaker"]
    _extract_discovery_results(queries, results, cv)
    assert cv["brand"] == ["Heco", "Maker"]


def test_extract_discovery_results_no_duplicates():
    cv = {"brand": ["Heco"]}
    queries = ["SELECT DISTINCT brand FROM products WHERE brand ILIKE '%heco%' LIMIT 10"]
    results = ["brand\nHeco"]
    _extract_discovery_results(queries, results, cv)
    assert cv["brand"] == ["Heco"]


def test_format_confirmed_values_single():
    cv = {"brand": ["Heco"]}
    text = _format_confirmed_values(cv)
    assert 'brand → confirmed: "Heco"' in text


def test_format_confirmed_values_multiple():
    cv = {"kind": ["wood screw", "self-tapping screw"]}
    text = _format_confirmed_values(cv)
    assert "wood screw" in text
    assert "self-tapping screw" in text


def test_format_schema_digest_lists_tables():
    digest = {
        "tables": {
            "products": {"columns": [{"name": "sku", "type": "TEXT"}, {"name": "brand", "type": "TEXT"}]}
        },
        "top_keys": ["diameter_mm"],
    }
    text = _format_schema_digest(digest)
    assert "products" in text
    assert "sku" in text
    assert "diameter_mm" in text


def test_call_llm_phase_returns_three_tuple(tmp_path):
    """_call_llm_phase returns (obj, sgr, tok) — tok has input/output keys."""
    from agent.pipeline import _call_llm_phase
    from agent.models import SqlPlanOutput

    raw = json.dumps({
        "reasoning": "ok",
        "queries": ["SELECT 1"],
    })

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: (
        kw.get("token_out", {}).update({"input": 42, "output": 7}) or raw
    )):
        obj, sgr, tok = _call_llm_phase("sys", "user", "model", {}, SqlPlanOutput)

    assert obj is not None
    assert tok.get("input") == 42
    assert tok.get("output") == 7


def test_learn_llm_fail_does_not_add_session_rule(tmp_path):
    """_run_learn with error_type='llm_fail' must not add to session_rules."""
    from agent.pipeline import _run_learn

    learn_json = json.dumps({"reasoning": "x", "conclusion": "y", "rule_content": "should not appear"})
    session_rules: list[str] = []
    sgr_trace: list[dict] = []

    with patch("agent.pipeline.call_llm_raw", return_value=learn_json):
        _run_learn(
            "system prompt",
            "model", {}, "task", [], "llm error",
            sgr_trace, session_rules, [], {},
            error_type="llm_fail",
        )

    assert session_rules == [], f"session_rules should be empty, got: {session_rules}"


def test_sgr_learn_entry_has_error_type(tmp_path):
    """LEARN sgr_trace entry must contain 'error_type' field."""
    from agent.pipeline import _run_learn

    learn_json = json.dumps({"reasoning": "x", "conclusion": "y", "rule_content": "rule"})
    session_rules: list[str] = []
    sgr_trace: list[dict] = []

    with patch("agent.pipeline.call_llm_raw", return_value=learn_json):
        _run_learn(
            "system prompt",
            "model", {}, "task", ["SELECT 1"], "syntax error",
            sgr_trace, session_rules, [], {},
            error_type="syntax",
        )

    assert len(sgr_trace) == 1
    assert sgr_trace[0].get("error_type") == "syntax", f"sgr_trace entry: {sgr_trace[0]}"


def test_session_rules_accumulate_all_learn(tmp_path):
    """session_rules accumulates all LEARN rules — no truncation cap."""
    from agent.pipeline import _run_learn

    session_rules: list[str] = []
    sgr_trace: list[dict] = []

    call_count = [0]
    def _fake_llm(*a, **kw):
        call_count[0] += 1
        if kw.get("token_out") is not None:
            kw["token_out"]["input"] = 1
            kw["token_out"]["output"] = 1
        return json.dumps({"reasoning": "x", "conclusion": "y", "rule_content": f"rule-{call_count[0]}"})

    with patch("agent.pipeline.call_llm_raw", side_effect=_fake_llm):
        for i in range(5):
            _run_learn("system prompt", "model", {}, "task", ["SELECT 1"], f"err-{i}",
                       sgr_trace, session_rules, [], {},
                       error_type="syntax")

    assert len(session_rules) == 5, f"session_rules has {len(session_rules)} entries: {session_rules}"
    assert session_rules[-1] == "rule-5", f"last rule wrong: {session_rules}"


def test_build_static_system_sql_plan_has_security_gates(tmp_path):
    """_build_static_system('sql_plan') includes security gates; 'learn' does not."""
    from agent.pipeline import _build_static_system
    from agent.rules_loader import RulesLoader

    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    rl = RulesLoader(rules_dir)
    gates = [{"id": "sec-001", "message": "no DDL"}]

    sql_blocks = _build_static_system("sql_plan", "AGENTS", {}, "SCHEMA", {}, rl, gates)
    learn_blocks = _build_static_system("learn", "AGENTS", {}, "SCHEMA", {}, rl, gates)

    sql_text = " ".join(b.get("text", "") for b in sql_blocks)
    learn_text = " ".join(b.get("text", "") for b in learn_blocks)

    assert "sec-001" in sql_text, "sql_plan must include security gates"
    assert "sec-001" not in learn_text, "learn must NOT include security gates"


def test_build_static_system_no_session_rules(tmp_path):
    """_build_static_system does not include IN-SESSION RULE (those go to user_msg)."""
    from agent.pipeline import _build_static_system
    from agent.rules_loader import RulesLoader

    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    rl = RulesLoader(rules_dir)

    blocks = _build_static_system("sql_plan", "AGENTS", {}, "SCHEMA", {}, rl, [])
    combined = " ".join(b.get("text", "") for b in blocks)
    assert "IN-SESSION RULE" not in combined


def test_build_static_system_returns_list_of_blocks(tmp_path):
    """_build_static_system returns list[dict], last block has cache_control."""
    from agent.pipeline import _build_static_system
    from agent.rules_loader import RulesLoader

    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    rl = RulesLoader(rules_dir)

    blocks = _build_static_system("sql_plan", "AGENTS", {}, "SCHEMA", {}, rl, [])

    assert isinstance(blocks, list), f"Expected list, got {type(blocks)}"
    assert all(isinstance(b, dict) for b in blocks)
    last = blocks[-1]
    assert last.get("cache_control") == {"type": "ephemeral"}, \
        f"Last block must have cache_control: {last}"


def test_pipeline_token_counts_nonzero(tmp_path):
    """total_in_tok and total_out_tok are non-zero after successful pipeline run."""
    from unittest.mock import MagicMock, patch

    vm = MagicMock()
    vm.exec.return_value = _make_exec_result('[{"count": 3}]')

    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    call_count = [0]

    def _fake_llm(system, user_msg, model, cfg, max_tokens=4096, token_out=None):
        if token_out is not None:
            token_out["input"] = 100
            token_out["output"] = 20
        call_count[0] += 1
        if call_count[0] == 1:
            return _sql_plan_json()
        return _answer_json()

    with patch("agent.pipeline.call_llm_raw", side_effect=_fake_llm), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]):
        stats, _thread = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "How many Lawn Mowers?", pre, {})

    assert stats["input_tokens"] > 0, f"input_tokens still 0: {stats}"
    assert stats["output_tokens"] > 0, f"output_tokens still 0: {stats}"


def test_run_pipeline_returns_tuple(tmp_path):
    """run_pipeline returns (dict, Thread | None)."""
    vm = MagicMock()
    vm.exec.return_value = _make_exec_result('[{"count": 1}]')

    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    call_seq = [_sql_plan_json(), _answer_json()]
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._rules_loader_cache", None), \
         patch("agent.pipeline._security_gates_cache", None), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline._EVAL_ENABLED", False):
        result = run_pipeline(vm, "model", "task", pre, {})

    assert isinstance(result, tuple) and len(result) == 2, f"expected 2-tuple, got {type(result)}"
    stats, thread = result
    assert isinstance(stats, dict)
    assert thread is None


def test_max_cycles_reads_env(monkeypatch):
    monkeypatch.setenv("MAX_STEPS", "7")
    import importlib
    import agent.pipeline as pipeline_mod
    try:
        importlib.reload(pipeline_mod)
        assert pipeline_mod._MAX_CYCLES == 7
    finally:
        monkeypatch.delenv("MAX_STEPS", raising=False)
        importlib.reload(pipeline_mod)
    assert pipeline_mod._MAX_CYCLES == 3  # default


def test_evaluator_thread_starts_on_failure(tmp_path):
    """Evaluator thread starts even when all cycles fail."""
    vm = MagicMock()
    vm.exec.return_value = _make_exec_result("Error: syntax error")

    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    learn_json = json.dumps({"reasoning": "x", "conclusion": "y", "rule_content": "z"})
    call_seq = ([_sql_plan_json(), learn_json]) * 4
    call_iter = iter(call_seq)

    thread_started = []

    def _fake_evaluator(*args, **kwargs):
        thread_started.append(True)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._rules_loader_cache", None), \
         patch("agent.pipeline._security_gates_cache", None), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline._EVAL_ENABLED", True), \
         patch("agent.pipeline._MODEL_EVALUATOR", "eval-model"), \
         patch("agent.pipeline._run_evaluator_safe", side_effect=_fake_evaluator):
        stats, thread = run_pipeline(vm, "model", "task", pre, {})
        if thread is not None:
            thread.join(timeout=5)

    assert thread_started, "Evaluator must start even on pipeline failure"


def test_answer_fallback_called_when_parse_fails(tmp_path):
    """When AnswerOutput.model_validate fails (invalid outcome), vm.answer is still called.

    Uses side_effect so SQL_PLAN succeeds (call 1) but ANSWER returns invalid JSON (call 2).
    Without the fix: answer_out=None → if answer_out: skipped → vm.answer never called.
    With the fix: else branch → vm.answer(OUTCOME_NONE_CLARIFICATION) called.
    """
    vm = MagicMock()
    # Both EXPLAIN and EXECUTE return sku+path data so pipeline reaches ANSWER
    exec_result = _make_exec_result("sku,path\nSKU-001,/proc/catalog/SKU-001.json\n")
    vm.exec.return_value = exec_result

    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    bad_answer_json = json.dumps({
        "reasoning": "x", "message": "hi",
        "outcome": "OUTCOME_NEED_MORE_DATA",   # invalid — not in AnswerOutput Literal
        "grounding_refs": [], "completed_steps": [],
    })
    # Call 1 → SQL_PLAN succeeds; Call 2 → ANSWER parse fails
    call_seq = [
        _sql_plan_json(queries=["SELECT p.sku, p.path FROM products p WHERE p.type='X'"]),
        bad_answer_json,
    ]
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None):
        run_pipeline(vm, "test-model", "test task", pre, {})

    # vm.answer must have been called despite parse failure
    vm.answer.assert_called_once()
    req = vm.answer.call_args.args[0]   # AnswerRequest positional arg
    assert "Could not synthesize" in req.message


def test_discovery_only_detection_fires_without_all_distinct(tmp_path):
    """Schema query (non-DISTINCT) mixed with DISTINCT batch → discovery-only fires if no sku/path.

    Old code: all_discovery = all(SELECT DISTINCT ...) → False → ANSWER after cycle 1
              call_seq[1] = _sql_plan_json (invalid AnswerOutput) → parse fails → vm.answer not called
    New code: not new_refs and not has_count_result → continue → cycle 2 → sku/path → vm.answer called
    """
    vm = MagicMock()

    def mock_exec(req):
        arg = req.args[0] if req.args else ""
        if arg.startswith("EXPLAIN"):
            return _make_exec_result("")
        if "sqlite_schema" in arg:
            return _make_exec_result("")
        if "DISTINCT" in arg.upper() and "kind_id" in arg:
            return _make_exec_result("kind_id\ntool_boxes\n")
        return _make_exec_result("sku,path\nSKU-001,/proc/catalog/SKU-001.json\n")

    vm.exec.side_effect = mock_exec
    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    # call_seq designed for new code: SQL_PLAN cycle1 → (discovery-only) → SQL_PLAN cycle2 → ANSWER
    # With old code: cycle1 goes directly to ANSWER, consuming call_seq[1] = _sql_plan_json
    # → AnswerOutput.model_validate fails → answer_out=None → vm.answer never called
    call_seq = [
        json.dumps({
            "reasoning": "discover schema then kind_id",
            "queries": [
                "SELECT name, sql FROM sqlite_schema WHERE name = 'kinds'",
                "SELECT DISTINCT kind_id FROM products WHERE kind_id LIKE '%tool%'",
            ],
        }),
        _sql_plan_json(["SELECT p.sku, p.path FROM products p WHERE p.kind_id = 'tool_boxes'"]),
        _answer_json(),
    ]
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None):
        run_pipeline(vm, "test-model", "find tool boxes", pre, {})

    # New code: cycle 2 ran → sku refs found → vm.answer called
    vm.answer.assert_called_once()


def test_session_rules_accumulate_beyond_three(tmp_path):
    """All LEARN rules are kept — no 3-rule truncation cap."""
    from unittest.mock import patch, MagicMock
    import json

    vm = MagicMock()
    vm.exec.return_value = _make_exec_result("Error: syntax error")

    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    # 4 cycles: each produces sql_plan + learn
    learn_jsons = [
        json.dumps({"reasoning": f"r{i}", "conclusion": f"c{i}", "rule_content": f"unique_rule_{i}"})
        for i in range(4)
    ]
    sql_jsons = [_sql_plan_json() for _ in range(4)]
    call_seq = []
    for s, l in zip(sql_jsons, learn_jsons):
        call_seq.extend([s, l])
    call_iter = iter(call_seq)

    captured_session_rules: list[list[str]] = []

    import agent.pipeline as pipeline_mod
    original_run_learn = pipeline_mod._run_learn

    def tracking_run_learn(*args, **kwargs):
        session_rules = args[7] if len(args) > 7 else kwargs.get("session_rules", [])
        original_run_learn(*args, **kwargs)
        captured_session_rules.append(list(session_rules))

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None), \
         patch("agent.pipeline._MAX_CYCLES", 4), \
         patch("agent.pipeline._run_learn", side_effect=tracking_run_learn):
        stats, _ = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "test?", pre, {})

    # After 4th LEARN, all 4 rules must survive (no truncation to 3)
    if captured_session_rules:
        final_rules = captured_session_rules[-1]
        assert len(final_rules) == 4, f"Expected 4 rules (no truncation), got {len(final_rules)}: {final_rules}"


def test_injected_prompt_addendum_appended(tmp_path):
    """When injected_prompt_addendum is non-empty, appends to guide block."""
    from agent.pipeline import _build_static_system
    from agent.rules_loader import RulesLoader
    from unittest.mock import MagicMock

    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    rl = RulesLoader(rules_dir)

    blocks = _build_static_system(
        "sql_plan", "", {}, "", {}, rl, [],
        injected_prompt_addendum="USE indexed columns",
    )
    guide_block = blocks[-1]["text"]
    assert "# INJECTED OPTIMIZATION" in guide_block
    assert "USE indexed columns" in guide_block


def test_no_addendum_no_injection(tmp_path):
    """When injected_prompt_addendum is empty, no injection section."""
    from agent.pipeline import _build_static_system
    from agent.rules_loader import RulesLoader
    from unittest.mock import MagicMock

    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    rl = RulesLoader(rules_dir)

    blocks = _build_static_system(
        "sql_plan", "", {}, "", {}, rl, [],
        injected_prompt_addendum="",
    )
    guide_block = blocks[-1]["text"]
    assert "# INJECTED OPTIMIZATION" not in guide_block


def test_run_pipeline_has_injection_params():
    """run_pipeline signature includes all injection params."""
    import inspect
    sig = inspect.signature(run_pipeline)
    assert "task_id" in sig.parameters
    assert "injected_session_rules" in sig.parameters
    assert "injected_prompt_addendum" in sig.parameters
    assert "injected_security_gates" in sig.parameters


def test_run_evaluator_safe_has_task_id():
    """_run_evaluator_safe accepts task_id param."""
    import inspect
    from agent.pipeline import _run_evaluator_safe
    sig = inspect.signature(_run_evaluator_safe)
    assert "task_id" in sig.parameters


def test_injected_session_rules_prepopulate_session():
    """injected_session_rules start the session_rules list."""
    captured_user_msgs = []

    def fake_call_llm(system, user_msg, model, cfg, **kw):
        captured_user_msgs.append(user_msg)
        return None

    pre = _make_pre()
    vm = MagicMock()
    rl = MagicMock()
    rl.get_rules_markdown.return_value = ""
    with patch("agent.pipeline.call_llm_raw", side_effect=fake_call_llm), \
         patch("agent.pipeline._get_security_gates", return_value=[]), \
         patch("agent.pipeline._get_rules_loader", return_value=rl), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline._EVAL_ENABLED", False):
        run_pipeline(vm, "m", "task text", pre, {},
                     injected_session_rules=["Always use LIMIT 100"])
    assert any("Always use LIMIT 100" in m for m in captured_user_msgs)


def test_build_static_system_agent_context_injected():
    """_build_static_system injects AGENT CONTEXT block for sql_plan phase when agent_id or current_date set."""
    import tempfile
    from pathlib import Path
    from agent.pipeline import _build_static_system
    from agent.rules_loader import RulesLoader

    with tempfile.TemporaryDirectory() as tmp:
        rules_loader = RulesLoader(Path(tmp))
        blocks = _build_static_system(
            "sql_plan",
            agents_md="",
            agents_md_index={},
            db_schema="",
            schema_digest={},
            rules_loader=rules_loader,
            security_gates=[],
            agent_id="cust-99",
            current_date="2026-05-14",
        )

    texts = [b["text"] for b in blocks]
    ctx_block = next((t for t in texts if "# AGENT CONTEXT" in t), None)
    assert ctx_block is not None
    assert "customer_id: cust-99" in ctx_block
    assert "date: 2026-05-14" in ctx_block


def test_build_static_system_agent_context_absent_when_both_empty():
    """No AGENT CONTEXT block when both agent_id and current_date are empty."""
    import tempfile
    from pathlib import Path
    from agent.pipeline import _build_static_system
    from agent.rules_loader import RulesLoader

    with tempfile.TemporaryDirectory() as tmp:
        rules_loader = RulesLoader(Path(tmp))
        blocks = _build_static_system(
            "sql_plan",
            agents_md="",
            agents_md_index={},
            db_schema="",
            schema_digest={},
            rules_loader=rules_loader,
            security_gates=[],
            agent_id="",
            current_date="",
        )

    texts = [b["text"] for b in blocks]
    assert not any(t.startswith("# AGENT CONTEXT\n") for t in texts)


def test_build_static_system_agent_context_absent_for_answer_phase():
    """AGENT CONTEXT block NOT injected for answer phase even if fields set."""
    import tempfile
    from pathlib import Path
    from agent.pipeline import _build_static_system
    from agent.rules_loader import RulesLoader

    with tempfile.TemporaryDirectory() as tmp:
        rules_loader = RulesLoader(Path(tmp))
        blocks = _build_static_system(
            "answer",
            agents_md="",
            agents_md_index={},
            db_schema="",
            schema_digest={},
            rules_loader=rules_loader,
            security_gates=[],
            agent_id="cust-99",
            current_date="2026-05-14",
        )

    texts = [b["text"] for b in blocks]
    assert not any(t.startswith("# AGENT CONTEXT\n") for t in texts)


def test_build_static_system_agent_context_first_block():
    """AGENT CONTEXT block is placed before VAULT RULES (first in blocks list)."""
    import tempfile
    from pathlib import Path
    from agent.pipeline import _build_static_system
    from agent.rules_loader import RulesLoader

    with tempfile.TemporaryDirectory() as tmp:
        rules_loader = RulesLoader(Path(tmp))
        blocks = _build_static_system(
            "sql_plan",
            agents_md="## Brand Aliases\nheco = Heco",
            agents_md_index={"brand_aliases": ["heco = Heco"]},
            db_schema="",
            schema_digest={},
            rules_loader=rules_loader,
            security_gates=[],
            agent_id="cust-1",
            current_date="2026-05-14",
            task_text="find heco products",
        )

    texts = [b["text"] for b in blocks]
    ctx_idx = next(i for i, t in enumerate(texts) if t.startswith("# AGENT CONTEXT\n"))
    vault_idx = next((i for i, t in enumerate(texts) if "# VAULT RULES" in t), len(texts))
    assert ctx_idx < vault_idx
