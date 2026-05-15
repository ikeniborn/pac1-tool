"""Subprocess test runner for TDD pipeline."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Regex: (?:[^'"\\]|\\.)* handles basic escape sequences (e.g. \', \").
# Known edge cases (acceptable for MVP):
#   False-negative: unescaped embedded opposite-quote inside string — e.g. assert "Bob's Drill" in answer[...]
#                   The [^'"\\] class stops on the embedded quote; regex fails to match.
#   False-positive: mismatched delimiters — e.g. assert 'foo" in answer[...]
#                   Acceptable since LLM-generated test code is expected to be syntactically valid.
_ANSWER_ASSERT_RE = re.compile(r"""assert\s+['"]((?:[^'"\\]|\\.)*)['"]\s+in\s+answer\[""")
# _HEADER_ASSERT_RE matches `assert '<literal>' in header` only — not `in header[0]`, `in headers`,
# or any compound name.
# Known edge case (acceptable for MVP):
#   False-positive: non-aggregate column names (e.g. `sku`, `path`) also match and emit a warning.
_HEADER_ASSERT_RE = re.compile(r"""assert\s+['"]((?:[^'"\\]|\\.)*)['"]\s+in\s+header""")
_AGG_RE = re.compile(r"\b(COUNT|SUM|AVG|MIN|MAX)\s*\(", re.IGNORECASE)
_BAD_LEN_RE = re.compile(r"len\s*\(\s*(?:rows|results)\s*\)\s*>\s*1")


def _check_tdd_antipatterns(
    test_code: str,
    task_text: str = "",
    sql_queries: list[str] | None = None,
) -> list[str]:
    warnings = []
    if task_text:
        for lit in _ANSWER_ASSERT_RE.findall(test_code):
            if lit in task_text:
                warnings.append(f"hardcoded task literal in answer assert: '{lit}'")
    for col in _HEADER_ASSERT_RE.findall(test_code):
        warnings.append(
            f"hardcoded string in sql header assert: '{col}' — "
            "for aggregates use row/type check; for named columns this warning may be a false-positive"
        )
    if sql_queries and _BAD_LEN_RE.search(test_code):
        if any(_AGG_RE.search(q) for q in sql_queries):
            warnings.append(
                "aggregate query + len > 1 antipattern — use rows == 1 + integer parse"
            )
    return warnings


def run_tests(
    test_code: str,
    fn_name: str,
    context: dict,
    task_text: str = "",
    sql_queries: list[str] | None = None,
) -> tuple[bool, str, list[str]]:
    """Run test_code in isolated subprocess. Returns (passed, error_message, warnings)."""
    warnings = _check_tdd_antipatterns(test_code, task_text, sql_queries)
    for w in warnings:
        if "antipattern" in w.lower():
            return False, w, warnings
    script = (
        "import json, sys\n"
        "context = json.loads(sys.stdin.read())\n"
        + test_code + "\n"
        + fn_name + "(**context)\n"
    )
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script)
            tmp_path = f.name
        result = subprocess.run(
            [sys.executable, tmp_path],
            input=json.dumps(context),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, "", warnings
        error = (result.stderr or result.stdout or "non-zero exit").strip()
        return False, error[:2000], warnings
    except subprocess.TimeoutExpired:
        return False, "test timeout", warnings
    except Exception as e:
        return False, str(e)[:2000], warnings
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
