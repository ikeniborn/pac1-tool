"""Phase-based SQL pipeline for lookup tasks — replaces run_loop() for task_type='lookup'."""
from __future__ import annotations

import json
import os
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync
from bitgn.vm.ecom.ecom_pb2 import AnswerRequest, ExecRequest

from .dispatch import (
    call_llm_raw, OUTCOME_BY_NAME,
    CLI_BLUE, CLI_CLR, CLI_GREEN, CLI_RED, CLI_YELLOW,
)
from .json_extract import _extract_json_from_text
from .models import SqlPlanOutput, LearnOutput, AnswerOutput
from .prephase import PrephaseResult
from .prompt import load_prompt
from .rules_loader import RulesLoader, _RULES_DIR
from .sql_security import check_sql_queries, load_security_gates

_MAX_CYCLES = 3
_EVAL_ENABLED = os.environ.get("EVAL_ENABLED", "0") == "1"
_MODEL_EVALUATOR = os.environ.get("MODEL_EVALUATOR", "")
_EVAL_LOG = Path(__file__).parent.parent / "data" / "eval_log.jsonl"


def _exec_result_text(result) -> str:
    """Extract stdout/output text from an ExecResponse or test mock."""
    if isinstance(result, Message):
        try:
            d = MessageToDict(result)
            return d.get("stdout", "") or d.get("output", "") or ""
        except Exception:
            pass
    return getattr(result, "stdout", "") or getattr(result, "output", "") or ""


def _csv_has_data(result_txt: str) -> bool:
    """/bin/sql returns CSV (header + data rows) or JSON array/object.
    CSV empty = only 1 line (headers only). JSON empty = [] or {}.
    """
    stripped = result_txt.strip()
    if not stripped:
        return False
    if stripped.startswith("["):
        return stripped not in ("[]",)
    if stripped.startswith("{"):
        return stripped not in ("{}",)
    # CSV: line 1 = column headers, lines 2+ = data rows
    lines = [l for l in stripped.splitlines() if l.strip()]
    return len(lines) > 1


def _call_llm_phase(
    system: str,
    user_msg: str,
    model: str,
    cfg: dict,
    output_cls,
    max_tokens: int = 4096,
) -> tuple[object | None, dict]:
    """SGR LLM call: returns (parsed_output_or_None, sgr_trace_entry)."""
    tok_info: dict = {}
    raw = call_llm_raw(system, user_msg, model, cfg, max_tokens=max_tokens, token_out=tok_info)
    phase_name = output_cls.__name__
    sgr_entry: dict = {
        "phase": phase_name,
        "guide_prompt": system[:300],
        "reasoning": "",
        "output": raw or "",
    }
    if not raw:
        return None, sgr_entry
    parsed = _extract_json_from_text(raw)
    if not isinstance(parsed, dict):
        return None, sgr_entry
    try:
        obj = output_cls.model_validate(parsed)
        sgr_entry["reasoning"] = obj.reasoning
        sgr_entry["output"] = parsed
        return obj, sgr_entry
    except Exception:
        return None, sgr_entry


def _gates_summary(gates: list[dict]) -> str:
    return "\n".join(f"- [{g['id']}] {g.get('message', '')}" for g in gates)


def _build_system(
    phase: str,
    agents_md: str,
    db_schema: str,
    rules_loader: RulesLoader,
    session_rules: list[str],
    security_gates: list[dict],
) -> str:
    parts: list[str] = []

    if phase in ("sql_plan", "learn", "answer", "pipeline_evaluator") and agents_md:
        parts.append(f"# VAULT RULES\n{agents_md}")

    if phase in ("sql_plan", "learn"):
        rules_md = rules_loader.get_rules_markdown(phase="sql_plan", verified_only=True)
        if rules_md:
            parts.append(f"# PIPELINE RULES\n{rules_md}")

    if phase == "sql_plan" and security_gates:
        parts.append(f"# SECURITY GATES\n{_gates_summary(security_gates)}")

    if db_schema:
        parts.append(f"# DATABASE SCHEMA\n{db_schema}")

    if phase in ("sql_plan", "learn"):
        for r in session_rules:
            parts.append(f"# IN-SESSION RULE\n{r}")

    guide = load_prompt(phase)
    if guide:
        parts.append(guide)

    return "\n\n".join(parts)


