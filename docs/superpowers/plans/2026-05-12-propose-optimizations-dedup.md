# propose_optimizations: Context-Aware Deduplication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pass existing security gates and prompt content to LLM synthesizers so they can skip duplicates, matching the existing pattern in `_synthesize_rule`.

**Architecture:** Add two helper functions (`_existing_security_text`, `_existing_prompts_text`), extend two synthesizer signatures with the new context param, update system prompts with null-on-duplicate instruction, load context once in `main()` before the loop.

**Tech Stack:** Python, PyYAML, existing `agent.llm.call_llm_raw`

---

## File Map

| File | Change |
|---|---|
| `scripts/propose_optimizations.py` | Add 2 helpers, modify 2 function signatures + prompts, update `main()` |
| `tests/test_propose_optimizations.py` | Add tests for new helpers + verify new args passed to synthesizers |

---

### Task 1: Tests for `_existing_security_text()`

**Files:**
- Modify: `tests/test_propose_optimizations.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_propose_optimizations.py`:

```python
def test_existing_security_text_returns_id_message(tmp_path):
    sec_dir = tmp_path / "security"
    sec_dir.mkdir()
    (sec_dir / "sec-001.yaml").write_text(
        "id: sec-001\naction: block\nmessage: DDL prohibited\n"
    )
    (sec_dir / "sec-002.yaml").write_text(
        "id: sec-002\ncheck: no_where_clause\naction: block\nmessage: Full scan prohibited\n"
    )
    with patch.object(po, "_SECURITY_DIR", sec_dir):
        result = po._existing_security_text()
    assert "sec-001: DDL prohibited" in result
    assert "sec-002: Full scan prohibited" in result


def test_existing_security_text_skips_invalid(tmp_path):
    sec_dir = tmp_path / "security"
    sec_dir.mkdir()
    (sec_dir / "bad.yaml").write_text("not: valid: yaml: [")
    (sec_dir / "no-msg.yaml").write_text("id: sec-003\naction: block\n")
    with patch.object(po, "_SECURITY_DIR", sec_dir):
        result = po._existing_security_text()
    assert result == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_propose_optimizations.py::test_existing_security_text_returns_id_message tests/test_propose_optimizations.py::test_existing_security_text_skips_invalid -v
```

Expected: `AttributeError: module 'scripts.propose_optimizations' has no attribute '_existing_security_text'`

---

### Task 2: Implement `_existing_security_text()`

**Files:**
- Modify: `scripts/propose_optimizations.py`

- [ ] **Step 1: Add helper after `_existing_rules_text()`** (after line 60)

```python
def _existing_security_text() -> str:
    parts = []
    for f in sorted(_SECURITY_DIR.glob("*.yaml")):
        try:
            r = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(r, dict) and r.get("id") and r.get("message"):
                parts.append(f"- {r['id']}: {r['message']}")
        except Exception:
            pass
    return "\n".join(parts)
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
uv run pytest tests/test_propose_optimizations.py::test_existing_security_text_returns_id_message tests/test_propose_optimizations.py::test_existing_security_text_skips_invalid -v
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add scripts/propose_optimizations.py tests/test_propose_optimizations.py
git commit -m "feat: add _existing_security_text helper"
```

---

### Task 3: Tests for `_existing_prompts_text()`

**Files:**
- Modify: `tests/test_propose_optimizations.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_existing_prompts_text_returns_full_content(tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "answer.md").write_text("# Answer\n\nDo X.\n")
    (prompts_dir / "sql_plan.md").write_text("# SQL Plan\n\nDo Y.\n")
    optimized_dir = prompts_dir / "optimized"
    optimized_dir.mkdir()
    (optimized_dir / "2026-05-12-01-answer.md").write_text("## Extra\nShould not appear.\n")
    with patch.object(po, "_PROMPTS_DIR", prompts_dir):
        result = po._existing_prompts_text()
    assert "=== answer.md ===" in result
    assert "Do X." in result
    assert "=== sql_plan.md ===" in result
    assert "Do Y." in result
    assert "Should not appear" not in result


def test_existing_prompts_text_empty_dir(tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    with patch.object(po, "_PROMPTS_DIR", prompts_dir):
        result = po._existing_prompts_text()
    assert result == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_propose_optimizations.py::test_existing_prompts_text_returns_full_content tests/test_propose_optimizations.py::test_existing_prompts_text_empty_dir -v
```

