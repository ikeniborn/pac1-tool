"""Resolve phase: confirm task identifiers against DB before pipeline cycles."""
from __future__ import annotations

import re

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync
from bitgn.vm.ecom.ecom_pb2 import ExecRequest
from google.protobuf.json_format import MessageToDict

from .json_extract import _extract_json_from_text
from .llm import call_llm_raw
from .models import ResolveOutput
from .prephase import PrephaseResult
from .prompt import load_prompt

_DDL_RE = re.compile(r"^\s*(DROP|INSERT|UPDATE|DELETE|ALTER|CREATE|REPLACE)\b", re.IGNORECASE)
_DISCOVERY_RE = re.compile(r"\b(ILIKE|DISTINCT)\b", re.IGNORECASE)


def _security_check(query: str) -> str | None:
    if _DDL_RE.match(query):
        return f"DDL/DML not allowed in resolve: {query[:60]}"
    if not _DISCOVERY_RE.search(query):
        return f"resolve query must contain ILIKE or DISTINCT: {query[:60]}"
    return None


def _exec_sql(vm: EcomRuntimeClientSync, query: str) -> str:
    result = vm.exec(ExecRequest(path="/bin/sql", args=[query]))
    try:
        d = MessageToDict(result)
        txt = d.get("stdout", "") or d.get("output", "") or ""
        if txt:
            return txt
    except Exception:
        pass
    return getattr(result, "stdout", "") or getattr(result, "output", "") or ""


def _first_value(csv_text: str) -> str | None:
    lines = [ln.strip() for ln in csv_text.strip().splitlines() if ln.strip()]
    if len(lines) < 2:
        return None
    parts = lines[1].split(",")
    return parts[0].strip().strip('"') if parts else None


def _build_resolve_system(pre: PrephaseResult) -> str:
    parts: list[str] = []
    if pre.agents_md_index:
        index_lines = "\n".join(f"- {k}" for k in pre.agents_md_index)
        parts.append(f"# AGENTS.MD INDEX\n{index_lines}")
    top_keys = pre.schema_digest.get("top_keys", [])
    if top_keys:
        parts.append("# TOP PROPERTY KEYS\n" + "\n".join(f"- {k}" for k in top_keys))
    guide = load_prompt("resolve")
    if guide:
        parts.append(guide)
    return "\n\n".join(parts)


def run_resolve(
    vm: EcomRuntimeClientSync,
    model: str,
    task_text: str,
    pre: PrephaseResult,
    cfg: dict,
) -> dict:
    """Resolve identifiers in task_text against DB. Returns confirmed_values or {} on failure."""
    try:
        return _run(vm, model, task_text, pre, cfg)
    except Exception as e:
        print(f"[resolve] non-fatal error: {e}")
        return {}


def _run(
    vm: EcomRuntimeClientSync,
    model: str,
    task_text: str,
    pre: PrephaseResult,
    cfg: dict,
) -> dict:
    system = _build_resolve_system(pre)
    raw = call_llm_raw(system, f"TASK: {task_text}", model, cfg, max_tokens=1024)
    if not raw:
        return {}

    parsed = _extract_json_from_text(raw)
    if not isinstance(parsed, dict):
        return {}

    try:
        resolve_out = ResolveOutput.model_validate(parsed)
    except Exception:
        return {}

    confirmed_values: dict[str, list[str]] = {}

    for candidate in resolve_out.candidates:
        err = _security_check(candidate.discovery_query)
        if err:
            print(f"[resolve] security blocked: {err}")
            continue

        result_txt = _exec_sql(vm, candidate.discovery_query)
        value = _first_value(result_txt)
        if value:
            field = candidate.field
            if field not in confirmed_values:
                confirmed_values[field] = []
            if value not in confirmed_values[field]:
                confirmed_values[field].append(value)

    return confirmed_values
