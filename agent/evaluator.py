"""Post-execution pipeline evaluator. Fail-open: any exception returns None."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .llm import call_llm_raw
from .json_extract import _extract_json_from_text
from .models import PipelineEvalOutput
from .prompt import load_prompt

_EVAL_LOG = Path(__file__).parent.parent / "data" / "eval_log.jsonl"


@dataclass
class EvalInput:
    task_text: str
    agents_md: str
    db_schema: str
    sgr_trace: list[dict]
    cycles: int
    final_outcome: str


def run_evaluator(
    eval_input: EvalInput,
    model: str,
    cfg: dict,
) -> PipelineEvalOutput | None:
    """Evaluate pipeline trace. Returns PipelineEvalOutput or None on any failure."""
    try:
        return _run(eval_input, model, cfg)
    except Exception as e:
        print(f"[evaluator] non-fatal error: {e}")
        return None


def _run(eval_input: EvalInput, model: str, cfg: dict) -> PipelineEvalOutput | None:
    system = _build_eval_system(eval_input.agents_md)
    user_msg = json.dumps({
        "task_text": eval_input.task_text,
        "db_schema": eval_input.db_schema,
        "sgr_trace": eval_input.sgr_trace,
        "cycles": eval_input.cycles,
        "final_outcome": eval_input.final_outcome,
    }, ensure_ascii=False)

    raw = call_llm_raw(system, user_msg, model, cfg, max_tokens=2048)
    if not raw:
        return None

    parsed = _extract_json_from_text(raw)
    if not isinstance(parsed, dict):
        return None

    try:
        result = PipelineEvalOutput.model_validate(parsed)
    except Exception:
        return None

    _append_log(eval_input, result)
    return result


def _build_eval_system(agents_md: str) -> str:
    parts: list[str] = []
    if agents_md:
        parts.append(f"# VAULT RULES\n{agents_md}")
    guide = load_prompt("pipeline_evaluator")
    if guide:
        parts.append(guide)
    return "\n\n".join(parts)


def _append_log(eval_input: EvalInput, result: PipelineEvalOutput) -> None:
    entry = {
        "task_text": eval_input.task_text,
        "cycles": eval_input.cycles,
        "final_outcome": eval_input.final_outcome,
        "score": result.score,
        "comment": result.comment,
        "prompt_optimization": result.prompt_optimization,
        "rule_optimization": result.rule_optimization,
        "security_optimization": result.security_optimization,
        "reasoning": result.reasoning,
    }
    _EVAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(_EVAL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