Expected: `AttributeError: module ... has no attribute '_existing_prompts_text'` and `AttributeError: ... '_PROMPTS_DIR'`

---

### Task 4: Implement `_existing_prompts_text()` + add `_PROMPTS_DIR`

**Files:**
- Modify: `scripts/propose_optimizations.py`

- [ ] **Step 1: Add `_PROMPTS_DIR` constant** (after line 22, alongside existing path constants)

Current line 22:
```python
_PROMPTS_OPTIMIZED_DIR = _ROOT / "data" / "prompts" / "optimized"
```

Add after it:
```python
_PROMPTS_DIR = _ROOT / "data" / "prompts"
```

- [ ] **Step 2: Add helper after `_existing_security_text()`**

```python
def _existing_prompts_text() -> str:
    parts = []
    for f in sorted(_PROMPTS_DIR.glob("*.md")):
        try:
            content = f.read_text(encoding="utf-8")
            parts.append(f"=== {f.name} ===\n{content}")
        except Exception:
            pass
    return "\n".join(parts)
```

- [ ] **Step 3: Run tests to verify they pass**

```bash
uv run pytest tests/test_propose_optimizations.py::test_existing_prompts_text_returns_full_content tests/test_propose_optimizations.py::test_existing_prompts_text_empty_dir -v
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/propose_optimizations.py tests/test_propose_optimizations.py
git commit -m "feat: add _existing_prompts_text helper and _PROMPTS_DIR constant"
```

---

### Task 5: Tests that synthesizers receive context args

**Files:**
- Modify: `tests/test_propose_optimizations.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_synthesize_security_gate_receives_existing_context(tmp_path):
    eval_log, rules_dir, security_dir, prom_dir, processed = _setup(tmp_path)
    _write_eval_log(eval_log, [_eval_entry(security_opts=["Add gate for UNION SELECT"])])

    gate_spec = {"pattern": "UNION.*SELECT", "check": None, "message": "UNION SELECT prohibited"}
    patches = _base_patches(eval_log, rules_dir, security_dir, prom_dir, processed)
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], \
         patch.object(po, "_synthesize_rule", return_value=None), \
         patch.object(po, "_synthesize_security_gate", return_value=gate_spec) as mock_sec, \
         patch.object(po, "_synthesize_prompt_patch", return_value=None), \
         patch.object(po, "_existing_security_text", return_value="- sec-001: DDL prohibited"):
        po.main(dry_run=False)

    args = mock_sec.call_args
    assert args[0][1] == "- sec-001: DDL prohibited"


def test_synthesize_prompt_patch_receives_existing_context(tmp_path):
    eval_log, rules_dir, security_dir, prom_dir, processed = _setup(tmp_path)
    _write_eval_log(eval_log, [_eval_entry(prompt_opts=["answer.md: add grounding rule"])])

    patch_result = {"target_file": "answer.md", "content": "## Guard\nNever X."}
    patches = _base_patches(eval_log, rules_dir, security_dir, prom_dir, processed)
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], \
         patch.object(po, "_synthesize_rule", return_value=None), \
         patch.object(po, "_synthesize_security_gate", return_value=None), \
         patch.object(po, "_synthesize_prompt_patch", return_value=patch_result) as mock_prompt, \
         patch.object(po, "_existing_prompts_text", return_value="=== answer.md ===\n# Answer\n"):
        po.main(dry_run=False)

    args = mock_prompt.call_args
    assert args[0][1] == "=== answer.md ===\n# Answer\n"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_propose_optimizations.py::test_synthesize_security_gate_receives_existing_context tests/test_propose_optimizations.py::test_synthesize_prompt_patch_receives_existing_context -v
```

Expected: FAIL — args[0][1] will not match (context not yet passed)

---

### Task 6: Update `_synthesize_security_gate` signature and system prompt

**Files:**
- Modify: `scripts/propose_optimizations.py`

Current signature (line 96):
```python
def _synthesize_security_gate(raw_rec: str, model: str, cfg: dict) -> dict | None:
```

Current system prompt (lines 100-105):
```python
    system = (
        "Convert the security recommendation into a gate spec. "
        "Return JSON: {\"pattern\": \"<regex or null>\", \"check\": \"<name or null>\", \"message\": \"<block reason>\"}. "
        "Exactly one of pattern or check must be non-null. "
        "If not blockable as a regex/check, return exactly: null"
    )
```

- [ ] **Step 1: Update function signature and system prompt**

Replace the entire function definition:

