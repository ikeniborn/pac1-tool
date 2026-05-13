"""Phase-based SQL pipeline for lookup tasks — replaces run_loop() for task_type='lookup'."""
from __future__ import annotations

import json
import os
import re
import threading
import time
import traceback
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync
from bitgn.vm.ecom.ecom_pb2 import AnswerRequest, ExecRequest

from .llm import (
    call_llm_raw, OUTCOME_BY_NAME,
    CLI_BLUE, CLI_CLR, CLI_GREEN, CLI_RED, CLI_YELLOW,
)
from .json_extract import _extract_json_from_text
from .models import SqlPlanOutput, LearnOutput, AnswerOutput
from .prephase import PrephaseResult
from .prompt import load_prompt
from .resolve import run_resolve
from .rules_loader import RulesLoader, _RULES_DIR
from .schema_gate import check_schema_compliance
from .sql_security import check_sql_queries, load_security_gates
from .trace import get_trace

_MAX_CYCLES = 3
_EVAL_ENABLED = os.environ.get("EVAL_ENABLED", "0") == "1"
_MODEL_EVALUATOR = os.environ.get("MODEL_EVALUATOR", "")
_EVAL_LOG = Path(__file__).parent.parent / "data" / "eval_log.jsonl"

_rules_loader_cache: "RulesLoader | None" = None
_security_gates_cache: "list[dict] | None" = None


def _get_rules_loader() -> RulesLoader:
    global _rules_loader_cache
    if _rules_loader_cache is None:
        _rules_loader_cache = RulesLoader(_RULES_DIR)
    return _rules_loader_cache


def _get_security_gates() -> list[dict]:
    global _security_gates_cache
    if _security_gates_cache is None:
        _security_gates_cache = load_security_gates()
    return _security_gates_cache


def _exec_result_text(result) -> str:
    if isinstance(result, Message):
        try:
            d = MessageToDict(result)
            return d.get("stdout", "") or d.get("output", "") or ""
        except Exception:
            pass
    return getattr(result, "stdout", "") or getattr(result, "output", "") or ""


def _csv_has_data(result_txt: str) -> bool:
    stripped = result_txt.strip()
    if not stripped:
        return False
    if stripped.startswith("["):
        return stripped not in ("[]",)
    if stripped.startswith("{"):
        return stripped not in ("{}",)
    lines = [l for l in stripped.splitlines() if l.strip()]
    return len(lines) > 1


def _call_llm_phase(
    system: "str | list[dict]",
    user_msg: str,
    model: str,
    cfg: dict,
    output_cls,
    max_tokens: int = 4096,
    phase: str = "",
    cycle: int = 0,
) -> tuple[object | None, dict, dict]:
    """SGR LLM call: returns (parsed_output_or_None, sgr_trace_entry, tok_info)."""
    tok_info: dict = {}
    t0 = time.monotonic()
    raw = call_llm_raw(system, user_msg, model, cfg, max_tokens=max_tokens, token_out=tok_info)
    duration_ms = int((time.monotonic() - t0) * 1000)
    phase_name = phase or output_cls.__name__
    _system_preview = system[:300] if isinstance(system, str) else str(system)[:300]
    sgr_entry: dict = {
        "phase": phase_name,
        "guide_prompt": _system_preview,
        "reasoning": "",
        "output": raw or "",
    }
    parsed: dict | None = None
    if raw:
        extracted = _extract_json_from_text(raw)
        if isinstance(extracted, dict):
            parsed = extracted
    if parsed is not None:
        try:
            obj = output_cls.model_validate(parsed)
            sgr_entry["reasoning"] = obj.reasoning
            sgr_entry["output"] = parsed
            if t := get_trace():
                t.log_llm_call(
                    phase=phase_name,
                    cycle=cycle,
                    system=system,
                    user_msg=user_msg,
                    raw_response=raw or "",
                    parsed_output=parsed,
                    tokens_in=tok_info.get("input", 0),
                    tokens_out=tok_info.get("output", 0),
                    duration_ms=duration_ms,
                )
            return obj, sgr_entry, tok_info
        except Exception:
            pass
    if t := get_trace():
        t.log_llm_call(
            phase=phase_name,
            cycle=cycle,
            system=system,
            user_msg=user_msg,
            raw_response=raw or "",
            parsed_output=None,
            tokens_in=tok_info.get("input", 0),
            tokens_out=tok_info.get("output", 0),
            duration_ms=duration_ms,
        )
    return None, sgr_entry, tok_info


