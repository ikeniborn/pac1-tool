# agent/contract_phase.py
"""Pre-execution contract negotiation between executor and evaluator agents.

Two LLM roles exchange Pydantic-validated JSON messages for up to max_rounds.
When both set agreed=True, a Contract is finalized. Otherwise falls back to
data/default_contracts/{task_type}.json (then data/default_contracts/default.json).

Fail-open: any LLM error or JSON parse failure → returns default contract.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import ValidationError

from .contract_models import Contract, ContractRound, EvaluatorResponse, ExecutorProposal
from .dispatch import call_llm_raw
from .json_extract import _extract_json_from_text
from .wiki import load_contract_constraints as _load_contract_constraints

_DATA = Path(__file__).parent.parent / "data"
_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

_EXECUTOR_PROGRAM_PATH = _DATA / "contract_executor_program.json"
_EVALUATOR_PROGRAM_PATH = _DATA / "contract_evaluator_program.json"


def _effective_model(caller_model: str) -> str:
    """Return MODEL_CONTRACT if set, else caller_model."""
    return os.environ.get("MODEL_CONTRACT") or caller_model


_executor_predictor = None
_evaluator_predictor = None


def _load_compiled_programs() -> bool:
    """Load compiled DSPy programs at module startup. Returns True on success, False on fail-open."""
    global _executor_predictor, _evaluator_predictor
    if not (_EXECUTOR_PROGRAM_PATH.exists() and _EVALUATOR_PROGRAM_PATH.exists()):
        return False
    try:
        import dspy
        from .optimization.contract_modules import ExecutorPropose, EvaluatorReview
        ep = dspy.Predict(ExecutorPropose)
        ep.load(str(_EXECUTOR_PROGRAM_PATH))
        evp = dspy.Predict(EvaluatorReview)
        evp.load(str(_EVALUATOR_PROGRAM_PATH))
        _executor_predictor = ep
        _evaluator_predictor = evp
        if _LOG_LEVEL == "DEBUG":
            print("[contract] Loaded compiled executor/evaluator programs")
        return True
    except Exception as exc:
        if _LOG_LEVEL == "DEBUG":
            print(f"[contract] Failed to load compiled programs: {exc}")
        return False


_load_compiled_programs()


def _load_prompt(role: str, task_type: str) -> str:
    """Load domain-specific prompt, falling back to default."""
    for folder in (task_type, "default"):
        p = _DATA / "prompts" / folder / f"{role}_contract.md"
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    return ""


def _load_default_contract(task_type: str) -> Contract:
    """Load fallback contract: per-type first, then universal default."""
    for name in (f"{task_type}.json", "default.json"):
        p = _DATA / "default_contracts" / name
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                data["is_default"] = True
                data.setdefault("rounds_taken", 0)
                return Contract(**data)
            except Exception:
                pass
    # Hard fallback if files missing
    return Contract(
        plan_steps=["discover vault", "execute task", "report"],
        success_criteria=["task completed"],
        required_evidence=[],
        failure_conditions=["no action taken"],
        is_default=True,
        rounds_taken=0,
    )


def negotiate_contract(
    task_text: str,
    task_type: str,
    agents_md: str,
    wiki_context: str,
    graph_context: str,
    model: str,
    cfg: dict,
    max_rounds: int = 3,
    vault_date_hint: str = "",
    vault_tree: str = "",
) -> tuple[Contract, int, int, list[dict]]:
    """Run contract negotiation. Returns (contract, total_in_tokens, total_out_tokens, rounds_transcript).

    Each round:
      1. ExecutorAgent proposes/refines plan → ExecutorProposal
      2. EvaluatorAgent responds with criteria/objections → EvaluatorResponse
      3. Both agreed=True → finalize; else continue.
      4. FIX-406: if evaluator agreed with no objections, accept even if executor
         did not self-agree — evaluator is the authority on success criteria.
    Fallback to default contract on: max_rounds exceeded, LLM error, parse error.
    """
    executor_system = _load_prompt("executor", task_type)
    evaluator_system = _load_prompt("evaluator", task_type)

    if not executor_system or not evaluator_system:
        if _LOG_LEVEL == "DEBUG":
            print("[contract] prompts missing — using default contract")
        return _load_default_contract(task_type), 0, 0, []

    # FIX-394: CC tier cannot produce structured JSON (tool_use blocks are stripped
    # from result). Skip negotiation entirely — avoids 1-2 empty subprocess launches
    # per task. Default contract is equivalent to what negotiate_contract would return.
    if model.startswith("claude-code/"):
        if _LOG_LEVEL == "DEBUG":
            print("[contract] CC tier — skipping negotiation, using default contract")
        return _load_default_contract(task_type), 0, 0, []

    negotiation_model = _effective_model(model)

    context_block = ""
    if vault_date_hint:
        # Neutral date anchor — executor uses this as lower bound, not literal today.
        context_block += (
            f"\n\nDATE CONTEXT:\nVAULT_DATE_LOWER_BOUND: {vault_date_hint}"
            f"\n(Real benchmark today ≥ this date; use it as anchor to derive ESTIMATED_TODAY.)"
        )
    if agents_md:
        context_block += f"\n\nAGENTS.MD:\n{agents_md}"
    if wiki_context:
        context_block += f"\n\nWIKI CONTEXT:\n{wiki_context}"
    if graph_context:
        context_block += f"\n\nKNOWLEDGE GRAPH:\n{graph_context}"
    if vault_tree:
        context_block += f"\n\nVAULT STRUCTURE:\n{vault_tree}"

    # FIX-415: load wiki contract constraints for evaluator checklist
    _constraints = _load_contract_constraints(task_type)
    _constraint_checklist = ""
    if _constraints:
        _lines = ["CONSTRAINT CHECKLIST (verify planned_mutations against these before agreeing):"]
        for _c in _constraints:
            _lines.append(f"- {_c['id']}: {_c['rule']}")
        _constraint_checklist = "\n".join(_lines)

    # FIX-393: build per-role cfg overrides with Pydantic-derived JSON schemas
    # so CC tier enforces structured output via --json-schema.
    _base_cc_opts = cfg.get("cc_options")
    if not isinstance(_base_cc_opts, dict):
        _base_cc_opts = {}
    executor_cfg = {**cfg, "cc_options": {**_base_cc_opts,
                                           "cc_json_schema": ExecutorProposal.model_json_schema()}}
    evaluator_cfg = {**cfg, "cc_options": {**_base_cc_opts,
                                            "cc_json_schema": EvaluatorResponse.model_json_schema()}}

    total_in = total_out = 0
    last_evaluator_response = ""
    rounds_transcript: list[dict] = []
    _PARSE_RETRIES = 3

    for round_num in range(1, max_rounds + 1):
        # --- Executor turn ---
        executor_user = f"TASK: {task_text}{context_block}"
        if last_evaluator_response:
            executor_user += f"\n\nEVALUATOR RESPONSE (round {round_num - 1}):\n{last_evaluator_response}"
        executor_user += "\n\nPropose your execution plan as JSON."

        executor_tok: dict = {}
        raw_executor = call_llm_raw(
            executor_system, executor_user, negotiation_model, executor_cfg,
            max_tokens=800, token_out=executor_tok,
        )
        total_in += executor_tok.get("input", 0)
        total_out += executor_tok.get("output", 0)

        if not raw_executor:
            if _LOG_LEVEL == "DEBUG":
                print(f"[contract] executor LLM failed round {round_num}")
            return _load_default_contract(task_type), total_in, total_out, rounds_transcript

        # FIX-407: retry parse up to _PARSE_RETRIES before skipping round
        proposal = None
        for _retry in range(_PARSE_RETRIES):
            extracted_executor = _extract_json_from_text(raw_executor)
            try:
                proposal = ExecutorProposal(**(extracted_executor or {}))
                break
            except (ValidationError, TypeError) as e:
                if _LOG_LEVEL == "DEBUG":
                    print(f"[contract] executor parse error round {round_num} attempt {_retry + 1}: {e}")
                if _retry < _PARSE_RETRIES - 1:
                    _retry_tok: dict = {}
                    raw_executor = call_llm_raw(
                        executor_system, executor_user, negotiation_model, executor_cfg,
                        max_tokens=800, token_out=_retry_tok,
                    ) or raw_executor
                    total_in += _retry_tok.get("input", 0)
                    total_out += _retry_tok.get("output", 0)

        if proposal is None:
            if _LOG_LEVEL == "DEBUG":
                print(f"[contract] executor parse exhausted round {round_num} — skipping round")
            continue

        # --- Evaluator turn ---
        evaluator_user = (
            f"TASK: {task_text}{context_block}\n\n"
            f"EXECUTOR PROPOSAL (round {round_num}):\n{raw_executor}\n\n"
            "Review the plan and respond with your criteria as JSON."
        )
        if _constraint_checklist:
            evaluator_user += f"\n\n{_constraint_checklist}"

        evaluator_tok: dict = {}
        raw_evaluator = call_llm_raw(
            evaluator_system, evaluator_user, negotiation_model, evaluator_cfg,
            max_tokens=800, token_out=evaluator_tok,
        )
        total_in += evaluator_tok.get("input", 0)
        total_out += evaluator_tok.get("output", 0)

        if not raw_evaluator:
            if _LOG_LEVEL == "DEBUG":
                print(f"[contract] evaluator LLM failed round {round_num}")
            return _load_default_contract(task_type), total_in, total_out, rounds_transcript

        # FIX-407: retry parse up to _PARSE_RETRIES before skipping round
        response = None
        for _retry in range(_PARSE_RETRIES):
            extracted_evaluator = _extract_json_from_text(raw_evaluator)
            try:
                response = EvaluatorResponse(**(extracted_evaluator or {}))
                break
            except (ValidationError, TypeError) as e:
                if _LOG_LEVEL == "DEBUG":
                    print(f"[contract] evaluator parse error round {round_num} attempt {_retry + 1}: {e}")
                if _retry < _PARSE_RETRIES - 1:
                    _retry_tok2: dict = {}
                    raw_evaluator = call_llm_raw(
                        evaluator_system, evaluator_user, negotiation_model, evaluator_cfg,
                        max_tokens=800, token_out=_retry_tok2,
                    ) or raw_evaluator
                    total_in += _retry_tok2.get("input", 0)
                    total_out += _retry_tok2.get("output", 0)

        if response is None:
            if _LOG_LEVEL == "DEBUG":
                print(f"[contract] evaluator parse exhausted round {round_num} — skipping round")
            continue

        rounds_transcript.append(ContractRound(
            round_num=round_num,
            executor_proposal=proposal.model_dump(),
            evaluator_response=response.model_dump(),
        ).model_dump())

        last_evaluator_response = raw_evaluator

        if _LOG_LEVEL == "DEBUG":
            print(
                f"[contract] round {round_num}: executor.agreed={proposal.agreed} "
                f"evaluator.agreed={response.agreed} objections={response.objections}"
            )

        # FIX-406: partial consensus — evaluator is authority on success criteria.
        # FIX-415: track evaluator-only flag and filter mutation_scope on forbidden paths.
        # FIX-418: blocking_objections are true blockers; objections are non-blocking notes.
        evaluator_accepts = response.agreed and not response.blocking_objections
        full_consensus = proposal.agreed and evaluator_accepts
        if full_consensus or evaluator_accepts:
            _evaluator_only = not full_consensus

            # FIX-415: build mutation_scope from proposal.planned_mutations.
            # On evaluator-only consensus, block mutations matching forbidden constraint keywords.
            _planned = list(proposal.planned_mutations)
            _forbidden_keywords = {"result.txt", ".disposition.json"}
            if _evaluator_only:
                _allowed = [
                    p for p in _planned
                    if not any(kw in p for kw in _forbidden_keywords)
                ]
            else:
                _allowed = _planned

            contract = Contract(
                plan_steps=proposal.plan_steps,
                success_criteria=response.success_criteria,
                required_evidence=response.required_evidence,
                failure_conditions=response.failure_conditions,
                mutation_scope=_allowed,
                forbidden_mutations=[p for p in _planned if p not in _allowed],
                evaluator_only=_evaluator_only,
                is_default=False,
                rounds_taken=round_num,
            )
            if _LOG_LEVEL == "DEBUG":
                mode = "full consensus" if full_consensus else "evaluator-only consensus"
                print(f"[contract] {mode} reached in {round_num} round(s)")
            return contract, total_in, total_out, rounds_transcript

    # Max rounds exceeded — use partial contract from last round if available
    if _LOG_LEVEL == "DEBUG":
        print(
            f"[contract] max_rounds={max_rounds} exceeded — "
            f"{'using partial from last round' if rounds_transcript else 'using default contract'}"
        )
    if rounds_transcript:
        last = rounds_transcript[-1]
        ep = last["executor_proposal"]
        er = last["evaluator_response"]
        return Contract(
            plan_steps=ep.get("plan_steps", []),
            success_criteria=er.get("success_criteria", []),
            required_evidence=er.get("required_evidence", []),
            failure_conditions=er.get("failure_conditions", []),
            mutation_scope=[],
            forbidden_mutations=[],
            evaluator_only=True,
            is_default=False,
            rounds_taken=max_rounds,
        ), total_in, total_out, rounds_transcript
    return _load_default_contract(task_type), total_in, total_out, rounds_transcript