```python
def _synthesize_security_gate(raw_rec: str, existing_security_md: str, model: str, cfg: dict) -> dict | None:
    from agent.llm import call_llm_raw
    from agent.json_extract import _extract_json_from_text

    system = (
        "Convert the security recommendation into a gate spec. "
        "Return JSON: {\"pattern\": \"<regex or null>\", \"check\": \"<name or null>\", \"message\": \"<block reason>\"}. "
        "Exactly one of pattern or check must be non-null. "
        "If not blockable as a regex/check, return exactly: null\n"
        "If the recommendation is already fully covered by an existing gate, respond with exactly: null\n\n"
        f"Existing gates:\n{existing_security_md}"
    )
    result = call_llm_raw(system, f"Security recommendation:\n{raw_rec}",
                          model, cfg, max_tokens=256)
    if not result:
        return None
    result = result.strip()
    if result.lower() == "null":
        return None
    parsed = _extract_json_from_text(result)
    if not isinstance(parsed, dict) or not parsed.get("message"):
        return None
    if not parsed.get("pattern") and not parsed.get("check"):
        return None
    return parsed
```

---

### Task 7: Update `_synthesize_prompt_patch` signature and system prompt

**Files:**
- Modify: `scripts/propose_optimizations.py`

Current signature (line 121):
```python
def _synthesize_prompt_patch(raw_rec: str, model: str, cfg: dict) -> dict | None:
```

Current system prompt (lines 125-129):
```python
    system = (
        "Convert the prompt optimization recommendation into a markdown rule block. "
        "Return JSON: {\"target_file\": \"<basename e.g. answer.md>\", \"content\": \"<markdown section starting with ## heading>\"}. "
        "If too vague to produce a concrete rule, return exactly: null"
    )
```

- [ ] **Step 1: Update function signature and system prompt**

Replace the entire function definition:

```python
def _synthesize_prompt_patch(raw_rec: str, existing_prompts_md: str, model: str, cfg: dict) -> dict | None:
    from agent.llm import call_llm_raw
    from agent.json_extract import _extract_json_from_text

    system = (
        "Convert the prompt optimization recommendation into a markdown rule block. "
        "Return JSON: {\"target_file\": \"<basename e.g. answer.md>\", \"content\": \"<markdown section starting with ## heading>\"}. "
        "If too vague to produce a concrete rule, return exactly: null\n"
        "If the recommendation is already present in the existing prompt content, respond with exactly: null\n\n"
        f"Existing prompt files:\n{existing_prompts_md}"
    )
    result = call_llm_raw(system, f"Prompt recommendation:\n{raw_rec}",
                          model, cfg, max_tokens=512)
    if not result:
        return None
    result = result.strip()
    if result.lower() == "null":
        return None
    parsed = _extract_json_from_text(result)
    if not isinstance(parsed, dict):
        return None
    if not parsed.get("target_file") or not parsed.get("content"):
        return None
    return parsed
```

---

### Task 8: Update `main()` to load context and pass to synthesizers

**Files:**
- Modify: `scripts/propose_optimizations.py`

- [ ] **Step 1: Load context once before loop**

Current `main()` around line 205:
```python
    rules_md = _existing_rules_text()
    new_processed = set(processed)
```

Replace with:
```python
    rules_md = _existing_rules_text()
    security_md = _existing_security_text()
    prompts_md = _existing_prompts_text()
    new_processed = set(processed)
```

- [ ] **Step 2: Update `_synthesize_security_gate` call site**

Current (around line 234):
```python
            gate_spec = _synthesize_security_gate(raw_rec, model, cfg)
```

Replace with:
```python
            gate_spec = _synthesize_security_gate(raw_rec, security_md, model, cfg)
```

- [ ] **Step 3: Update `_synthesize_prompt_patch` call site**

Current (around line 253):
```python
            patch_result = _synthesize_prompt_patch(raw_rec, model, cfg)
```

Replace with:
```python
            patch_result = _synthesize_prompt_patch(raw_rec, prompts_md, model, cfg)
```

- [ ] **Step 4: Run new tests to verify they pass**

```bash
uv run pytest tests/test_propose_optimizations.py::test_synthesize_security_gate_receives_existing_context tests/test_propose_optimizations.py::test_synthesize_prompt_patch_receives_existing_context -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest tests/test_propose_optimizations.py -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/propose_optimizations.py tests/test_propose_optimizations.py
git commit -m "feat: pass existing security/prompt context to synthesizers to prevent duplicates"
```
