def test_passing_assert():
    from agent.test_runner import run_tests
    code = "def test_sql(results):\n    assert results == ['row1']\n"
    passed, err, _ = run_tests(code, "test_sql", {"results": ["row1"]})
    assert passed is True
    assert err == ""


def test_failing_assert():
    from agent.test_runner import run_tests
    code = "def test_sql(results):\n    assert len(results) > 0\n"
    passed, err, _ = run_tests(code, "test_sql", {"results": []})
    assert passed is False
    assert err  # non-empty AssertionError message


def test_syntax_error_in_test_code():
    from agent.test_runner import run_tests
    code = "def test_sql(results):\n    assert len(results > 0\n"  # missing closing paren
    passed, err, _ = run_tests(code, "test_sql", {"results": [1]})
    assert passed is False
    assert err  # non-empty


def test_timeout():
    from agent.test_runner import run_tests
    code = "import time\ndef test_sql(results):\n    time.sleep(30)\n"
    passed, err, _ = run_tests(code, "test_sql", {"results": []})
    assert passed is False
    assert err == "test timeout"


def test_answer_tests_signature():
    from agent.test_runner import run_tests
    code = (
        "def test_answer(sql_results, answer):\n"
        "    assert answer['outcome'] == 'OUTCOME_OK'\n"
        "    assert answer['message']\n"
    )
    passed, err, _ = run_tests(
        code,
        "test_answer",
        {
            "sql_results": ["id,name\n1,Widget"],
            "answer": {
                "outcome": "OUTCOME_OK",
                "message": "Found 1",
                "grounding_refs": [],
                "reasoning": "",
                "completed_steps": [],
            },
        },
    )
    assert passed is True
    assert err == ""


# ── _check_tdd_antipatterns tests ──────────────────────────────────────────


def test_antipattern_literal_in_answer_warns_when_in_task():
    from agent.test_runner import _check_tdd_antipatterns
    code = "def test_answer(sql_results, answer):\n    assert 'Cordless Drill Driver' in answer['message']\n"
    task = "How many Cordless Drill Driver SKUs are active?"
    warnings = _check_tdd_antipatterns(code, task_text=task)
    assert any("Cordless Drill Driver" in w for w in warnings)


def test_antipattern_literal_not_in_task_no_warn():
    from agent.test_runner import _check_tdd_antipatterns
    code = "def test_answer(sql_results, answer):\n    assert 'Cordless Drill Driver' in answer['message']\n"
    # task does NOT contain the literal
    warnings = _check_tdd_antipatterns(code, task_text="List active SKUs")
    assert not any("Cordless Drill Driver" in w for w in warnings)


def test_antipattern_no_task_text_no_answer_warn():
    from agent.test_runner import _check_tdd_antipatterns
    code = "def test_answer(sql_results, answer):\n    assert 'Cordless Drill Driver' in answer['message']\n"
    # task_text omitted — answer anti-pattern check skipped
    warnings = _check_tdd_antipatterns(code)
    assert not any("Cordless Drill Driver" in w for w in warnings)


def test_antipattern_header_literal_always_warns():
    from agent.test_runner import _check_tdd_antipatterns
    code = "def test_sql(results):\n    header = results[0].split('\\n')[0].lower()\n    assert 'count' in header\n"
    warnings = _check_tdd_antipatterns(code)
    assert any("count" in w for w in warnings)


def test_antipattern_unescaped_opposite_quote_no_warn():
    """False-negative: regex does not match unescaped opposite-quote inside literal. Acceptable for MVP."""
    from agent.test_runner import _check_tdd_antipatterns
    # "Bob's Drill" — embedded apostrophe inside double-quoted string
    code = "def test_answer(sql_results, answer):\n    assert \"Bob's Drill\" in answer['message']\n"
    task = "Find Bob's Drill products"
    warnings = _check_tdd_antipatterns(code, task_text=task)
    # regex stops on the embedded ' — no match, no warning (documented false-negative)
    assert not warnings


def test_aggregate_antipattern_force_fail():
    from agent.test_runner import run_tests
    code = (
        "def test_sql(results):\n"
        "    rows = results[-1].split('\\n')\n"
        "    assert len(rows) > 1\n"
    )
    sql_queries = ["SELECT COUNT(*) FROM products WHERE kind_id = 7"]
    passed, err, warns = run_tests(
        code, "test_sql", {"results": ["count\n3"]},
        task_text="", sql_queries=sql_queries,
    )
    assert passed is False
    assert "antipattern" in err.lower()
    assert any("antipattern" in w.lower() for w in warns)


def test_non_aggregate_len_check_allowed():
    from agent.test_runner import run_tests
    code = (
        "def test_sql(results):\n"
        "    rows = results[-1].split('\\n')\n"
        "    assert len(rows) > 1\n"
    )
    sql_queries = ["SELECT sku FROM products WHERE kind_id = 7"]
    passed, err, warns = run_tests(
        code, "test_sql", {"results": ["sku\nA1\nA2"]},
        task_text="", sql_queries=sql_queries,
    )
    assert passed is True
    assert not any("antipattern" in w.lower() for w in warns)


def test_aggregate_without_bad_len_passes():
    from agent.test_runner import run_tests
    code = (
        "def test_sql(results):\n"
        "    rows = results[-1].split('\\n')\n"
        "    assert int(rows[-1].strip()) >= 0\n"
    )
    sql_queries = ["SELECT COUNT(*) FROM products"]
    passed, err, warns = run_tests(
        code, "test_sql", {"results": ["count\n3"]},
        task_text="", sql_queries=sql_queries,
    )
    assert passed is True