def run_pipeline(
    vm: EcomRuntimeClientSync,
    model: str,
    task_text: str,
    pre: PrephaseResult,
    cfg: dict,
) -> dict:
    """Phase-based SQL pipeline. Returns stats dict compatible with run_loop()."""
    rules_loader = RulesLoader(_RULES_DIR)
    security_gates = load_security_gates()
    session_rules: list[str] = []
    sgr_trace: list[dict] = []
    total_in_tok = 0
    total_out_tok = 0

    last_error = ""
    sql_results: list[str] = []
    success = False
    cycles_used = 0

    for cycle in range(_MAX_CYCLES):
        cycles_used = cycle + 1
        print(f"\n{CLI_BLUE}[pipeline] cycle={cycle + 1}/{_MAX_CYCLES}{CLI_CLR}")

        # ── SQL_PLAN ──────────────────────────────────────────────────────────
        system = _build_system("sql_plan", pre.agents_md_content, pre.db_schema,
                               rules_loader, session_rules, security_gates)
        user_msg = f"TASK: {task_text}"
        if last_error:
            user_msg += f"\n\nPREVIOUS ERROR: {last_error}"

        sql_plan_out, sgr_entry = _call_llm_phase(system, user_msg, model, cfg, SqlPlanOutput)
        sgr_trace.append(sgr_entry)

        if not sql_plan_out:
            print(f"{CLI_RED}[pipeline] SQL_PLAN LLM call failed{CLI_CLR}")
            last_error = "SQL_PLAN phase LLM call failed"
            _run_learn(pre, model, cfg, task_text, [], last_error,
                       rules_loader, session_rules, sgr_trace, security_gates)
            continue

        queries = sql_plan_out.queries
        print(f"{CLI_BLUE}[pipeline] SQL_PLAN: {len(queries)} queries{CLI_CLR}")

        # ── SECURITY CHECK (before VALIDATE so DDL never reaches EXPLAIN) ─────
        gate_err = check_sql_queries(queries, security_gates)
        if gate_err:
            print(f"{CLI_YELLOW}[pipeline] SECURITY gate blocked: {gate_err}{CLI_CLR}")
            last_error = gate_err
            _run_learn(pre, model, cfg, task_text, queries, last_error,
                       rules_loader, session_rules, sgr_trace, security_gates)
            continue

        # ── VALIDATE ──────────────────────────────────────────────────────────
        validate_error = None
        for q in queries:
            try:
                result = vm.exec(ExecRequest(path="/bin/sql", args=[f"EXPLAIN {q}"]))
                result_txt = _exec_result_text(result)
                if "error" in result_txt.lower():
                    validate_error = f"EXPLAIN error: {result_txt[:200]}"
                    break
            except Exception as e:
                validate_error = f"EXPLAIN exception: {e}"
                break

        if validate_error:
            print(f"{CLI_YELLOW}[pipeline] VALIDATE failed: {validate_error}{CLI_CLR}")
            last_error = validate_error
            _run_learn(pre, model, cfg, task_text, queries, last_error,
                       rules_loader, session_rules, sgr_trace, security_gates)
            continue

        # ── EXECUTE ───────────────────────────────────────────────────────────
        execute_error = None
        sql_results = []
        for q in queries:
            try:
                result = vm.exec(ExecRequest(path="/bin/sql", args=[q]))
                result_txt = _exec_result_text(result)
                sql_results.append(result_txt)
                print(f"{CLI_BLUE}[pipeline] EXECUTE: {q[:60]!r} → {result_txt[:80]}{CLI_CLR}")
            except Exception as e:
                execute_error = f"Execute exception: {e}"
                break

        # /bin/sql returns CSV: line 1 = column headers, lines 2+ = data rows.
        # Check the LAST result only — DISTINCT discovery queries always return data,
        # but the final answer query may return only headers (= empty result set).
        last_empty = not sql_results or not _csv_has_data(sql_results[-1])
        if execute_error or last_empty:
            err = execute_error or f"Empty result set: {(sql_results[-1] if sql_results else '').strip()[:120]}"
            print(f"{CLI_YELLOW}[pipeline] EXECUTE failed: {err}{CLI_CLR}")
            last_error = err
            _run_learn(pre, model, cfg, task_text, queries, last_error,
                       rules_loader, session_rules, sgr_trace, security_gates)
            continue

        success = True
        break

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
        return {
            "outcome": "OUTCOME_NONE_CLARIFICATION",
            "step_facts": [f"cycles={_MAX_CYCLES}"],
            "done_ops": [],
            "input_tokens": total_in_tok,
            "output_tokens": total_out_tok,
            "total_elapsed_ms": 0,
        }

    # ── ANSWER ────────────────────────────────────────────────────────────────
    answer_system = _build_system("answer", pre.agents_md_content, pre.db_schema,
                                  rules_loader, session_rules, security_gates)
    answer_user = f"TASK: {task_text}\n\nSQL RESULTS:\n" + "\n---\n".join(sql_results)
    answer_out, sgr_answer = _call_llm_phase(answer_system, answer_user, model, cfg, AnswerOutput)
    sgr_trace.append(sgr_answer)

    outcome = "OUTCOME_NONE_CLARIFICATION"
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

    # ── EVALUATE ──────────────────────────────────────────────────────────────
    if _EVAL_ENABLED and _MODEL_EVALUATOR:
        _run_evaluator_safe(
            task_text=task_text,
            agents_md=pre.agents_md_content,
            db_schema=pre.db_schema,
            sgr_trace=sgr_trace,
            cycles=cycles_used,
            final_outcome=outcome,
            model=_MODEL_EVALUATOR,
            cfg=cfg,
        )

    return {
        "outcome": outcome,
        "step_facts": [f"pipeline cycles={cycles_used}"],
        "done_ops": [],
        "input_tokens": total_in_tok,
        "output_tokens": total_out_tok,
        "total_elapsed_ms": 0,
    }


def _run_learn(
    pre: PrephaseResult,
    model: str,
    cfg: dict,
    task_text: str,
    queries: list[str],
    error: str,
    rules_loader: RulesLoader,
    session_rules: list[str],
    sgr_trace: list[dict],
    security_gates: list[dict],
) -> None:
    learn_system = _build_system("learn", pre.agents_md_content, pre.db_schema,
                                 rules_loader, session_rules, security_gates)
    learn_user = (
        f"TASK: {task_text}\n"
        f"FAILED QUERIES: {json.dumps(queries)}\n"
        f"ERROR: {error}"
    )
    learn_out, sgr_learn = _call_llm_phase(learn_system, learn_user, model, cfg, LearnOutput, max_tokens=2048)
    sgr_trace.append(sgr_learn)
    if learn_out:
        rules_loader.append_rule(learn_out.rule_content, task_id=task_text[:100])
        session_rules.append(learn_out.rule_content)
        print(f"{CLI_BLUE}[pipeline] LEARN: rule saved, retrying{CLI_CLR}")


def _run_evaluator_safe(
    task_text: str, agents_md: str, db_schema: str,
    sgr_trace: list[dict], cycles: int, final_outcome: str,
    model: str, cfg: dict,
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