def _gates_summary(gates: list[dict]) -> str:
    return "\n".join(f"- [{g['id']}] {g.get('message', '')}" for g in gates)


def _format_confirmed_values(cv: dict) -> str:
    lines = []
    for field, values in cv.items():
        if isinstance(values, list):
            if len(values) == 1:
                lines.append(f'{field} → confirmed: "{values[0]}"')
            else:
                joined = ", ".join(f'"{v}"' for v in values)
                lines.append(f'{field} → confirmed db values: [{joined}]')
        else:
            lines.append(f'{field} → confirmed: "{values}"')
    return "\n".join(lines)


def _format_schema_digest(sd: dict) -> str:
    lines = []
    for table, info in sd.get("tables", {}).items():
        cols = ", ".join(f"{c['name']}({c['type']})" for c in info.get("columns", []))
        lines.append(f"{table}: {cols}")
        for fk in info.get("fk", []):
            lines.append(f"  FK: {fk['from']} → {fk['to']}")
    top_keys = sd.get("top_keys", [])
    if top_keys:
        lines.append("Top property keys: " + ", ".join(top_keys[:10]))
    return "\n".join(lines)


def _relevant_agents_sections(agents_md_index: dict, task_text: str) -> dict[str, list[str]]:
    task_words = {w.lower() for w in task_text.split() if len(w) > 3}
    relevant = {}
    for section, lines in agents_md_index.items():
        section_text = (" ".join(lines) + " " + section).lower()
        if any(w in section_text for w in task_words):
            relevant[section] = lines
    return relevant


def _build_static_system(
    phase: str,
    agents_md: str,
    agents_md_index: dict,
    db_schema: str,
    schema_digest: dict,
    rules_loader: RulesLoader,
    security_gates: list[dict],
    confirmed_values: dict | None = None,
    task_text: str = "",
) -> list[dict]:
    blocks: list[dict] = []

    if phase in ("sql_plan", "learn", "answer"):
        if agents_md_index and task_text and phase in ("sql_plan", "learn"):
            relevant = _relevant_agents_sections(agents_md_index, task_text)
            index_line = "Section index: " + ", ".join(agents_md_index.keys())
            if relevant:
                section_blocks = "\n\n".join(
                    f"### {k}\n" + "\n".join(lines) for k, lines in relevant.items()
                )
                blocks.append({"type": "text", "text": f"# VAULT RULES\n{index_line}\n\n{section_blocks}"})
            elif agents_md:
                blocks.append({"type": "text", "text": f"# VAULT RULES\n{agents_md}"})
        elif agents_md:
            blocks.append({"type": "text", "text": f"# VAULT RULES\n{agents_md}"})

    if phase in ("sql_plan", "learn"):
        rules_md = rules_loader.get_rules_markdown(phase="sql_plan", verified_only=True)
        if rules_md:
            blocks.append({"type": "text", "text": f"# PIPELINE RULES\n{rules_md}"})

    if phase == "sql_plan" and security_gates:
        blocks.append({"type": "text", "text": f"# SECURITY GATES\n{_gates_summary(security_gates)}"})

    if schema_digest and phase in ("sql_plan", "learn"):
        blocks.append({"type": "text", "text": f"# SCHEMA DIGEST\n{_format_schema_digest(schema_digest)}"})

    if db_schema:
        blocks.append({"type": "text", "text": f"# DATABASE SCHEMA\n{db_schema}"})

    if confirmed_values and phase in ("sql_plan", "learn"):
        blocks.append({"type": "text", "text": f"# CONFIRMED VALUES\n{_format_confirmed_values(confirmed_values)}"})

    guide = load_prompt(phase)
    blocks.append({
        "type": "text",
        "text": guide or f"# PHASE: {phase}",
        "cache_control": {"type": "ephemeral"},
    })
    return blocks


