# Dispatch Reliability + Contract Objection Types

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two reliability gaps found during t43 post-mortem: (1) `[Errno 32] Broken Pipe` is not retried and has no fallback model; (2) contract evaluator treats informational notes as blocking objections, causing unnecessary extra rounds and premature max_rounds exhaustion.

**Architecture:**
- FIX-416/417: separate hard connection errors (`HARD_CONNECTION_KWS`) from soft transient errors (`TRANSIENT_KWS`). Hard errors get max 1 retry then immediately try `MODEL_FALLBACK`. Soft errors keep existing 3-retry behaviour.
- FIX-418: add `blocking_objections: list[str]` to `EvaluatorResponse`; consensus check uses this field instead of `objections`, so caveats/confirmations in `objections` no longer block agreement.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, uv

---

## File Map

| File | Change |
|------|--------|
| `agent/dispatch.py:258-263` | Add `HARD_CONNECTION_KWS`; keep `TRANSIENT_KWS` for soft errors |
| `agent/dispatch.py:call_llm_raw` | Distinguish retry count for hard vs soft errors; add `_FALLBACK_MODEL` + retry |
| `agent/loop.py:_call_openai_tier` | Hard connection error → max 1 retry, then break (skip remaining 3 attempts) |
| `agent/loop.py:_call_llm` | After all tiers return None → retry once with `MODEL_FALLBACK` |
| `agent/contract_models.py` | Add `blocking_objections: list[str]` to `EvaluatorResponse` |
| `agent/contract_phase.py:283` | Consensus check: `response.agreed and not response.blocking_objections` |
| `data/prompts/default/evaluator_contract.md` | Document `blocking_objections` vs `objections` distinction |
| `.env.example` | Add `MODEL_FALLBACK` |
| `tests/test_dispatch_transient.py` | New: hard error retry limits + fallback tests |
| `tests/test_contract_phase.py` | Add: caveat-notes don't block consensus; real blockers do |

---

## Task 1: FIX-416 — HARD_CONNECTION_KWS with 1-retry limit

