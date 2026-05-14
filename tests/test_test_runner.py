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