def _build_sql_user_msg(
    task_text: str,
    session_rules: list[str],
    highlighted_vault_rules: list[str],
    last_error: str,
) -> str:
    parts: list[str] = []
    for r in highlighted_vault_rules:
        parts.append(f"# HIGHLIGHTED VAULT RULE\n{r}")
    for r in session_rules:
        parts.append(f"# IN-SESSION RULE\n{r}")
    parts.append(f"TASK: {task_text}")
    if last_error:
        parts.append(f"PREVIOUS ERROR: {last_error}")
    return "\n\n".join(parts)


def _build_learn_user_msg(task_text: str, queries: list[str], error: str, error_type: str) -> str:
    return (
        f"TASK: {task_text}\n"
        f"FAILED QUERIES: {json.dumps(queries)}\n"
        f"ERROR: {error}\n"
        f"ERROR_TYPE: {error_type}"
    )


def _build_answer_user_msg(task_text: str, sql_results: list[str], auto_refs: list[str]) -> str:
    base = f"TASK: {task_text}\n\nSQL RESULTS:\n" + "\n---\n".join(sql_results)
    if not auto_refs:
        return base
    refs_block = "\n".join(auto_refs)
    return (
        base
        + f"\n\nAUTO_REFS (from sku column in SQL results — MUST be included in grounding_refs):\n{refs_block}"
    )


def _extract_discovery_results(
    queries: list[str],
    results: list[str],
    confirmed_values: dict,
) -> None:
    """Update confirmed_values in-place from DISTINCT query results."""
    for q, result_txt in zip(queries, results):
        m = re.search(r'SELECT\s+DISTINCT\s+(\w+)', q, re.IGNORECASE)
        if not m:
            continue
        col = m.group(1).lower()
        lines = [ln.strip() for ln in result_txt.strip().splitlines() if ln.strip()]
        for line in lines[1:]:
            val = line.split(",")[0].strip().strip('"')
            if val:
                if col not in confirmed_values:
                    confirmed_values[col] = []
                if val not in confirmed_values[col]:
                    confirmed_values[col].append(val)


