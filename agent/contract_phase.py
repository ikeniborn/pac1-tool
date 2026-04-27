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
import re
from pathlib import Path

from pydantic import ValidationError

from .contract_models import Contract, EvaluatorResponse, ExecutorProposal
from .dispatch import call_llm_raw

_DATA = Path(__file__).parent.parent / "data"
_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)


def _strip_fences(text: str) -> str:
    """Strip markdown code fences from LLM output before JSON parsing."""
    text = text.strip()
    m = _FENCE_RE.match(text)
    return m.group(1).strip() if m else text


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
) -> tuple[Contract, int, int]:
    """Run contract negotiation. Returns (contract, total_in_tokens, total_out_tokens).

    Each round:
      1. ExecutorAgent proposes/refines plan → ExecutorProposal
      2. EvaluatorAgent responds with criteria/objections → EvaluatorResponse
      3. Both agreed=True → finalize; else continue.
    Fallback to default contract on: max_rounds exceeded, LLM error, parse error.
    """
    executor_system = _load_prompt("executor", task_type)
    evaluator_system = _load_prompt("evaluator", task_type)

    if not executor_system or not evaluator_system:
        if _LOG_LEVEL == "DEBUG":
            print("[contract] prompts missing — using default contract")
        return _load_default_contract(task_type), 0, 0

    context_block = ""
    if agents_md:
        context_block += f"\n\nAGENTS.MD:\n{agents_md[:2000]}"
    if wiki_context:
        context_block += f"\n\nWIKI CONTEXT:\n{wiki_context[:1000]}"
    if graph_context:
        context_block += f"\n\nKNOWLEDGE GRAPH:\n{graph_context[:500]}"

    total_in = total_out = 0
    last_evaluator_response = ""

    for round_num in range(1, max_rounds + 1):
        # --- Executor turn ---
        executor_user = f"TASK: {task_text}{context_block}"
        if last_evaluator_response:
            executor_user += f"\n\nEVALUATOR RESPONSE (round {round_num - 1}):\n{last_evaluator_response}"
        executor_user += "\n\nPropose your execution plan as JSON."

        executor_tok: dict = {}
        raw_executor = call_llm_raw(
            executor_system, executor_user, model, cfg,
            max_tokens=800, token_out=executor_tok,
        )
        total_in += executor_tok.get("input", 0)
        total_out += executor_tok.get("output", 0)

        if not raw_executor:
            if _LOG_LEVEL == "DEBUG":
                print(f"[contract] executor LLM failed round {round_num}")
            return _load_default_contract(task_type), total_in, total_out

        try:
            proposal = ExecutorProposal(**json.loads(raw_executor))
        except (json.JSONDecodeError, ValidationError) as e:
            if _LOG_LEVEL == "DEBUG":
                print(f"[contract] executor parse error round {round_num}: {e}")
            return _load_default_contract(task_type), total_in, total_out

        # --- Evaluator turn ---
        evaluator_user = (
            f"TASK: {task_text}{context_block}\n\n"
            f"EXECUTOR PROPOSAL (round {round_num}):\n{raw_executor}\n\n"
            "Review the plan and respond with your criteria as JSON."
        )

        evaluator_tok: dict = {}
        raw_evaluator = call_llm_raw(
            evaluator_system, evaluator_user, model, cfg,
            max_tokens=800, token_out=evaluator_tok,
        )
        total_in += evaluator_tok.get("input", 0)
        total_out += evaluator_tok.get("output", 0)

        if not raw_evaluator:
            if _LOG_LEVEL == "DEBUG":
                print(f"[contract] evaluator LLM failed round {round_num}")
            return _load_default_contract(task_type), total_in, total_out

        try:
            response = EvaluatorResponse(**json.loads(raw_evaluator))
        except (json.JSONDecodeError, ValidationError) as e:
            if _LOG_LEVEL == "DEBUG":
                print(f"[contract] evaluator parse error round {round_num}: {e}")
            return _load_default_contract(task_type), total_in, total_out

        last_evaluator_response = raw_evaluator

        if _LOG_LEVEL == "DEBUG":
            print(
                f"[contract] round {round_num}: executor.agreed={proposal.agreed} "
                f"evaluator.agreed={response.agreed} objections={response.objections}"
            )

        # Consensus: both agreed with no objections
        if proposal.agreed and response.agreed and not response.objections:
            contract = Contract(
                plan_steps=proposal.plan_steps,
                success_criteria=response.success_criteria,
                required_evidence=response.required_evidence,
                failure_conditions=response.failure_conditions,
                is_default=False,
                rounds_taken=round_num,
            )
            if _LOG_LEVEL == "DEBUG":
                print(f"[contract] consensus reached in {round_num} round(s)")
            return contract, total_in, total_out

    # Max rounds exceeded — fallback
    if _LOG_LEVEL == "DEBUG":
        print(f"[contract] max_rounds={max_rounds} exceeded — using default contract")
    return _load_default_contract(task_type), total_in, total_out
