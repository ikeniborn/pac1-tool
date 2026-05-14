# OLLAMA_API_KEY Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Read `OLLAMA_API_KEY` from env and pass it to the Ollama OpenAI client, falling back to `"ollama"` when absent or empty.

**Architecture:** One-line change in `agent/llm.py` at module init (line 87). Two env example files get documentation comments. No signature changes, no new modules.

**Tech Stack:** Python, python-dotenv-style `_load_secrets`, `openai.OpenAI`

---

## File Map

| File | Change |
|------|--------|
| `agent/llm.py` | Add `_OLLAMA_KEY` constant; pass to `OpenAI(api_key=...)` |
| `.env.example` | Add `OLLAMA_API_KEY=` line (doc only, no value) |
| `.secrets.example` | Add `# OLLAMA_API_KEY=sk-...` comment line |
| `tests/test_llm_module.py` | Add unit test for `_OLLAMA_KEY` fallback logic |

---

### Task 1: Unit test for `_OLLAMA_KEY` fallback

**Files:**
- Modify: `tests/test_llm_module.py`

- [ ] **Step 1: Write the failing test**

If `import os` is absent from the top of `tests/test_llm_module.py`, prepend it as the first line of the file.

Then append to `tests/test_llm_module.py`:

```python
def test_ollama_key_constant_exists_and_fallback():
    """_OLLAMA_KEY attribute must exist on module and use or-fallback logic."""
    import os
    import agent.llm as llm_mod

    # Attribute must exist — fails before Task 2 implementation
    assert hasattr(llm_mod, "_OLLAMA_KEY"), "_OLLAMA_KEY not defined in agent.llm"

    # Value must match or-fallback of current env
    expected = os.environ.get("OLLAMA_API_KEY") or "ollama"
    assert llm_mod._OLLAMA_KEY == expected
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/ikeniborn/Documents/Project/ecom1-agent
uv run pytest tests/test_llm_module.py::test_ollama_key_constant_exists_and_fallback -v
```

Expected: FAIL with `AssertionError: _OLLAMA_KEY not defined in agent.llm`

- [ ] **Step 3: Commit failing test**

```bash
git add tests/test_llm_module.py
git commit -m "test: OLLAMA_API_KEY — _OLLAMA_KEY must exist with or-fallback to 'ollama'"
```

---

### Task 2: Implement `_OLLAMA_KEY` in `agent/llm.py`

**Files:**
- Modify: `agent/llm.py:46-47` (constants block after `_OLLAMA_URL`)

- [ ] **Step 1: Replace hardcoded `"ollama"` with env-based constant**

In `agent/llm.py`, current line 46–47:

```python
_OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
_CC_ENABLED = os.environ.get("CC_ENABLED") == "1"  # Claude Code tier (iclaude subprocess)
```

Replace with:

```python
_OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
_OLLAMA_KEY = os.environ.get("OLLAMA_API_KEY") or "ollama"
_CC_ENABLED = os.environ.get("CC_ENABLED") == "1"  # Claude Code tier (iclaude subprocess)
```

Then update line 87 (the `ollama_client` instantiation):

```python
# was:
ollama_client = OpenAI(base_url=_OLLAMA_URL, api_key="ollama", timeout=_HTTP_TIMEOUT)

# becomes:
ollama_client = OpenAI(base_url=_OLLAMA_URL, api_key=_OLLAMA_KEY, timeout=_HTTP_TIMEOUT)
```

- [ ] **Step 2: Run tests — failing test must now pass**

```bash
uv run pytest tests/test_llm_module.py -v
```

Expected: all tests PASS including `test_ollama_key_constant_exists_and_fallback`.

- [ ] **Step 3: Commit**

```bash
git add agent/llm.py
git commit -m "feat: read OLLAMA_API_KEY from env; fallback 'ollama' when absent or empty"
```

---

### Task 3: Document in `.env.example` and `.secrets.example`

**Files:**
- Modify: `.env.example`
- Modify: `.secrets.example`

- [ ] **Step 1: Add `OLLAMA_API_KEY=` to `.env.example`**

Find the `OLLAMA_BASE_URL` line in `.env.example` (currently line 27). Insert the following **immediately after** it:

```
OLLAMA_API_KEY=           # ключ для OpenAI-совместимого прокси (пусто = "ollama"); значение — только в .secrets
```

Result block should look like:

```
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_API_KEY=           # ключ для OpenAI-совместимого прокси (пусто = "ollama"); значение — только в .secrets
```

- [ ] **Step 2: Add commented key to `.secrets.example`**

`.secrets.example` currently ends with:

```
# ─── BitGN (api.bitgn.com) ───────────────────────────────────────────────────
# BITGN_API_KEY=...
```

Append the following block **after the last line of the file**:

```
# ─── Ollama / OpenAI-compatible proxy ────────────────────────────────────────
# OLLAMA_API_KEY=sk-...
```

- [ ] **Step 3: Verify no tests broken**

```bash
uv run pytest tests/ -v --tb=short -q
```

Expected: all pass (config files don't affect tests).

- [ ] **Step 4: Commit**

```bash
git add .env.example .secrets.example
git commit -m "docs: document OLLAMA_API_KEY in .env.example and .secrets.example"
```

---

## Verification Checklist

After all tasks complete:

- [ ] `uv run pytest tests/test_llm_module.py -v` — all pass
- [ ] `grep "_OLLAMA_KEY" agent/llm.py` — returns `_OLLAMA_KEY = os.environ.get("OLLAMA_API_KEY") or "ollama"` and `api_key=_OLLAMA_KEY`
- [ ] `grep "OLLAMA_API_KEY" .env.example .secrets.example` — both files contain the line
- [ ] No other files modified

### Manual integration tests (spec §Тестирование п.1–3)

**§1 — без ключа, локальный Ollama** (требует запущенного Ollama и `MODEL` указывающего на Ollama-модель):

```bash
make task TASKS='t01'
```

Expected: задача завершается штатно, поведение идентично текущему.

### Manual integration test (spec §Тестирование п.2)

This step requires access to an OpenAI-compatible proxy with a real key. Run only if such a proxy is available:

```bash
MODEL=qwen3:latest OLLAMA_BASE_URL=https://<vps>/v1 OLLAMA_API_KEY=sk-... make task TASKS='t01'
```

Expected: task completes. Confirm `Authorization: Bearer sk-...` header is sent by checking proxy logs or using `LOG_LEVEL=DEBUG`.

Wrong key control check:

```bash
MODEL=qwen3:latest OLLAMA_BASE_URL=https://<vps>/v1 OLLAMA_API_KEY=sk-wrong make task TASKS='t01'
```

Expected: `[Ollama] Error: AuthenticationError ...` in output, no retry, pipeline returns failure result (not a crash).