def _extract_sku_refs(queries: list[str], results: list[str]) -> list[str]:
    """Extract /proc/catalog/{sku}.json paths from SQL results that contain a sku column."""
    refs: list[str] = []
    for result_txt in results:
        lines = [ln.strip() for ln in result_txt.strip().splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        headers = [h.strip().lower() for h in lines[0].split(",")]
        if "sku" not in headers:
            continue
        sku_idx = headers.index("sku")
        for row in lines[1:]:
            cols = row.split(",")
            if sku_idx < len(cols):
                sku = cols[sku_idx].strip().strip('"')
                if sku:
                    refs.append(f"/proc/catalog/{sku}.json")
    return refs


def run_pipeline(
    vm: EcomRuntimeClientSync,
    model: str,
    task_text: str,
    pre: PrephaseResult,
    cfg: dict,
) -> tuple[dict, threading.Thread | None]:
    """Phase-based SQL pipeline. Returns (stats dict, eval Thread or None)."""
    rules_loader = _get_rules_loader()
    security_gates = _get_security_gates()
    session_rules: list[str] = []
    highlighted_vault_rules: list[str] = []
    sgr_trace: list[dict] = []
    total_in_tok = 0
    total_out_tok = 0

    last_error = ""
    sql_results: list[str] = []
    executed_queries: list[str] = []
    sku_refs: list[str] = []
    sql_plan_outputs: list[SqlPlanOutput] = []
    success = False
    cycles_used = 0

    # ── RESOLVE ───────────────────────────────────────────────────────────────
    confirmed_values: dict = run_resolve(vm, model, task_text, pre, cfg)
    if confirmed_values:
        print(f"{CLI_BLUE}[pipeline] RESOLVE: {list(confirmed_values.keys())}{CLI_CLR}")

    static_sql = _build_static_system(
        "sql_plan", pre.agents_md_content, pre.agents_md_index, pre.db_schema,
        pre.schema_digest, rules_loader, security_gates,
        confirmed_values=confirmed_values, task_text=task_text,
    )
    static_learn = _build_static_system(
        "learn", pre.agents_md_content, pre.agents_md_index, pre.db_schema,
        pre.schema_digest, rules_loader, security_gates,
        confirmed_values=confirmed_values, task_text=task_text,
    )
    static_answer = _build_static_system(
        "answer", pre.agents_md_content, pre.agents_md_index, pre.db_schema,
        pre.schema_digest, rules_loader, security_gates,
    )

    for cycle in range(_MAX_CYCLES):
        cycles_used = cycle + 1
        print(f"\n{CLI_BLUE}[pipeline] cycle={cycle + 1}/{_MAX_CYCLES}{CLI_CLR}")

        # ── SQL_PLAN ──────────────────────────────────────────────────────────
        user_msg = _build_sql_user_msg(task_text, session_rules, highlighted_vault_rules, last_error)
        sql_plan_out, sgr_entry, tok = _call_llm_phase(
            static_sql, user_msg, model, cfg, SqlPlanOutput,
            phase="sql_plan", cycle=cycle + 1,
        )
        total_in_tok += tok.get("input", 0)
        total_out_tok += tok.get("output", 0)
        sgr_trace.append(sgr_entry)

        if not sql_plan_out:
            print(f"{CLI_RED}[pipeline] SQL_PLAN LLM call failed{CLI_CLR}")
            last_error = "SQL_PLAN phase LLM call failed"
            _run_learn(static_learn, model, cfg, task_text, [], last_error,
                       sgr_trace, session_rules, highlighted_vault_rules,
                       pre.agents_md_index, error_type="llm_fail", cycle=cycle + 1)
            continue

        sql_plan_outputs.append(sql_plan_out)
        queries = sql_plan_out.queries
        print(f"{CLI_BLUE}[pipeline] SQL_PLAN: {len(queries)} queries{CLI_CLR}")

        # ── AGENTS.MD REFS CHECK ───────────────────────────────────────────────
        if not sql_plan_out.agents_md_refs and pre.agents_md_index:
            task_lower = task_text.lower()
            index_terms_in_task = [
                k for k in pre.agents_md_index
                if any(part in task_lower for part in k.split("_"))
            ]
            if index_terms_in_task:
                last_error = "agents_md_refs empty despite known vocabulary terms in task"
                print(f"{CLI_YELLOW}[pipeline] AGENTS.MD refs check failed: {last_error}{CLI_CLR}")
                _run_learn(static_learn, model, cfg, task_text, queries, last_error,
                           sgr_trace, session_rules, highlighted_vault_rules,
                           pre.agents_md_index, error_type="semantic", cycle=cycle + 1)
                continue

        # ── SECURITY CHECK ────────────────────────────────────────────────────
        gate_err = check_sql_queries(queries, security_gates)
        if t := get_trace():
            t.log_gate_check(cycle + 1, "security", queries, bool(gate_err), gate_err or None)
        if gate_err:
            print(f"{CLI_YELLOW}[pipeline] SECURITY gate blocked: {gate_err}{CLI_CLR}")
            last_error = gate_err
            _run_learn(static_learn, model, cfg, task_text, queries, last_error,
                       sgr_trace, session_rules, highlighted_vault_rules,
                       pre.agents_md_index, error_type="security", cycle=cycle + 1)
            continue

        # ── SCHEMA GATE ───────────────────────────────────────────────────────
        schema_err = check_schema_compliance(queries, pre.schema_digest, confirmed_values, task_text)
        if t := get_trace():
            t.log_gate_check(cycle + 1, "schema", queries, bool(schema_err), schema_err or None)
        if schema_err:
            print(f"{CLI_YELLOW}[pipeline] SCHEMA gate blocked: {schema_err}{CLI_CLR}")
            last_error = schema_err
            _run_learn(static_learn, model, cfg, task_text, queries, last_error,
                       sgr_trace, session_rules, highlighted_vault_rules,
                       pre.agents_md_index, error_type="security", cycle=cycle + 1)
            continue

        # ── VALIDATE ──────────────────────────────────────────────────────────
        validate_error = None
        for q in queries:
            try:
                result = vm.exec(ExecRequest(path="/bin/sql", args=[f"EXPLAIN {q}"]))
                result_txt = _exec_result_text(result)
                if "error" in result_txt.lower():
                    validate_error = f"EXPLAIN error: {result_txt[:200]}"
                    if t := get_trace():
                        t.log_sql_validate(cycle + 1, q, result_txt, validate_error)
                    break
                if t := get_trace():
                    t.log_sql_validate(cycle + 1, q, result_txt, None)
            except Exception as e:
                validate_error = f"EXPLAIN exception: {e}"
                if t := get_trace():
                    t.log_sql_validate(cycle + 1, q, "", validate_error)
                break

        if validate_error:
            print(f"{CLI_YELLOW}[pipeline] VALIDATE failed: {validate_error}{CLI_CLR}")
            last_error = validate_error
            _run_learn(static_learn, model, cfg, task_text, queries, last_error,
                       sgr_trace, session_rules, highlighted_vault_rules,
                       pre.agents_md_index, error_type="syntax", cycle=cycle + 1)
            continue

        # ── EXECUTE ───────────────────────────────────────────────────────────
        execute_error = None
        sql_results = []
        for q in queries:
            try:
                _t0 = time.monotonic()
                result = vm.exec(ExecRequest(path="/bin/sql", args=[q]))
                _dur = int((time.monotonic() - _t0) * 1000)
                result_txt = _exec_result_text(result)
                sql_results.append(result_txt)
                if t := get_trace():
                    t.log_sql_execute(cycle + 1, q, result_txt, _csv_has_data(result_txt), _dur)
                print(f"{CLI_BLUE}[pipeline] EXECUTE: {q[:60]!r} → {result_txt[:80]}{CLI_CLR}")
            except Exception as e:
                execute_error = f"Execute exception: {e}"
                break

        last_empty = not sql_results or not _csv_has_data(sql_results[-1])
        if execute_error or last_empty:
            err = execute_error or f"Empty result set: {(sql_results[-1] if sql_results else '').strip()[:120]}"
            print(f"{CLI_YELLOW}[pipeline] EXECUTE failed: {err}{CLI_CLR}")
            last_error = err
            _run_learn(static_learn, model, cfg, task_text, queries, last_error,
                       sgr_trace, session_rules, highlighted_vault_rules,
                       pre.agents_md_index,
                       error_type="empty" if last_empty and not execute_error else "semantic",
                       cycle=cycle + 1)
            continue

        # ── CARRYOVER: update confirmed_values from DISTINCT results ──────────
        executed_queries.extend(queries)
        _extract_discovery_results(queries, sql_results, confirmed_values)
        sku_refs.extend(_extract_sku_refs(queries, sql_results))

        success = True
        break

    outcome = "OUTCOME_NONE_CLARIFICATION"
    if not success:
        print(f"{CLI_RED}[pipeline] All {_MAX_CYCLES} cycles exhausted — clarification{CLI_CLR}")
        try:
            vm.answer(AnswerRequest(
                message="Could not retrieve data after multiple attempts.",
                outcome=OUTCOME_BY_NAME["OUTCOME_NONE_CLARIFICATION"],
                refs=[],
            ))
        except Exception as e:
            print(f"{CLI_RED}[pipeline] vm.answer error: {e}{CLI_CLR}")
    else:
        # ── ANSWER ────────────────────────────────────────────────────────────
        answer_user = _build_answer_user_msg(task_text, sql_results, sku_refs)
        answer_out, sgr_answer, tok = _call_llm_phase(
            static_answer, answer_user, model, cfg, AnswerOutput,
            phase="answer", cycle=cycle + 1,
        )
        total_in_tok += tok.get("input", 0)
        total_out_tok += tok.get("output", 0)
        sgr_trace.append(sgr_answer)

        if answer_out:
            outcome = answer_out.outcome
            print(f"{CLI_GREEN}[pipeline] ANSWER: {outcome} — {answer_out.message[:100]}{CLI_CLR}")
            try:
                vm.answer(AnswerRequest(
                    message=answer_out.message,
                    outcome=OUTCOME_BY_NAME[outcome],
                    refs=answer_out.grounding_refs,
                ))
            except Exception as e:
                print(f"{CLI_RED}[pipeline] vm.answer error: {e}{CLI_CLR}")

    # ── EVALUATE (always, success or fail) ────────────────────────────────────
    eval_thread: threading.Thread | None = None
    if _EVAL_ENABLED and _MODEL_EVALUATOR:
        eval_thread = threading.Thread(
            target=_run_evaluator_safe,
            kwargs={
                "task_text": task_text,
                "agents_md": pre.agents_md_content,
                "agents_md_index": pre.agents_md_index,
                "db_schema": pre.db_schema,
                "schema_digest": pre.schema_digest,
                "sgr_trace": sgr_trace,
                "cycles": cycles_used,
                "final_outcome": outcome,
                "sql_plan_outputs": sql_plan_outputs,
                "executed_queries": executed_queries,
                "model": _MODEL_EVALUATOR,
                "cfg": cfg,
            },
            daemon=False,
        )
        eval_thread.start()

    stats = {
        "outcome": outcome,
        "cycles_used": cycles_used,
        "step_facts": [f"pipeline cycles={cycles_used}"],
        "done_ops": [],
        "input_tokens": total_in_tok,
        "output_tokens": total_out_tok,
        "total_elapsed_ms": 0,
    }
    return stats, eval_thread


def _run_learn(
    static_learn: "str | list[dict]",
    model: str,
    cfg: dict,
    task_text: str,
    queries: list[str],
    error: str,
    sgr_trace: list[dict],
    session_rules: list[str],
    highlighted_vault_rules: list[str],
    agents_md_index: dict,
    error_type: str = "semantic",
    cycle: int = 0,
) -> None:
    learn_user = _build_learn_user_msg(task_text, queries, error, error_type)
    learn_out, sgr_learn, _ = _call_llm_phase(
        static_learn, learn_user, model, cfg, LearnOutput,
        max_tokens=2048, phase="learn", cycle=cycle,
    )
    sgr_learn["error_type"] = error_type
    sgr_trace.append(sgr_learn)
    if learn_out and error_type != "llm_fail":
        anchor = learn_out.agents_md_anchor
        if anchor:
            anchor_section = anchor.split(">")[0].strip()
            if anchor_section in agents_md_index:
                anchor_lines = agents_md_index[anchor_section]
                highlighted_vault_rules.append(f"[{anchor_section}]\n" + "\n".join(anchor_lines))
                print(f"{CLI_BLUE}[pipeline] LEARN: anchor={anchor!r}, elevating vault rule{CLI_CLR}")
                return
        session_rules.append(learn_out.rule_content)
        session_rules[:] = session_rules[-3:]
        print(f"{CLI_BLUE}[pipeline] LEARN: rule added to session, retrying{CLI_CLR}")


def _run_evaluator_safe(
    task_text: str,
    agents_md: str,
    agents_md_index: dict,
    db_schema: str,
    schema_digest: dict,
    sgr_trace: list[dict],
    cycles: int,
    final_outcome: str,
    sql_plan_outputs: list,
    executed_queries: list[str],
    model: str,
    cfg: dict,
) -> None:
    try:
        from .evaluator import run_evaluator, EvalInput
        run_evaluator(
            EvalInput(
                task_text=task_text,
                agents_md=agents_md,
                db_schema=db_schema,
                sgr_trace=sgr_trace,
                cycles=cycles,
                final_outcome=final_outcome,
            ),
            model=model,
            cfg=cfg,
        )
    except Exception as e:
        print(f"{CLI_YELLOW}[pipeline] evaluator error (non-fatal): {e}{CLI_CLR}")
