# Remove run_loop() and Vault Artifacts

**Date:** 2026-05-12  
**Status:** Approved  
**Scope:** Delete `agent/loop.py` and all code that exists only to support the freeform reactive loop — vault models, `dispatch()` tool router, few-shot prephase block. Rename `dispatch.py` → `llm.py`. Leave the structured pipeline (`pipeline.py`, `evaluator.py`) intact and connected.

---

## Problem

`agent/loop.py` implemented an open-ended reactive loop where the LLM decided tool sequences and emitted freeform 5-field JSON (`NextStep`). This loop has been replaced by the deterministic SQL pipeline (`pipeline.py`) for all `lookup` tasks — the only task type in the benchmark.

The reactive loop left behind significant dead code:
- `agent/loop.py` — 356 lines, no longer called
- Vault models in `models.py`: `NextStep`, `ReportTaskCompletion`, `Req_Write/Delete/Tree/Find/Search/List/Stat/Context`, `EmailOutbox`, `TaskRoute`
- `dispatch()` function in `dispatch.py` — routes vault tool calls, only called by loop
- `_normalize_parsed()` in `json_extract.py` — NextStep normalization, only called by loop
- Few-shot pair in `prephase.py` — primed the NextStep JSON format for loop
- Fallback branch in `orchestrator.py` — `run_loop()` call for non-lookup paths

---

## Solution

**Removal order: bottom-up (Variant A)** — clean models first so TDD signals cascade upward.

### Files changed

| File | Action | Detail |
|------|--------|--------|
| `agent/models.py` | remove vault models | delete `TaskRoute`, `NextStep`, all `Req_*` (8 classes), `ReportTaskCompletion`, `EmailOutbox`; keep `SqlPlanOutput`, `LearnOutput`, `AnswerOutput`, `PipelineEvalOutput` |
| `agent/json_extract.py` | remove loop artifacts | delete `_normalize_parsed()`; remove NextStep-specific priority logic from `_extract_json_from_text` |
| `agent/loop.py` | delete | entire file |
| `agent/dispatch.py` → `agent/llm.py` | rename + trim | delete `dispatch()` function (lines 634–685) and vault model imports; rename file |
| `agent/prephase.py` | remove few-shot | delete `_FEW_SHOT_USER`, `_FEW_SHOT_ASSISTANT` constants and their insertion into `log` |
| `agent/orchestrator.py` | remove fallback | delete `from agent.loop import run_loop` and `stats = run_loop(...)` branch |
| `tests/test_orchestrator_pipeline.py` | remove mock | delete `patch("agent.orchestrator.run_loop")` and `mock_loop.assert_not_called()` |
| `agent/pipeline.py` | update import | `from .dispatch import` → `from .llm import` |
| `agent/evaluator.py` | update import | `from .dispatch import` → `from .llm import` |

---

## What survives in `llm.py` (was `dispatch.py`)

- `call_llm_raw()` — single LLM call entry point, used by pipeline and evaluator
- `probe_structured_output()`, `get_response_format()` — capability probing
- `OUTCOME_BY_NAME` — string → protobuf Outcome enum mapping
- Provider routing: `get_provider()`, `get_anthropic_model_id()`
- Retry logic, transient error detection (`TRANSIENT_KWS`, `HARD_CONNECTION_KWS`)
- CLI colour constants (`CLI_RED`, `CLI_GREEN`, etc.)

## What survives in `models.py`

```python
SqlPlanOutput      # reasoning: str, queries: list[str]
LearnOutput        # reasoning: str, conclusion: str, rule_content: str
AnswerOutput       # reasoning: str, message: str, outcome: str, grounding_refs: list[str], completed_steps: list[str]
PipelineEvalOutput # reasoning: str, score: float, comment: str, prompt_optimization: list[str], rule_optimization: list[str]
```

## What survives in `json_extract.py`

Single public function: `_extract_json_from_text(text: str) -> dict | None`  
Used by `pipeline.py` and `evaluator.py` to parse raw LLM JSON responses.

---

## Dependency graph after removal

```
orchestrator.py
  → pipeline.py
      → llm.py          (call_llm_raw, OUTCOME_BY_NAME)
      → json_extract.py (_extract_json_from_text)
      → models.py       (SqlPlanOutput, LearnOutput, AnswerOutput)
      → rules_loader.py
      → sql_security.py
      → prompt.py
  → prephase.py
  → evaluator.py
      → llm.py
      → json_extract.py
      → models.py       (PipelineEvalOutput)
```

No cycles. No dead imports.

---

## Success criteria

- `agent/loop.py` does not exist
- `agent/dispatch.py` does not exist  
- `agent/llm.py` exists and exports `call_llm_raw`, `OUTCOME_BY_NAME`
- `agent/models.py` contains exactly 4 classes
- `from .llm import` in pipeline.py and evaluator.py
- All tests pass (`uv run pytest tests/ -v`)
