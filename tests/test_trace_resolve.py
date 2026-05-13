"""Verify resolve.py writes llm_call + resolve_exec trace records."""
import json
from unittest.mock import MagicMock, patch

import pytest

from agent.resolve import run_resolve
from agent.prephase import PrephaseResult
from agent.trace import TraceLogger, set_trace


def _make_pre():
    return PrephaseResult(
        agents_md_content="",
        agents_md_path="/AGENTS.MD",
        db_schema="CREATE TABLE products(brand TEXT)",
    )


def _exec_result(stdout="brand\nHeco\n"):
    r = MagicMock()
    r.stdout = stdout
    return r


def test_resolve_exec_records_written(tmp_path):
    """resolve_exec written for each SQL execution in resolve phase."""
    p = tmp_path / "t01.jsonl"
    t = TraceLogger(p, "t01")
    set_trace(t)

    vm = MagicMock()
    vm.exec.return_value = _exec_result()

    resolve_json = json.dumps({
        "reasoning": "brand name needs confirmation",
        "candidates": [
            {"term": "heco", "field": "brand",
             "discovery_query": "SELECT DISTINCT brand FROM products WHERE brand ILIKE '%heco%'"}
        ]
    })

    with patch("agent.resolve.call_llm_raw", return_value=resolve_json):
        run_resolve(vm, "model", "find Heco speakers", _make_pre(), {})

    t.close()
    set_trace(None)

    records = [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]
    types = [r["type"] for r in records]
    assert "llm_call" in types
    assert "resolve_exec" in types

    llm = next(r for r in records if r["type"] == "llm_call")
    assert llm["phase"] == "resolve"
    assert llm["cycle"] == 0
    assert "duration_ms" in llm

    exec_r = next(r for r in records if r["type"] == "resolve_exec")
    assert "value_extracted" in exec_r
    assert exec_r["value_extracted"] == "Heco"