**Files:**
- Modify: `agent/dispatch.py:258-263`
- Modify: `agent/loop.py:_call_openai_tier` (~line 301)
- Test: `tests/test_dispatch_transient.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_dispatch_transient.py
from agent.dispatch import TRANSIENT_KWS, HARD_CONNECTION_KWS


def test_broken_pipe_in_hard_connection_kws():
    err = "[Errno 32] Broken pipe"
    assert any(kw.lower() in err.lower() for kw in HARD_CONNECTION_KWS)


def test_rate_limit_still_in_transient_kws():
    assert any(kw in "429" for kw in TRANSIENT_KWS)


def test_broken_pipe_not_in_transient_kws():
    """Hard errors are NOT in TRANSIENT_KWS to avoid the 3-retry loop."""
    assert not any(kw in "broken pipe" for kw in TRANSIENT_KWS)
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_dispatch_transient.py -v
```
Expected: FAIL (`HARD_CONNECTION_KWS` doesn't exist yet)

- [ ] **Step 3: Add HARD_CONNECTION_KWS in dispatch.py**

Find in `agent/dispatch.py` (around line 256):
```python
# Transient error keywords — single source of truth; imported by loop.py
# FIX-215: added timeout/timed out/connection reset — httpx/OpenAI timeouts should retry
TRANSIENT_KWS = (
    "503", "502", "429", "NoneType", "overloaded",
    "unavailable", "server error", "rate limit", "rate-limit",
    "timeout", "timed out", "connection reset", "read timeout",
    "apitimeouterror", "connecttimeout", "readtimeout",
)
```

Replace with:
```python
# Transient error keywords — single source of truth; imported by loop.py
# FIX-215: added timeout/timed out/connection reset — httpx/OpenAI timeouts should retry
TRANSIENT_KWS = (
    "503", "502", "429", "NoneType", "overloaded",
    "unavailable", "server error", "rate limit", "rate-limit",
    "timeout", "timed out", "connection reset", "read timeout",
    "apitimeouterror", "connecttimeout", "readtimeout",
)

# FIX-416: hard connection errors — not retried 3 times like soft transients.
# These indicate the socket is dead; one immediate retry is sufficient before
# falling through to MODEL_FALLBACK. Kept separate so loop.py can cap retries at 1.
HARD_CONNECTION_KWS = (
    "broken pipe", "errno 32", "connection aborted",
    "connection refused", "remotedisconnected", "incompleteread",
)
```

- [ ] **Step 4: Update _call_openai_tier in loop.py to cap hard errors at 1 retry**

Find in `agent/loop.py` inside `_call_openai_tier` (around line 320):
```python
        except Exception as e:
            err_str = str(e)
            is_transient = any(kw.lower() in err_str.lower() for kw in TRANSIENT_KWS)
            if is_transient and attempt < 3:
                print(f"{CLI_YELLOW}[{label}] Transient error (attempt {attempt + 1}): {e} — retrying in 4s{CLI_CLR}")
                time.sleep(4)
                continue
            print(f"{CLI_RED}[{label}] Error: {e}{CLI_CLR}")
            break
```

Replace with:
```python
        except Exception as e:
            err_str = str(e)
            # FIX-416: hard connection errors (broken pipe etc.) get 1 retry max.
            # Soft transient errors (429, 503) keep the existing 3-retry behaviour.
            is_hard = any(kw.lower() in err_str.lower() for kw in HARD_CONNECTION_KWS)
            is_transient = any(kw.lower() in err_str.lower() for kw in TRANSIENT_KWS)
            max_attempt = 1 if is_hard else 3
            if (is_hard or is_transient) and attempt < max_attempt:
                delay = 2 if is_hard else 4
                print(f"{CLI_YELLOW}[{label}] {'Hard connection' if is_hard else 'Transient'} error "
                      f"(attempt {attempt + 1}): {e} — retrying in {delay}s{CLI_CLR}")
                time.sleep(delay)
                continue
            print(f"{CLI_RED}[{label}] Error: {e}{CLI_CLR}")
            break
```

Also update the same pattern in the **Anthropic SDK tier** in `_call_llm` (around line 453):
```python
            except Exception as e:
                err_str = str(e)
                is_transient = any(kw.lower() in err_str.lower() for kw in TRANSIENT_KWS)
                if is_transient and attempt < 3:
                    print(f"{CLI_YELLOW}[Anthropic] Transient error (attempt {attempt + 1}): {e} — retrying in 4s{CLI_CLR}")
                    time.sleep(4)
                    continue
                print(f"{CLI_RED}[Anthropic] Error: {e}{CLI_CLR}")
                break
```

Replace with:
```python
            except Exception as e:
                err_str = str(e)
                # FIX-416: hard connection errors capped at 1 retry
                is_hard = any(kw.lower() in err_str.lower() for kw in HARD_CONNECTION_KWS)
                is_transient = any(kw.lower() in err_str.lower() for kw in TRANSIENT_KWS)
                max_attempt = 1 if is_hard else 3
                if (is_hard or is_transient) and attempt < max_attempt:
                    delay = 2 if is_hard else 4
                    print(f"{CLI_YELLOW}[Anthropic] {'Hard connection' if is_hard else 'Transient'} error "
                          f"(attempt {attempt + 1}): {e} — retrying in {delay}s{CLI_CLR}")
                    time.sleep(delay)
                    continue
                print(f"{CLI_RED}[Anthropic] Error: {e}{CLI_CLR}")
                break
```

Also add `HARD_CONNECTION_KWS` to the import block at the top of `agent/loop.py`:
```python
from .dispatch import (
    CLI_RED, CLI_GREEN, CLI_CLR, CLI_YELLOW, CLI_BLUE,
    anthropic_client, openrouter_client, ollama_client,
    get_anthropic_model_id,
    get_provider,
    is_ollama_model,
    dispatch,
    probe_structured_output, get_response_format,
    TRANSIENT_KWS, HARD_CONNECTION_KWS,  # FIX-416
    _THINK_RE,
    _CC_ENABLED,
)
```

Also apply the same `is_hard` / `max_attempt` pattern to `call_llm_raw` in `dispatch.py` — it has the same per-tier retry loops (Anthropic, OpenRouter, Ollama). Each `except Exception as e` block inside `call_llm_raw` gets the same replacement.

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_dispatch_transient.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add agent/dispatch.py agent/loop.py tests/test_dispatch_transient.py
git commit -m "fix(dispatch): add HARD_CONNECTION_KWS with 1-retry cap for broken-pipe errors (FIX-416)"
```

---

## Task 2: FIX-417 — MODEL_FALLBACK after all tiers fail

**Files:**
- Modify: `agent/dispatch.py` (add `_FALLBACK_MODEL`; wrap `call_llm_raw`)
- Modify: `agent/loop.py:_call_llm` (fallback after Ollama tier)
- Modify: `.env.example`
- Test: `tests/test_dispatch_transient.py` (extend)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_dispatch_transient.py`:
```python
import os
from unittest.mock import patch, call as mcall


def test_call_llm_raw_falls_back_on_total_failure(monkeypatch):
    """When all tiers return None, call_llm_raw retries with MODEL_FALLBACK."""
    monkeypatch.setenv("MODEL_FALLBACK", "fallback-model:test")

    results = iter([None, '{"type": "lookup"}'])

    def fake_single(system, user_msg, model, cfg, **kwargs):
        return next(results)

    # Reload to pick up MODEL_FALLBACK env var
    import importlib
    import agent.dispatch as disp
    importlib.reload(disp)

    with patch.object(disp, "_call_raw_single_model", side_effect=fake_single) as mock:
        result = disp.call_llm_raw(
            "sys", "user", "primary-model:test", {}, max_tokens=10,
        )

    assert result == '{"type": "lookup"}'
    assert mock.call_count == 2
    # Second call uses fallback model
    assert mock.call_args_list[1][0][2] == "fallback-model:test"


def test_call_llm_raw_no_fallback_when_unset(monkeypatch):
    """MODEL_FALLBACK not set → single attempt, returns None on failure."""
    monkeypatch.delenv("MODEL_FALLBACK", raising=False)

    import importlib
    import agent.dispatch as disp
    importlib.reload(disp)

    with patch.object(disp, "_call_raw_single_model", return_value=None) as mock:
        result = disp.call_llm_raw("sys", "user", "primary:test", {}, max_tokens=10)

    assert result is None
    assert mock.call_count == 1
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_dispatch_transient.py::test_call_llm_raw_falls_back_on_total_failure \
              tests/test_dispatch_transient.py::test_call_llm_raw_no_fallback_when_unset -v
```
Expected: FAIL (`_call_raw_single_model` doesn't exist)

- [ ] **Step 3: Extract _call_raw_single_model in dispatch.py**

In `agent/dispatch.py`, immediately before `call_llm_raw`:

1. Rename the current `call_llm_raw` function body to `_call_raw_single_model`. Its signature is identical to `call_llm_raw`. No logic changes inside.

2. Add the new `_FALLBACK_MODEL` constant right after `HARD_CONNECTION_KWS`:
```python
# FIX-417: fallback model used when all tiers of primary model fail completely.
# Set MODEL_FALLBACK to any supported model string (same format as MODEL_DEFAULT).
_FALLBACK_MODEL = os.environ.get("MODEL_FALLBACK", "")
```

3. Add the new thin `call_llm_raw` wrapper:
```python
def call_llm_raw(
    system: str,
    user_msg: str,
    model: str,
    cfg: dict,
    max_tokens: int = 20,
    think: bool | None = None,
    max_retries: int = 3,
    plain_text: bool = False,
    token_out: dict | None = None,
    logprobs: bool = False,
) -> str | None:
    """Call LLM with MODEL_FALLBACK retry (FIX-417). Primary model through all tiers first."""
    result = _call_raw_single_model(
        system, user_msg, model, cfg,
        max_tokens=max_tokens, think=think, max_retries=max_retries,
        plain_text=plain_text, token_out=token_out, logprobs=logprobs,
    )
    if result is None and _FALLBACK_MODEL and _FALLBACK_MODEL != model:
        print(f"[dispatch] Primary exhausted — retrying with MODEL_FALLBACK={_FALLBACK_MODEL}")
        result = _call_raw_single_model(
            system, user_msg, _FALLBACK_MODEL, {},
            max_tokens=max_tokens, think=think, max_retries=1,
            plain_text=plain_text, token_out=token_out, logprobs=logprobs,
        )
    return result
```

- [ ] **Step 4: Add MODEL_FALLBACK retry to loop._call_llm**

In `agent/loop.py`, add `_FALLBACK_MODEL` to the dispatch import block:
```python
from .dispatch import (
    ...
    TRANSIENT_KWS, HARD_CONNECTION_KWS,
    _FALLBACK_MODEL,   # FIX-417
    _THINK_RE,
    _CC_ENABLED,
)
```

At the very bottom of `_call_llm`, replace the existing:
```python
    return _call_openai_tier(
        ollama_client, ollama_model, log,
        None,
        "Ollama",
        extra_body=extra if extra else None,
        response_format=get_response_format("json_object"),
    )
```

With:
```python
    ollama_result = _call_openai_tier(
        ollama_client, ollama_model, log,
        None,
        "Ollama",
        extra_body=extra if extra else None,
        response_format=get_response_format("json_object"),
    )
    if ollama_result[0] is not None:
        return ollama_result

    # FIX-417: all tiers failed — one attempt with MODEL_FALLBACK
    if _FALLBACK_MODEL and _FALLBACK_MODEL != model:
        print(f"{CLI_YELLOW}[loop] All tiers failed — retrying with MODEL_FALLBACK={_FALLBACK_MODEL}{CLI_CLR}")
        return _call_llm(log, _FALLBACK_MODEL, max_tokens, {})

    return None, 0, 0, 0, 0, 0, 0, 0, 0
```

- [ ] **Step 5: Document in .env.example**

In `.env.example`, find the models section and add after `MODEL_CONTRACT`:
```
# MODEL_FALLBACK=                    # FIX-417: резервная модель когда все тиры основной упали
#                                    # Пример: anthropic/claude-haiku-4.5 или qwen3.5:cloud
#                                    # Один повтор. Не каскадирует дальше.
```

- [ ] **Step 6: Run all dispatch tests**

```bash
uv run pytest tests/test_dispatch_transient.py -v
```
Expected: PASS (5 tests)

- [ ] **Step 7: Commit**

```bash
git add agent/dispatch.py agent/loop.py .env.example tests/test_dispatch_transient.py
git commit -m "feat(dispatch): MODEL_FALLBACK retry after all tiers fail (FIX-417)"
```

---

## Task 3: FIX-418 — blocking_objections in EvaluatorResponse

**Files:**
- Modify: `agent/contract_models.py`
- Modify: `agent/contract_phase.py:283`
- Modify: `data/prompts/default/evaluator_contract.md`
- Test: `tests/test_contract_phase.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_contract_phase.py`:
```python
@patch("agent.contract_phase.call_llm_raw")
def test_caveat_notes_do_not_block_consensus(mock_llm):
    """agreed=True + objections with confirmations + blocking_objections=[]
    → consensus reached in round 1, not max_rounds."""
    mock_llm.side_effect = [
        _make_executor_json(agreed=True),
        json.dumps({
            "success_criteria": ["article found"],
            "failure_conditions": [],
            "required_evidence": ["/01_capture/influential/"],
            "objections": [
                "Date math verified: 14 days before 2026-03-23 = 2026-03-09 ✓",
                "Plan correctly anchors to VAULT_DATE_LOWER_BOUND ✓",
            ],
            "blocking_objections": [],
            "counter_proposal": None,
            "agreed": True,
        }),
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _, rounds = negotiate_contract(
        task_text="What article did I capture 14 days ago?",
        task_type="lookup",
        agents_md="", wiki_context="", graph_context="",
        model="m", cfg={}, max_rounds=3,
    )
    assert contract.is_default is False
    assert contract.rounds_taken == 1
    assert len(rounds) == 1


@patch("agent.contract_phase.call_llm_raw")
def test_blocking_objections_require_extra_round(mock_llm):
    """blocking_objections non-empty → round 1 not accepted, round 2 is."""
    mock_llm.side_effect = [
        _make_executor_json(agreed=True),
        json.dumps({
            "success_criteria": ["article found"],
            "failure_conditions": [],
            "required_evidence": [],
            "objections": [],
            "blocking_objections": ["Missing explicit date calculation step before search"],
            "counter_proposal": None,
            "agreed": True,
        }),
        _make_executor_json(agreed=True, steps=[
            "compute target date: 14 days before 2026-03-23 = 2026-03-09",
            "list /01_capture/influential",
            "filter by date prefix 2026-03-09",
            "report_completion with found article",
        ]),
        _make_evaluator_json(agreed=True),
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _, rounds = negotiate_contract(
        task_text="What article did I capture 14 days ago?",
        task_type="lookup",
        agents_md="", wiki_context="", graph_context="",
        model="m", cfg={}, max_rounds=3,
    )
    assert contract.rounds_taken == 2
    assert contract.is_default is False
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_contract_phase.py::test_caveat_notes_do_not_block_consensus \
              tests/test_contract_phase.py::test_blocking_objections_require_extra_round -v
```
Expected: FAIL (`blocking_objections` field not in `EvaluatorResponse`)

- [ ] **Step 3: Add blocking_objections to EvaluatorResponse**

In `agent/contract_models.py`, change:
```python
class EvaluatorResponse(BaseModel):
    success_criteria: list[str]
    failure_conditions: list[str]
    required_evidence: list[str]
    objections: list[str]
    counter_proposal: str | None = None
    agreed: bool
```

To:
```python
class EvaluatorResponse(BaseModel):
    success_criteria: list[str]
    failure_conditions: list[str]
    required_evidence: list[str]
    objections: list[str]                                          # non-blocking: notes, caveats, confirmations
    blocking_objections: list[str] = Field(default_factory=list)  # FIX-418: true plan-blockers only
    counter_proposal: str | None = None
    agreed: bool
```

- [ ] **Step 4: Update consensus check in contract_phase.py**

Find in `agent/contract_phase.py` (around line 283):
```python
        # FIX-406: partial consensus — evaluator is authority on success criteria.
        # FIX-415: track evaluator-only flag and filter mutation_scope on forbidden paths.
        evaluator_accepts = response.agreed and not response.objections
```

Replace with:
```python
        # FIX-406: partial consensus — evaluator is authority on success criteria.
        # FIX-415: track evaluator-only flag and filter mutation_scope on forbidden paths.
        # FIX-418: blocking_objections are true blockers; objections are non-blocking notes.
        evaluator_accepts = response.agreed and not response.blocking_objections
```

- [ ] **Step 5: Update evaluator_contract.md prompt**

Replace the full content of `data/prompts/default/evaluator_contract.md` with:
```markdown
You are an EvaluatorAgent for a personal knowledge vault task.
Your role: review the executor's plan and define verifiable success criteria.

VAULT CONTEXT:
- Vault structure is discovered at runtime. Plans must not hardcode paths.
- Task is complete only if the described action was taken on the correct vault path.

COMMON FAILURE CONDITIONS:
- No action taken (task abandoned or clarification requested without good reason).
- Wrong path modified (side effects outside the intended scope).
- Truncated task description misinterpreted.

TWO OBJECTION FIELDS — use them correctly:
- `blocking_objections`: ONLY true plan-blockers that require another negotiation round.
  Examples: missing required step, wrong target path, incorrect date calculation.
  If non-empty, consensus is NOT reached even when agreed=true.
- `objections`: non-blocking notes, caveats, or confirmations.
  Examples: "date math verified ✓", "plan correctly uses VAULT_DATE_LOWER_BOUND ✓".
  These do NOT affect consensus. Leave `blocking_objections` empty when plan is correct.

When the plan is correct and you agree: set agreed=true, put verification notes in
`objections`, leave `blocking_objections` as [].

Respond with ONLY valid JSON. No text before or after the JSON object.
{
  "success_criteria": ["criterion 1"],
  "failure_conditions": ["condition 1"],
  "required_evidence": [],
  "objections": [],
  "blocking_objections": [],
  "agreed": false
}
```

- [ ] **Step 6: Run all contract tests**

```bash
uv run pytest tests/test_contract_phase.py tests/test_contract_models.py -v
```
Expected: PASS (all existing + 2 new tests)

- [ ] **Step 7: Commit**

```bash
git add agent/contract_models.py agent/contract_phase.py \
        data/prompts/default/evaluator_contract.md \
        tests/test_contract_phase.py
git commit -m "feat(contract): blocking_objections field; caveats no longer stall consensus (FIX-418)"
```

---

## Self-Review

**Spec coverage:**
- Broken pipe retried (max 1 attempt) → FIX-416, Task 1 ✓
- MODEL_FALLBACK after all tiers fail → FIX-417, Task 2 ✓
- blocking_objections vs notes → FIX-418, Task 3 ✓

**No placeholders:** All code is complete and runnable.

**Type consistency:**
- `HARD_CONNECTION_KWS` defined in `dispatch.py`, imported in `loop.py` Tasks 1 and 2.
- `_FALLBACK_MODEL` defined in `dispatch.py`, imported in `loop.py` Task 2.
- `blocking_objections: list[str]` consistent across `contract_models.py`, `contract_phase.py`, prompt, and tests.

**Backward compat:**
- `HARD_CONNECTION_KWS` is additive; existing `TRANSIENT_KWS` unchanged.
- `blocking_objections` defaults to `[]` — existing callers pass only `objections`, Pydantic fills the default.
- `_FALLBACK_MODEL` defaults to `""` (no-op when unset).
- `_make_evaluator_json` in tests doesn't include `blocking_objections` → Pydantic default `[]` → existing tests unaffected.
