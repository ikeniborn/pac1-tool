"""Subprocess test runner for TDD pipeline."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run_tests(test_code: str, fn_name: str, context: dict) -> tuple[bool, str]:
    """Run test_code in isolated subprocess. Returns (passed, error_message)."""
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
            return True, ""
        error = (result.stderr or result.stdout or "non-zero exit").strip()
        return False, error[:500]
    except subprocess.TimeoutExpired:
        return False, "test timeout"
    except Exception as e:
        return False, str(e)[:500]
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
