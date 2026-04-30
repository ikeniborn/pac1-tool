# Wiki Big Bang Restructure — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Перестроить wiki-pipeline агента: add-only синтез по knowledge_aspects, provenance tracking через fragment_ids, quality lifecycle (nascent/developing/mature).

**Architecture:** Каждый lint-прогон синтезирует страницу посекционно — одна LLM-сессия на каждый knowledge_aspect (workflow_steps / pitfalls / shortcuts). Существующий контент секции передаётся LLM вместе с новыми фрагментами с инструкцией «только добавлять». Meta-заголовок `<!-- wiki:meta -->` хранит provenance и quality. Promoted-секции (Successful pattern, Verified refusal) остаются нетронутыми.

**Tech Stack:** Python 3.11+, pytest, monkeypatch. Все изменения в `agent/wiki.py`, `agent/task_types.py`, `data/task_types.json`, `agent/prompt.py` (1 строка), `agent/evaluator.py` (3 строки). `agent/wiki_graph.py` не меняется.

**Spec:** `docs/superpowers/specs/2026-04-29-wiki-big-bang-restructure-design.md`

---

## File Map

| Файл | Роль изменений |
|------|---------------|
| `data/task_types.json` | Добавить `knowledge_aspects` для каждого типа |
| `agent/task_types.py` | `TaskType.knowledge_aspects: tuple`; функция `knowledge_aspects()`; `_DEFAULT_ASPECTS` |
| `agent/wiki.py` | `_read_page_meta`, `_write_page_meta`, `_parse_page_sections`, `_page_quality`; рефакторинг `_llm_synthesize` → aspect-by-aspect; обновление `run_wiki_lint`; `_run_pages_lint_pass` + `wiki_mature` тег |
| `agent/prompt.py` | `load_wiki_patterns`: добавить `[draft]` для nascent |
| `agent/evaluator.py` | `_load_reference_patterns`: усечение по quality |
| `tests/test_wiki_meta.py` | Новый файл: тесты meta read/write/parse/quality |
| `tests/test_wiki_aspect_synthesis.py` | Новый файл: тесты aspect-by-aspect синтеза |
| `tests/test_wiki_incremental.py` | Новый файл: тесты инкрементального lint |
| `tests/test_wiki_quality_header.py` | Новый файл: тест `[draft]` в load_wiki_patterns |
| `tests/test_task_types_aspects.py` | Новый файл: тест knowledge_aspects accessor |
| `tests/test_wiki_pages_lint.py` | Дополнить: тест wiki_mature тега |

---

## Task 1: knowledge_aspects в data/task_types.json и task_types.py

**Files:**
- Modify: `data/task_types.json`
- Modify: `agent/task_types.py`
- Create: `tests/test_task_types_aspects.py`

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_task_types_aspects.py
from agent.task_types import knowledge_aspects, _DEFAULT_ASPECTS, REGISTRY


def test_default_aspects_structure():
    for a in _DEFAULT_ASPECTS:
        assert "id" in a
        assert "header" in a
        assert "prompt" in a


def test_knowledge_aspects_returns_list_for_known_type():
    aspects = knowledge_aspects("email")
    assert isinstance(aspects, list)
    assert len(aspects) >= 1
    assert all("id" in a and "prompt" in a for a in aspects)


def test_knowledge_aspects_falls_back_to_defaults_for_type_without_aspects():
    # 'default' type might not define knowledge_aspects in JSON → falls back
    result = knowledge_aspects("default")
    assert result == _DEFAULT_ASPECTS


def test_knowledge_aspects_falls_back_for_unknown_type():
    result = knowledge_aspects("nonexistent_type_xyz")
    assert result == _DEFAULT_ASPECTS
```

- [ ] **Step 2: Запустить — убедиться что падает**

```bash
uv run pytest tests/test_task_types_aspects.py -v
```

Ожидается: `ImportError` или `AttributeError: module 'agent.task_types' has no attribute 'knowledge_aspects'`

- [ ] **Step 3: Добавить `knowledge_aspects` в `data/task_types.json`**

Добавить поле `"knowledge_aspects"` в каждый тип. Для типов без специфики используй дефолтный набор:

```json
{
  "version": 1,
  "_comment": "...",
  "types": {
    "default": {
      "description": "everything else (read, write, create, delete, move, standard tasks)",
      "model_env": "MODEL_DEFAULT",
      "fallback_chain": [],
      "wiki_folder": "default",
      "fast_path": null,
      "needs_builder": true,
      "status": "hard",
      "knowledge_aspects": []
    },
    "preject": {
      "description": "calendar invites, sync to external CRM/service, upload to external URL",
      "model_env": "MODEL_PREJECT",
      "fallback_chain": ["default"],
      "wiki_folder": "preject",
      "fast_path": {
        "pattern": "\\b(calendar\\s+invite|create\\s+(a\\s+)?(meeting|event|ticket)|sync\\s+(to|with)\\s+\\w+|upload\\s+to\\s+https?|salesforce|hubspot|zendesk|jira|external\\s+(api|crm|url)|send\\s+to\\s+https?)\\b",
        "flags": ["IGNORECASE"],
        "confidence": "high"
      },
      "needs_builder": false,
      "status": "hard",
      "knowledge_aspects": []
    },
    "email": {
      "description": "send/compose/write email to a recipient",
      "model_env": "MODEL_EMAIL",
      "fallback_chain": ["default"],
      "wiki_folder": "email",
      "fast_path": {
        "pattern": "\\b(send|compose|write|email)\\b.*\\b(to|recipient|subject)\\b|\\bemail\\s+(?!(?:address|of|from|in)\\b)[A-Za-z]+\\s+(a\\b|an\\b|brief\\b|reminder\\b|summary\\b|short\\b)",
        "flags": ["IGNORECASE"],
        "confidence": "high"
      },
      "needs_builder": true,
      "status": "hard",
      "knowledge_aspects": [
        {
          "id": "workflow_steps",
          "header": "Workflow steps",
          "prompt": "Proven step sequences leading to OUTCOME_OK, especially contact lookup then outbox write patterns"
        },
        {
          "id": "pitfalls",
          "header": "Key pitfalls",
          "prompt": "Risks and failure patterns, especially wrong-recipient errors and skipped contact file reads"
        },
        {
          "id": "shortcuts",
          "header": "Shortcuts",
          "prompt": "Email-specific optimizations and lookup shortcuts"
        }
      ]
    },
    "queue": {
      "description": "work through / take care of / handle the incoming queue or all inbox items",
      "model_env": "MODEL_QUEUE",
      "fallback_chain": ["inbox", "default"],
      "wiki_folder": "queue",
      "fast_path": null,
      "needs_builder": true,
      "status": "hard",
      "knowledge_aspects": [
        {
          "id": "workflow_steps",
          "header": "Workflow steps",
          "prompt": "Proven sequences for working through all inbox items to OUTCOME_OK including latest invoice lookup and account resolution"
        },
        {
          "id": "pitfalls",
          "header": "Key pitfalls",
          "prompt": "Risks including invoice attribution errors, wrong account_id resolution, filename-as-owner-proxy mistakes, unreadable candidates"
        },
        {
          "id": "shortcuts",
          "header": "Shortcuts",
          "prompt": "Queue-specific patterns: account resolution priority (body-named company wins), recipient identity rules (use exact From header)"
        }
      ]
    },
    "inbox": {
      "description": "process/check/handle/review single inbox or inbound note",
      "model_env": "MODEL_INBOX",
      "fallback_chain": ["default"],
      "wiki_folder": "inbox",
      "fast_path": null,
      "needs_builder": true,
      "status": "hard",
      "knowledge_aspects": [
        {
          "id": "workflow_steps",
          "header": "Workflow steps",
          "prompt": "Proven step sequences for processing single inbox or inbound notes to OUTCOME_OK"
        },
        {
          "id": "pitfalls",
          "header": "Key pitfalls",
          "prompt": "Risks and failure patterns for inbox processing"
        },
        {
          "id": "shortcuts",
          "header": "Shortcuts",
          "prompt": "Inbox-specific insights and optimizations"
        }
      ]
    },
    "lookup": {
      "description": "find, count, or query vault data (contacts, files, channels) with no write action",
      "model_env": "MODEL_LOOKUP",
      "fallback_chain": ["default"],
      "wiki_folder": "lookup",
      "fast_path": null,
      "needs_builder": true,
      "status": "hard",
      "knowledge_aspects": [
        {
          "id": "workflow_steps",
          "header": "Workflow steps",
          "prompt": "Proven step sequences for finding, counting, or querying vault data without writes"
        },
        {
          "id": "pitfalls",
          "header": "Key pitfalls",
          "prompt": "Risks: false matches, wrong filters, premature NONE_CLARIFICATION before running list/find/tree"
        },
        {
          "id": "shortcuts",
          "header": "Shortcuts",
          "prompt": "Lookup-specific patterns: search strategies, filter approaches"
        }
      ]
    },
    "capture": {
      "description": "capture explicit snippet/content from source into a specific vault path",
      "model_env": "MODEL_CAPTURE",
      "fallback_chain": ["default"],
      "wiki_folder": "capture",
      "fast_path": null,
      "needs_builder": true,
      "status": "hard",
      "knowledge_aspects": [
        {
          "id": "workflow_steps",
          "header": "Workflow steps",
          "prompt": "Proven sequences for capturing content from source into vault paths"
        },
        {
          "id": "pitfalls",
          "header": "Key pitfalls",
          "prompt": "Risks: wrong target path, partial captures, source misidentification"
        },
        {
          "id": "shortcuts",
          "header": "Shortcuts",
          "prompt": "Capture-specific insights and optimizations"
        }
      ]
    },
    "crm": {
      "description": "reschedule follow-up, reconnect date, fix follow-up regression, date arithmetic + write",
      "model_env": "MODEL_CRM",
      "fallback_chain": ["default"],
      "wiki_folder": "crm",
      "fast_path": null,
      "needs_builder": true,
      "status": "hard",
      "knowledge_aspects": [
        {
          "id": "workflow_steps",
          "header": "Workflow steps",
          "prompt": "Proven sequences for rescheduling follow-ups, date arithmetic and write operations"
        },
        {
          "id": "pitfalls",
          "header": "Key pitfalls",
          "prompt": "Risks: dropped fields on write, wrong field mutation, account_manager overwrite on reschedule"
        },
        {
          "id": "shortcuts",
          "header": "Shortcuts",
          "prompt": "CRM-specific patterns: field preservation (read full record first), date arithmetic, reconnect logic"
        }
      ]
    },
    "temporal": {
      "description": "date-relative queries needing datetime arithmetic (N days ago, in N days, what date)",
      "model_env": "MODEL_TEMPORAL",
      "fallback_chain": ["lookup", "default"],
      "wiki_folder": "temporal",
      "fast_path": {
        "pattern": "\\bwhat\\s+(date|day)\\s+is\\s+in\\s+\\d+\\s+(day|week|month)s?\\b|\\b\\d+\\s+(day|week|month)s?\\s+from\\s+(today|now)\\b",
        "flags": ["IGNORECASE"],
        "confidence": "high"
      },
      "needs_builder": true,
      "status": "hard",
      "knowledge_aspects": [
        {
          "id": "workflow_steps",
          "header": "Workflow steps",
          "prompt": "Proven sequences for date-relative queries: vault anchor derivation, candidate file inversion approach"
        },
        {
          "id": "pitfalls",
          "header": "Key pitfalls",
          "prompt": "Risks: system-clock vs vault-time confusion, wrong temporal anchor, premature NONE_CLARIFICATION before list/find/tree"
        },
        {
          "id": "shortcuts",
          "header": "Shortcuts",
          "prompt": "Temporal patterns: VAULT_DATE as lower bound, ESTIMATED_TODAY derivation, candidate inversion (implied_today = file_date + N)"
        }
      ]
    },
    "distill": {
      "description": "analysis/reasoning AND writing a card/note/summary",
      "model_env": "MODEL_DISTILL",
      "fallback_chain": ["default"],
      "wiki_folder": "distill",
      "fast_path": null,
      "needs_builder": true,
      "status": "hard",
      "knowledge_aspects": [
        {
          "id": "workflow_steps",
          "header": "Workflow steps",
          "prompt": "Proven sequences for analysis/reasoning and writing summary cards or notes"
        },
        {
          "id": "pitfalls",
          "header": "Key pitfalls",
          "prompt": "Risks: incomplete analysis, wrong output format, missing required card fields"
        },
        {
          "id": "shortcuts",
          "header": "Shortcuts",
          "prompt": "Distill-specific insights and card-writing patterns"
        }
      ]
    }
  }
}
```

- [ ] **Step 4: Добавить `knowledge_aspects` в `agent/task_types.py`**

В разделе `# Schema` добавить константу и расширить датакласс:

```python
# После _RE_FLAG_MAP добавить:
_DEFAULT_ASPECTS: list[dict] = [
    {"id": "workflow_steps", "header": "Workflow steps", "prompt": "Proven step sequences leading to task success"},
    {"id": "pitfalls",       "header": "Key pitfalls",   "prompt": "Key risks and failure patterns"},
    {"id": "shortcuts",      "header": "Shortcuts",       "prompt": "Task-specific insights and optimizations"},
]
```

В `@dataclass(frozen=True) class TaskType` добавить поле после `status`:

```python
    knowledge_aspects: tuple  # tuple of dicts: [{id, header, prompt}, ...]
```

В `_parse_task_type` добавить чтение поля (перед `return TaskType(`):

```python
    raw_aspects = raw.get("knowledge_aspects") or []
    knowledge_aspects_tuple = tuple(raw_aspects)
```

И в `return TaskType(...)` добавить:

```python
        knowledge_aspects=knowledge_aspects_tuple,
```

В конце файла добавить публичную функцию (после `vault_types()`):

```python
def knowledge_aspects(type_name: str) -> list[dict]:
    """Return knowledge_aspects for type_name, falling back to _DEFAULT_ASPECTS."""
    t = REGISTRY.types.get(type_name)
    if t is None or not t.knowledge_aspects:
        return _DEFAULT_ASPECTS
    return list(t.knowledge_aspects)
```

- [ ] **Step 5: Запустить тесты — убедиться что проходят**

```bash
uv run pytest tests/test_task_types_aspects.py -v
```

Ожидается: 4 PASSED

- [ ] **Step 6: Убедиться что существующие тесты не сломаны**

```bash
uv run pytest tests/ -x -q
```

Ожидается: все существующие тесты проходят.

- [ ] **Step 7: Коммит**

```bash
git add data/task_types.json agent/task_types.py tests/test_task_types_aspects.py
git commit -m "feat(wiki): add knowledge_aspects to task_types registry and accessor"
```

---

## Task 2: Meta-утилиты в wiki.py

**Files:**
- Modify: `agent/wiki.py`
- Create: `tests/test_wiki_meta.py`

- [ ] **Step 1: Написать падающие тесты**

```python
# tests/test_wiki_meta.py
import pytest
from agent.wiki import _read_page_meta, _write_page_meta, _parse_page_sections, _page_quality


# --- _page_quality ---

def test_quality_nascent():
    assert _page_quality(0) == "nascent"
    assert _page_quality(4) == "nascent"


def test_quality_developing():
    assert _page_quality(5) == "developing"
    assert _page_quality(14) == "developing"


def test_quality_mature():
    assert _page_quality(15) == "mature"
    assert _page_quality(100) == "mature"


# --- _write_page_meta ---

def test_write_page_meta_basic():
    meta = {
        "category": "email",
        "quality": "nascent",
        "fragment_count": 3,
        "fragment_ids": ["t01_20260101T120000Z", "t02_20260102T130000Z"],
        "last_synthesized": "2026-04-30",
        "aspects_covered": "workflow_steps,pitfalls",
    }
    result = _write_page_meta(meta)
    assert result.startswith("<!-- wiki:meta")
    assert "category: email" in result
    assert "quality: nascent" in result
    assert "fragment_count: 3" in result
    assert "t01_20260101T120000Z" in result
    assert result.strip().endswith("-->")


def test_write_page_meta_empty_ids():
    meta = {"category": "crm", "quality": "nascent", "fragment_count": 0,
            "fragment_ids": [], "last_synthesized": "2026-04-30", "aspects_covered": ""}
    result = _write_page_meta(meta)
    assert "fragment_ids: []" in result


# --- _read_page_meta (from raw content string) ---

def test_read_page_meta_roundtrip():
    meta_in = {
        "category": "email",
        "quality": "developing",
        "fragment_count": 7,
        "fragment_ids": ["t01_abc", "t02_def"],
        "last_synthesized": "2026-04-30",
        "aspects_covered": "workflow_steps,pitfalls,shortcuts",
    }
    header = _write_page_meta(meta_in)
    page_content = header + "\n\n## Workflow steps\nsome content\n"
    meta_out = _read_page_meta_from_content(page_content)
    assert meta_out["quality"] == "developing"
    assert meta_out["fragment_count"] == 7
    assert "t01_abc" in meta_out["fragment_ids"]
    assert "t02_def" in meta_out["fragment_ids"]


def test_read_page_meta_missing_header_returns_defaults():
    content = "## Workflow steps\nsome content without meta header\n"
    meta = _read_page_meta_from_content(content)
    assert meta["quality"] == "nascent"
    assert meta["fragment_count"] == 0
    assert meta["fragment_ids"] == []


# --- _parse_page_sections ---

def test_parse_page_sections_basic():
    content = """<!-- wiki:meta
category: email
quality: nascent
fragment_count: 0
fragment_ids: []
last_synthesized: 2026-04-30
aspects_covered:
-->

## Workflow steps
Step 1: do this.
Step 2: do that.

## Key pitfalls
- Avoid X.
"""
    sections = _parse_page_sections(content)
    assert "workflow_steps" in sections
    assert "key_pitfalls" in sections
    assert "Step 1: do this." in sections["workflow_steps"]
    assert "Avoid X." in sections["key_pitfalls"]


def test_parse_page_sections_no_meta():
    content = "## Shortcuts\nUse find before read.\n\n## Key pitfalls\nDon't guess.\n"
    sections = _parse_page_sections(content)
    assert "shortcuts" in sections
    assert "key_pitfalls" in sections


def test_parse_page_sections_empty():
    assert _parse_page_sections("") == {}
    assert _parse_page_sections("<!-- wiki:meta\n-->") == {}
```

Важно: тест импортирует `_read_page_meta_from_content` — это внутренняя функция, которую нам нужно реализовать (принимает строку, а не имя страницы).

- [ ] **Step 2: Запустить — убедиться что падает**

```bash
uv run pytest tests/test_wiki_meta.py -v
```

Ожидается: `ImportError` — функции не существуют.

- [ ] **Step 3: Добавить функции в `agent/wiki.py`**

Добавить после блока констант (`_ENTITY_PATTERNS`, `_scrub_entity`), перед `promote_successful_pattern`:

```python
# ---------------------------------------------------------------------------
# FIX-BIG-BANG: page meta + section utilities
# ---------------------------------------------------------------------------

_META_BLOCK_RE = re.compile(r"^<!--\s*wiki:meta\s*\n(.*?)-->[ \t]*\n?", re.DOTALL)
_FRAGMENT_IDS_RE = re.compile(r"[\w.-]+")


def _page_quality(fragment_count: int) -> str:
    """nascent/developing/mature based on accumulated fragment count."""
    if fragment_count >= 15:
        return "mature"
    if fragment_count >= 5:
        return "developing"
    return "nascent"


def _read_page_meta_from_content(content: str) -> dict:
    """Parse wiki:meta comment block from raw page content string."""
    defaults: dict = {"fragment_ids": [], "quality": "nascent", "fragment_count": 0,
                      "category": "", "last_synthesized": "", "aspects_covered": ""}
    if not content:
        return defaults
    m = _META_BLOCK_RE.match(content)
    if not m:
        return defaults
    meta = dict(defaults)
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if key == "fragment_ids":
            meta["fragment_ids"] = _FRAGMENT_IDS_RE.findall(val)
        elif key == "fragment_count":
            try:
                meta["fragment_count"] = int(val)
            except ValueError:
                pass
        elif key in meta:
            meta[key] = val
    return meta


def _read_page_meta(page_name: str) -> dict:
    """Read wiki:meta from pages/{page_name}.md. Fail-open → defaults."""
    return _read_page_meta_from_content(_read_page(page_name))


def _write_page_meta(meta: dict) -> str:
    """Serialize meta dict → <!-- wiki:meta ... --> block."""
    frag_ids = meta.get("fragment_ids") or []
    ids_str = "[" + ", ".join(str(i) for i in frag_ids) + "]"
    return (
        f"<!-- wiki:meta\n"
        f"category: {meta.get('category', '')}\n"
        f"quality: {meta.get('quality', 'nascent')}\n"
        f"fragment_count: {meta.get('fragment_count', 0)}\n"
        f"fragment_ids: {ids_str}\n"
        f"last_synthesized: {meta.get('last_synthesized', '')}\n"
        f"aspects_covered: {meta.get('aspects_covered', '')}\n"
        f"-->"
    )


def _parse_page_sections(content: str) -> dict[str, str]:
    """Split page into {normalized_header_id: body} dict (insertion order preserved).

    Strips wiki:meta block first. Header normalized: lower, non-alnum → underscore.
    """
    if not content:
        return {}
    # Strip meta block
    body = _META_BLOCK_RE.sub("", content).strip()
    if not body:
        return {}
    parts = re.split(r"(?m)^## (.+)$", body)
    # parts[0] = preamble (ignored), parts[1::2] = headers, parts[2::2] = bodies
    sections: dict[str, str] = {}
    for i in range(1, len(parts), 2):
        header = parts[i].strip()
        section_body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        section_id = re.sub(r"[^a-z0-9]+", "_", header.lower()).strip("_")
        sections[section_id] = section_body
    return sections
```

- [ ] **Step 4: Обновить импорт в тесте**

В `tests/test_wiki_meta.py` заменить импорт:

```python
from agent.wiki import (
    _read_page_meta, _read_page_meta_from_content,
    _write_page_meta, _parse_page_sections, _page_quality,
)
```

- [ ] **Step 5: Запустить тесты**

```bash
uv run pytest tests/test_wiki_meta.py -v
```

Ожидается: все PASSED.

- [ ] **Step 6: Полный прогон**

```bash
uv run pytest tests/ -x -q
```

- [ ] **Step 7: Коммит**

```bash
git add agent/wiki.py tests/test_wiki_meta.py
git commit -m "feat(wiki): add page meta utilities (_read_page_meta, _write_page_meta, _parse_page_sections, _page_quality)"
```

---

## Task 3: Aspect-by-aspect синтез

**Files:**
- Modify: `agent/wiki.py`
- Create: `tests/test_wiki_aspect_synthesis.py`

- [ ] **Step 1: Написать падающие тесты**

```python
# tests/test_wiki_aspect_synthesis.py
from unittest.mock import patch, call
from agent.wiki import _llm_synthesize_aspects, _assemble_page_from_sections


ASPECTS = [
    {"id": "workflow_steps", "header": "Workflow steps", "prompt": "Proven steps"},
    {"id": "pitfalls",       "header": "Key pitfalls",   "prompt": "Risks"},
]

NEW_FRAGS = ["---\noutcome: OUTCOME_OK\n---\n\nDONE OPS:\n- read /contacts/c.json\n"]


def test_assemble_page_from_sections_includes_all_aspects():
    meta = {"category": "email", "quality": "nascent", "fragment_count": 1,
            "fragment_ids": ["t01_ts"], "last_synthesized": "2026-04-30",
            "aspects_covered": "workflow_steps,pitfalls"}
    sections = {"workflow_steps": "Step 1: read contact.", "key_pitfalls": "Avoid X."}
    result = _assemble_page_from_sections(meta, sections, ASPECTS)
    assert "<!-- wiki:meta" in result
    assert "## Workflow steps" in result
    assert "Step 1: read contact." in result
    assert "## Key pitfalls" in result
    assert "Avoid X." in result


def test_assemble_page_preserves_promoted_sections():
    meta = {"category": "email", "quality": "developing", "fragment_count": 6,
            "fragment_ids": [], "last_synthesized": "2026-04-30", "aspects_covered": "workflow_steps"}
    sections = {
        "workflow_steps": "Step 1: do this.",
        "successful_pattern_t01_2026_04_01": "trajectory details here",
    }
    result = _assemble_page_from_sections(meta, sections, ASPECTS)
    assert "## Workflow steps" in result
    assert "## Successful pattern:" in result or "trajectory details here" in result


def test_llm_synthesize_aspects_calls_llm_per_aspect(tmp_path, monkeypatch):
    monkeypatch.setattr("agent.wiki._FRAGMENTS_DIR", tmp_path / "fragments")
    responses = ["merged workflow content", "merged pitfalls content"]

    with patch("agent.dispatch.call_llm_raw", side_effect=responses) as mock_llm:
        result_sections = _llm_synthesize_aspects(
            existing_sections={"workflow_steps": "old step", "key_pitfalls": "old risk"},
            new_entries=NEW_FRAGS,
            aspects=ASPECTS,
            model="test-model",
            cfg={},
        )

    assert mock_llm.call_count == 2
    assert result_sections["workflow_steps"] == "merged workflow content"
    assert result_sections["key_pitfalls"] == "merged pitfalls content"


def test_llm_synthesize_aspects_no_model_returns_concat():
    result_sections = _llm_synthesize_aspects(
        existing_sections={"workflow_steps": "old"},
        new_entries=["new fragment"],
        aspects=ASPECTS,
        model="",
        cfg={},
    )
    assert "old" in result_sections.get("workflow_steps", "")
    assert "new fragment" in result_sections.get("workflow_steps", "")


def test_llm_synthesize_aspects_preserves_existing_on_empty_llm_response():
    with patch("agent.dispatch.call_llm_raw", return_value=""):
        result_sections = _llm_synthesize_aspects(
            existing_sections={"workflow_steps": "must survive"},
            new_entries=["fragment"],
            aspects=ASPECTS,
            model="test-model",
            cfg={},
        )
    assert result_sections["workflow_steps"] == "must survive"
```

- [ ] **Step 2: Запустить — убедиться что падает**

```bash
uv run pytest tests/test_wiki_aspect_synthesis.py -v
```

Ожидается: `ImportError`.

- [ ] **Step 3: Добавить функции в `agent/wiki.py`**

Добавить после `_concat_merge` (около строки 1065):

```python
def _llm_synthesize_aspects(
    existing_sections: dict[str, str],
    new_entries: list[str],
    aspects: list[dict],
    model: str,
    cfg: dict,
) -> dict[str, str]:
    """Synthesize each knowledge aspect separately (add-only).

    Returns updated sections dict. Existing non-aspect sections are passed through.
    Falls back to concat-merge when model is empty or LLM returns empty response.
    """
    combined_new = "\n\n---\n\n".join(new_entries)
    result = dict(existing_sections)  # preserve all existing sections (promoted, etc.)

    for aspect in aspects:
        aspect_id = aspect["id"]
        header = aspect.get("header", aspect_id.replace("_", " ").capitalize())
        # normalized_id used as key in sections dict
        section_key = re.sub(r"[^a-z0-9]+", "_", header.lower()).strip("_")
        existing_section = existing_sections.get(section_key, "")

        if not model:
            # Concat fallback: append new fragment content to existing section
            merged = (existing_section + "\n\n" + combined_new).strip() if existing_section else combined_new
            result[section_key] = merged
            continue

        user_msg = (
            f"You are updating a wiki section for an AI file-system agent.\n"
            f"Section purpose: {aspect['prompt']}\n\n"
            f"EXISTING SECTION CONTENT (DO NOT REMOVE ANY LINE FROM THIS):\n"
            f"{existing_section or '(empty)'}\n\n"
            f"NEW TASK FRAGMENTS:\n{combined_new}\n\n"
            f"Instructions:\n"
            f"1. Extract only content relevant to: {aspect['prompt']}\n"
            f"2. ADD new insights to the existing content — never remove existing lines\n"
            f"3. Skip new fragment content that duplicates what is already on the page\n"
            f"4. Output ONLY the merged section body (no ## header, no preamble, no commentary)\n"
        )
        try:
            from .dispatch import call_llm_raw
            response = call_llm_raw(
                system="You are a knowledge curator. Output only clean Markdown, no commentary.",
                user_msg=user_msg,
                model=model,
                cfg=cfg,
                max_tokens=2000,
                plain_text=True,
            )
            if response and len(response.strip()) > 10:
                merged = _sanitize_synthesized_page(response.strip())
                result[section_key] = merged
            else:
                # LLM returned empty — preserve existing
                result[section_key] = existing_section
        except Exception as e:
            print(f"[wiki-lint] aspect synthesis failed for '{aspect_id}' ({e}), keeping existing")
            result[section_key] = existing_section

    return result


def _assemble_page_from_sections(
    meta: dict,
    sections: dict[str, str],
    aspects: list[dict],
) -> str:
    """Assemble final page: meta header + aspect sections + promoted sections.

    Aspect sections come first (for LLM relevance). Promoted sections (Successful
    pattern, Verified refusal, Contract constraints) follow in original order.
    """
    lines: list[str] = [_write_page_meta(meta)]

    # Aspect sections first
    aspect_keys: set[str] = set()
    for aspect in aspects:
        header = aspect.get("header", aspect["id"].replace("_", " ").capitalize())
        section_key = re.sub(r"[^a-z0-9]+", "_", header.lower()).strip("_")
        aspect_keys.add(section_key)
        content = sections.get(section_key, "").strip()
        if content:
            lines.append(f"\n## {header}\n{content}")

    # Promoted / non-aspect sections after (preserve order)
    for section_key, content in sections.items():
        if section_key in aspect_keys or not content.strip():
            continue
        # Reconstruct header from key: underscores → spaces, capitalize words
        header = " ".join(w.capitalize() for w in section_key.split("_"))
        lines.append(f"\n## {header}\n{content.strip()}")

    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Запустить тесты**

```bash
uv run pytest tests/test_wiki_aspect_synthesis.py -v
```

Ожидается: все PASSED.

- [ ] **Step 5: Полный прогон**

```bash
uv run pytest tests/ -x -q
```

- [ ] **Step 6: Коммит**

```bash
git add agent/wiki.py tests/test_wiki_aspect_synthesis.py
git commit -m "feat(wiki): add aspect-by-aspect add-only synthesis (_llm_synthesize_aspects, _assemble_page_from_sections)"
```

---

## Task 4: Инкрементальный lint (интеграция нового синтеза)

**Files:**
- Modify: `agent/wiki.py` — функция `run_wiki_lint`
- Create: `tests/test_wiki_incremental.py`

- [ ] **Step 1: Написать падающие тесты**

```python
# tests/test_wiki_incremental.py
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from agent.wiki import run_wiki_lint, _read_page_meta_from_content


def _make_graph_module():
    gm = MagicMock()
    gm.merge_updates.return_value = []
    gm.load_graph.return_value = MagicMock()
    return gm


def _write_fragment(frag_dir: Path, name: str, content: str) -> None:
    frag_dir.mkdir(parents=True, exist_ok=True)
    (frag_dir / name).write_text(content, encoding="utf-8")


FRAGMENT_CONTENT = (
    "---\ntask_id: t01\ntask_type: email\noutcome: OUTCOME_OK\ndate: 2026-04-30\n"
    "task: 'send email'\n---\n\nDONE OPS:\n- read /contacts/c.json\n"
    "- write /outbox/1.json\n\nSTEP FACTS:\n- read: /contacts/c.json → found\n"
)


def test_lint_writes_page_with_meta_header(tmp_path, monkeypatch):
    """After lint, the page must contain a <!-- wiki:meta --> block."""
    frag_dir = tmp_path / "fragments" / "email"
    pages_dir = tmp_path / "pages"
    archive_dir = tmp_path / "archive" / "email"
    pages_dir.mkdir(parents=True)
    archive_dir.mkdir(parents=True)

    _write_fragment(frag_dir, "t01_20260430T120000Z.md", FRAGMENT_CONTENT)

    monkeypatch.setattr("agent.wiki._FRAGMENTS_DIR", tmp_path / "fragments")
    monkeypatch.setattr("agent.wiki._PAGES_DIR", pages_dir)
    monkeypatch.setattr("agent.wiki._ARCHIVE_DIR", tmp_path / "archive")
    monkeypatch.setattr("agent.wiki._GRAPH_AUTOBUILD", False)

    with patch("agent.dispatch.call_llm_raw", return_value="Step 1: read contact.\nStep 2: write outbox."):
        run_wiki_lint(model="test-model", cfg={})

    page_path = pages_dir / "email.md"
    assert page_path.exists(), "email.md was not written"
    content = page_path.read_text()
    assert "<!-- wiki:meta" in content, "meta header missing"
    assert "quality:" in content
    assert "fragment_count:" in content


def test_lint_records_fragment_id_in_meta(tmp_path, monkeypatch):
    """Processed fragment stem appears in fragment_ids of the page meta."""
    frag_dir = tmp_path / "fragments" / "email"
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir(parents=True)

    _write_fragment(frag_dir, "t01_20260430T120000Z.md", FRAGMENT_CONTENT)

    monkeypatch.setattr("agent.wiki._FRAGMENTS_DIR", tmp_path / "fragments")
    monkeypatch.setattr("agent.wiki._PAGES_DIR", pages_dir)
    monkeypatch.setattr("agent.wiki._ARCHIVE_DIR", tmp_path / "archive")
    monkeypatch.setattr("agent.wiki._GRAPH_AUTOBUILD", False)

    with patch("agent.dispatch.call_llm_raw", return_value="Merged content here."):
        run_wiki_lint(model="test-model", cfg={})

    page_path = pages_dir / "email.md"
    content = page_path.read_text()
    meta = _read_page_meta_from_content(content)
    assert "t01_20260430T120000Z" in meta["fragment_ids"]


def test_lint_quality_nascent_for_single_fragment(tmp_path, monkeypatch):
    frag_dir = tmp_path / "fragments" / "email"
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir(parents=True)

    _write_fragment(frag_dir, "t01_20260430T120000Z.md", FRAGMENT_CONTENT)

    monkeypatch.setattr("agent.wiki._FRAGMENTS_DIR", tmp_path / "fragments")
    monkeypatch.setattr("agent.wiki._PAGES_DIR", pages_dir)
    monkeypatch.setattr("agent.wiki._ARCHIVE_DIR", tmp_path / "archive")
    monkeypatch.setattr("agent.wiki._GRAPH_AUTOBUILD", False)

    with patch("agent.dispatch.call_llm_raw", return_value="Content."):
        run_wiki_lint(model="test-model", cfg={})

    content = (pages_dir / "email.md").read_text()
    meta = _read_page_meta_from_content(content)
    assert meta["quality"] == "nascent"


def test_lint_archives_fragments_after_synthesis(tmp_path, monkeypatch):
    """Fragments are moved to archive/ after processing."""
    frag_dir = tmp_path / "fragments" / "email"
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir(parents=True)

    _write_fragment(frag_dir, "t01_20260430T120000Z.md", FRAGMENT_CONTENT)

    monkeypatch.setattr("agent.wiki._FRAGMENTS_DIR", tmp_path / "fragments")
    monkeypatch.setattr("agent.wiki._PAGES_DIR", pages_dir)
    monkeypatch.setattr("agent.wiki._ARCHIVE_DIR", tmp_path / "archive")
    monkeypatch.setattr("agent.wiki._GRAPH_AUTOBUILD", False)

    with patch("agent.dispatch.call_llm_raw", return_value="Content."):
        run_wiki_lint(model="test-model", cfg={})

    assert not (frag_dir / "t01_20260430T120000Z.md").exists(), "fragment not archived"
    assert (tmp_path / "archive" / "email" / "t01_20260430T120000Z.md").exists()
```

- [ ] **Step 2: Запустить — убедиться что падает**

```bash
uv run pytest tests/test_wiki_incremental.py -v
```

Ожидается: тесты падают (старый lint не пишет meta-заголовок).

- [ ] **Step 3: Обновить `run_wiki_lint` в `agent/wiki.py`**

Найти цикл `for category in categories:` (строка ~873). Заменить блок внутри цикла, начиная с `frag_dir = _FRAGMENTS_DIR / category`:

```python
    for category in categories:
        frag_dir = _FRAGMENTS_DIR / category
        fragments = sorted(frag_dir.glob("*.md"))
        if not fragments:
            continue

        # Read existing page and its meta
        existing_raw = _read_page(category)
        page_meta = _read_page_meta_from_content(existing_raw)
        existing_sections = _parse_page_sections(existing_raw)
        new_entries = [f.read_text(encoding="utf-8") for f in fragments]

        # Resolve knowledge_aspects for this category
        from .task_types import knowledge_aspects as _get_aspects
        # category may be "errors/email" — use base name for aspect lookup
        base_cat = category.split("/")[-1] if "/" in category else category
        aspects = _get_aspects(base_cat)

        # Aspect-by-aspect add-only synthesis
        merged_sections, deltas = _llm_synthesize_v2(
            existing_sections=existing_sections,
            new_entries=new_entries,
            category=category,
            aspects=aspects,
            model=model,
            cfg=cfg,
        )

        # Update meta
        new_count = page_meta["fragment_count"] + len(fragments)
        new_ids = list(page_meta["fragment_ids"]) + [f.stem for f in fragments]
        new_quality = _page_quality(new_count)
        aspects_covered = ",".join(a["id"] for a in aspects)
        new_meta = {
            "category": category,
            "quality": new_quality,
            "fragment_count": new_count,
            "fragment_ids": new_ids,
            "last_synthesized": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "aspects_covered": aspects_covered,
        }
        merged_page = _assemble_page_from_sections(new_meta, merged_sections, aspects)

        page_path = _PAGES_DIR / f"{category}.md"
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(merged_page, encoding="utf-8")

        archive_dir = _ARCHIVE_DIR / category
        archive_dir.mkdir(parents=True, exist_ok=True)
        for f in fragments:
            f.rename(archive_dir / f.name)

        # Graph integration (unchanged)
        if graph_module is not None and graph_state is not None:
            n_ins = len(deltas.get("new_insights") or []) if isinstance(deltas, dict) else 0
            n_rul = len(deltas.get("new_rules") or []) if isinstance(deltas, dict) else 0
            n_apt = len(deltas.get("antipatterns") or []) if isinstance(deltas, dict) else 0
            print(
                f"[wiki-graph] {category}: deltas insights={n_ins} rules={n_rul} antipatterns={n_apt}"
            )
            if deltas and (n_ins or n_rul or n_apt):
                _stamp_category_tag(deltas, category)
                try:
                    touched = graph_module.merge_updates(graph_state, deltas)
                    graph_module.save_graph(graph_state)
                    n_total_items += n_ins + n_rul + n_apt
                    n_total_touched += len(touched)
                    print(f"[wiki-graph] {category}: persisted, touched {len(touched)} nodes")
                except Exception as e:
                    print(f"[wiki-graph] {category}: merge failed: {e}")

        print(f"[wiki-lint] {category}: synthesized {len(fragments)} fragments → {category}.md (quality={new_quality})")
```

Добавить вспомогательную функцию `_llm_synthesize_v2` (обёртка, которая вызывает `_llm_synthesize_aspects` и отдельно извлекает graph_deltas через `_split_markdown_and_deltas` из одного суммарного прогона, если нужно):

```python
def _llm_synthesize_v2(
    existing_sections: dict[str, str],
    new_entries: list[str],
    category: str,
    aspects: list[dict],
    model: str,
    cfg: dict,
) -> tuple[dict[str, str], dict]:
    """New synthesis entry point: aspect-by-aspect add-only.

    Returns (merged_sections, graph_deltas). graph_deltas extracted via
    separate graph-only LLM call when GRAPH_AUTOBUILD is on.
    """
    merged_sections = _llm_synthesize_aspects(
        existing_sections=existing_sections,
        new_entries=new_entries,
        aspects=aspects,
        model=model,
        cfg=cfg,
    )

    # Graph deltas: separate extraction from combined new fragments
    deltas: dict = {}
    if _GRAPH_AUTOBUILD and model:
        combined_new = "\n\n---\n\n".join(new_entries)
        if category.startswith("errors/") and category not in _LINT_PROMPTS:
            synthesis_prompt = _LINT_PROMPTS.get("errors", _LINT_PROMPTS["_pattern_default"])
        else:
            synthesis_prompt = _LINT_PROMPTS.get(category, _LINT_PROMPTS["_pattern_default"])
        graph_user_msg = (
            f"{synthesis_prompt}\n\n"
            f"NEW FRAGMENTS:\n{combined_new}\n\n"
            f"Output ONLY the graph deltas JSON block, no Markdown."
            f"{_GRAPH_INSTRUCTION_SUFFIX}"
        )
        try:
            from .dispatch import call_llm_raw
            graph_resp = call_llm_raw(
                system="You are a knowledge graph curator. Output only the JSON fence block.",
                user_msg=graph_user_msg,
                model=model,
                cfg=cfg,
                max_tokens=800,
                plain_text=True,
            )
            if graph_resp:
                _, deltas = _split_markdown_and_deltas(graph_resp)
        except Exception as e:
            print(f"[wiki-graph] delta extraction failed for '{category}' ({e})")

    return merged_sections, deltas
```

- [ ] **Step 4: Запустить тесты**

```bash
uv run pytest tests/test_wiki_incremental.py -v
```

Ожидается: все PASSED.

- [ ] **Step 5: Убедиться что существующие тесты не сломаны**

```bash
uv run pytest tests/ -x -q
```

- [ ] **Step 6: Коммит**

```bash
git add agent/wiki.py tests/test_wiki_incremental.py
git commit -m "feat(wiki): integrate aspect-by-aspect synthesis into run_wiki_lint with meta tracking"
```

---

## Task 5: Quality-aware load_wiki_patterns

**Files:**
- Modify: `agent/wiki.py` — функция `load_wiki_patterns`
- Create: `tests/test_wiki_quality_header.py`

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_wiki_quality_header.py
from pathlib import Path
from agent.wiki import load_wiki_patterns, _write_page_meta


def _write_page(pages_dir: Path, name: str, meta: dict, body: str) -> None:
    pages_dir.mkdir(parents=True, exist_ok=True)
    from agent.wiki import _write_page_meta
    content = _write_page_meta(meta) + "\n\n" + body
    (pages_dir / f"{name}.md").write_text(content, encoding="utf-8")


def test_nascent_page_adds_draft_marker(tmp_path, monkeypatch):
    monkeypatch.setattr("agent.wiki._PAGES_DIR", tmp_path / "pages")
    monkeypatch.setattr("agent.wiki._FRAGMENTS_DIR", tmp_path / "fragments")
    meta = {"category": "email", "quality": "nascent", "fragment_count": 2,
            "fragment_ids": [], "last_synthesized": "2026-04-30", "aspects_covered": "workflow_steps"}
    _write_page(tmp_path / "pages", "email", meta, "## Workflow steps\nStep 1.")

    result = load_wiki_patterns("email", include_negatives=False)
    assert "[draft" in result.lower() or "draft" in result


def test_developing_page_no_draft_marker(tmp_path, monkeypatch):
    monkeypatch.setattr("agent.wiki._PAGES_DIR", tmp_path / "pages")
    monkeypatch.setattr("agent.wiki._FRAGMENTS_DIR", tmp_path / "fragments")
    meta = {"category": "email", "quality": "developing", "fragment_count": 7,
            "fragment_ids": [], "last_synthesized": "2026-04-30", "aspects_covered": "workflow_steps"}
    _write_page(tmp_path / "pages", "email", meta, "## Workflow steps\nStep 1.")

    result = load_wiki_patterns("email", include_negatives=False)
    assert "draft" not in result.lower()


def test_page_without_meta_treated_as_nascent(tmp_path, monkeypatch):
    monkeypatch.setattr("agent.wiki._PAGES_DIR", tmp_path / "pages")
    monkeypatch.setattr("agent.wiki._FRAGMENTS_DIR", tmp_path / "fragments")
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "email.md").write_text("## Workflow steps\nStep 1.", encoding="utf-8")

    result = load_wiki_patterns("email", include_negatives=False)
    assert "draft" in result.lower()
```

- [ ] **Step 2: Запустить — убедиться что падает**

```bash
uv run pytest tests/test_wiki_quality_header.py -v
```

- [ ] **Step 3: Обновить `load_wiki_patterns` в `agent/wiki.py`**

Найти функцию `load_wiki_patterns` (строка ~304). Заменить на:

```python
def load_wiki_patterns(task_type: str, include_negatives: bool = True) -> str:
    """Load patterns page for the given task type.

    include_negatives=True (default) appends a KNOWN DEAD ENDS block.
    Nascent pages (fragment_count < 5) get a [draft — limited data] marker.
    """
    page_name = _TYPE_TO_PAGE.get(task_type, task_type)
    content = _read_page(page_name)
    parts = []
    if content:
        meta = _read_page_meta_from_content(content)
        quality = meta.get("quality", "nascent")
        header = f"## Wiki: {task_type} Patterns"
        if quality == "nascent":
            header += " [draft — limited data]"
        parts.append(f"{header}\n{content}")
    if include_negatives:
        negatives = _load_dead_ends(task_type)
        if negatives:
            parts.append(negatives)
    return "\n\n".join(parts)
```

- [ ] **Step 4: Запустить тесты**

```bash
uv run pytest tests/test_wiki_quality_header.py -v
```

Ожидается: все PASSED.

- [ ] **Step 5: Полный прогон**

```bash
uv run pytest tests/ -x -q
```

- [ ] **Step 6: Коммит**

```bash
git add agent/wiki.py tests/test_wiki_quality_header.py
git commit -m "feat(wiki): load_wiki_patterns adds [draft] header for nascent quality pages"
```

---

## Task 6: wiki_mature тег в _run_pages_lint_pass

**Files:**
- Modify: `agent/wiki.py` — функция `_run_pages_lint_pass`
- Modify: `tests/test_wiki_pages_lint.py` — добавить тест

- [ ] **Step 1: Написать дополнительный тест в существующий файл**

Добавить в конец `tests/test_wiki_pages_lint.py`:

```python
def test_pages_lint_pass_adds_wiki_mature_tag_for_mature_page(tmp_path, monkeypatch):
    """Nodes from mature pages get the wiki_mature tag."""
    from agent.wiki import _write_page_meta
    meta = {"category": "email", "quality": "mature", "fragment_count": 20,
            "fragment_ids": [], "last_synthesized": "2026-04-30", "aspects_covered": "workflow_steps"}
    meta_header = _write_page_meta(meta)
    mature_page = meta_header + "\n\n" + SAMPLE_PAGE

    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "email.md").write_text(mature_page, encoding="utf-8")

    monkeypatch.setattr("agent.wiki._PAGES_DIR", pages_dir)
    monkeypatch.setattr("agent.wiki._GRAPH_AUTOBUILD", True)

    fake_deltas_obj = {
        "graph_deltas": {
            "new_rules": [{"text": "read seq before write", "tags": ["email"], "confidence": 0.7}],
            "new_insights": [], "antipatterns": [],
        }
    }
    llm_response = "```json\n" + json.dumps(fake_deltas_obj) + "\n```"
    graph_module = _make_graph_module(["r_abc123"])
    graph_state = Graph()

    with patch("agent.dispatch.call_llm_raw", return_value=llm_response):
        _run_pages_lint_pass(graph_module, graph_state, model="test-model", cfg={})

    call_args = graph_module.merge_updates.call_args[0]
    deltas_arg = call_args[1]
    rules = deltas_arg.get("new_rules", [])
    assert any("wiki_mature" in r.get("tags", []) for r in rules), \
        f"wiki_mature tag missing from rules: {rules}"


def test_pages_lint_pass_no_wiki_mature_for_nascent_page(tmp_path, monkeypatch):
    """Nodes from nascent pages do NOT get the wiki_mature tag."""
    from agent.wiki import _write_page_meta
    meta = {"category": "email", "quality": "nascent", "fragment_count": 2,
            "fragment_ids": [], "last_synthesized": "2026-04-30", "aspects_covered": "workflow_steps"}
    meta_header = _write_page_meta(meta)
    nascent_page = meta_header + "\n\n" + SAMPLE_PAGE

    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "email.md").write_text(nascent_page, encoding="utf-8")

    monkeypatch.setattr("agent.wiki._PAGES_DIR", pages_dir)
    monkeypatch.setattr("agent.wiki._GRAPH_AUTOBUILD", True)

    fake_deltas_obj = {
        "graph_deltas": {
            "new_rules": [{"text": "read seq before write", "tags": ["email"], "confidence": 0.7}],
            "new_insights": [], "antipatterns": [],
        }
    }
    llm_response = "```json\n" + json.dumps(fake_deltas_obj) + "\n```"
    graph_module = _make_graph_module(["r_abc123"])
    graph_state = Graph()

    with patch("agent.dispatch.call_llm_raw", return_value=llm_response):
        _run_pages_lint_pass(graph_module, graph_state, model="test-model", cfg={})

    call_args = graph_module.merge_updates.call_args[0]
    deltas_arg = call_args[1]
    rules = deltas_arg.get("new_rules", [])
    assert not any("wiki_mature" in r.get("tags", []) for r in rules), \
        f"wiki_mature should NOT be in nascent page rules: {rules}"
```

- [ ] **Step 2: Запустить — убедиться что новые тесты падают**

```bash
uv run pytest tests/test_wiki_pages_lint.py -v -k "mature"
```

- [ ] **Step 3: Обновить `_run_pages_lint_pass` в `agent/wiki.py`**

Найти блок где добавляется `wiki_page` тег (строки ~1160-1167). После добавления `wiki_page` тега добавить логику `wiki_mature`:

```python
            _stamp_category_tag(deltas, category)
            # Read page meta to determine quality
            page_meta = _read_page_meta_from_content(content)
            is_mature = page_meta.get("quality") == "mature"

            for key in ("new_insights", "new_rules", "antipatterns"):
                for item in (deltas.get(key) or []):
                    if not isinstance(item, dict):
                        continue
                    tags = list(item.get("tags") or [])
                    if "wiki_page" not in tags:
                        tags.append("wiki_page")
                    if is_mature and "wiki_mature" not in tags:
                        tags.append("wiki_mature")
                    item["tags"] = tags
```

- [ ] **Step 4: Запустить тесты**

```bash
uv run pytest tests/test_wiki_pages_lint.py -v
```

Ожидается: все PASSED.

- [ ] **Step 5: Полный прогон**

```bash
uv run pytest tests/ -x -q
```

- [ ] **Step 6: Коммит**

```bash
git add agent/wiki.py tests/test_wiki_pages_lint.py
git commit -m "feat(wiki): add wiki_mature tag in pages-lint-pass for mature quality pages"
```

---

## Task 7: Quality-aware evaluator

**Files:**
- Modify: `agent/evaluator.py` — функция `_load_reference_patterns`
- Create: `tests/test_evaluator_wiki_quality.py`

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_evaluator_wiki_quality.py
from pathlib import Path
from unittest.mock import patch
from agent.evaluator import _load_reference_patterns
from agent.wiki import _write_page_meta


def _make_page(pages_dir: Path, name: str, quality: str, fragment_count: int) -> None:
    pages_dir.mkdir(parents=True, exist_ok=True)
    meta = {"category": name, "quality": quality, "fragment_count": fragment_count,
            "fragment_ids": [], "last_synthesized": "2026-04-30", "aspects_covered": "workflow_steps"}
    body = "## Workflow steps\n" + ("Step X.\n" * 50)  # ~50 lines of content
    content = _write_page_meta(meta) + "\n\n" + body
    (pages_dir / f"{name}.md").write_text(content, encoding="utf-8")


def test_nascent_page_truncated_to_short_limit(tmp_path, monkeypatch):
    monkeypatch.setattr("agent.wiki._PAGES_DIR", tmp_path / "pages")
    monkeypatch.setattr("agent.wiki._FRAGMENTS_DIR", tmp_path / "fragments")
    monkeypatch.setattr("agent.evaluator._WIKI_EVAL_ENABLED", True)
    _make_page(tmp_path / "pages", "email", "nascent", 2)

    result = _load_reference_patterns("email")
    assert len(result) <= 600, f"nascent page should be truncated to ≤600 chars, got {len(result)}"


def test_mature_page_has_higher_limit(tmp_path, monkeypatch):
    monkeypatch.setattr("agent.wiki._PAGES_DIR", tmp_path / "pages")
    monkeypatch.setattr("agent.wiki._FRAGMENTS_DIR", tmp_path / "fragments")
    monkeypatch.setattr("agent.evaluator._WIKI_EVAL_ENABLED", True)
    _make_page(tmp_path / "pages", "email", "mature", 20)

    result = _load_reference_patterns("email")
    # Mature gets up to 4000 chars — 50 lines of "Step X.\n" is ~500 chars, fits fully
    assert len(result) > 0
    assert "Step X." in result


def test_wiki_eval_disabled_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("agent.evaluator._WIKI_EVAL_ENABLED", False)
    result = _load_reference_patterns("email")
    assert result == ""
```

- [ ] **Step 2: Запустить — убедиться что падают**

```bash
uv run pytest tests/test_evaluator_wiki_quality.py -v
```

- [ ] **Step 3: Обновить `_load_reference_patterns` в `agent/evaluator.py`**

Найти функцию `_load_reference_patterns` (строка ~350). Заменить на:

```python
# Char limits per wiki quality level
_WIKI_CHARS_NASCENT    = int(os.environ.get("EVALUATOR_WIKI_MAX_CHARS_NASCENT",    "500"))
_WIKI_CHARS_DEVELOPING = int(os.environ.get("EVALUATOR_WIKI_MAX_CHARS_DEVELOPING", "2000"))
_WIKI_CHARS_MATURE     = int(os.environ.get("EVALUATOR_WIKI_MAX_CHARS_MATURE",     "4000"))

_QUALITY_CHAR_LIMITS = {
    "nascent":    _WIKI_CHARS_NASCENT,
    "developing": _WIKI_CHARS_DEVELOPING,
    "mature":     _WIKI_CHARS_MATURE,
}


def _load_reference_patterns(task_type: str) -> str:
    """Load wiki patterns for evaluator, truncated by page quality level.

    nascent   → max 500 chars (limited data, don't over-weight)
    developing → max 2000 chars
    mature    → max 4000 chars
    """
    if not _WIKI_EVAL_ENABLED:
        return ""
    try:
        from .wiki import load_wiki_patterns, _read_page_meta, _TYPE_TO_PAGE
        page_name = _TYPE_TO_PAGE.get(task_type, task_type)
        meta = _read_page_meta(page_name)
        quality = meta.get("quality", "nascent")
        char_limit = _QUALITY_CHAR_LIMITS.get(quality, _WIKI_CHARS_DEVELOPING)
        patterns = load_wiki_patterns(task_type, include_negatives=False) or ""
        if len(patterns) > char_limit:
            patterns = patterns[:char_limit] + "\n...(truncated)"
        return patterns
    except Exception as exc:
        print(f"{CLI_YELLOW}[evaluator] wiki load failed ({exc}) — skipping patterns{CLI_CLR}")
        return ""
```

- [ ] **Step 4: Запустить тесты**

```bash
uv run pytest tests/test_evaluator_wiki_quality.py -v
```

Ожидается: все PASSED.

- [ ] **Step 5: Полный прогон**

```bash
uv run pytest tests/ -x -q
```

Ожидается: все тесты проходят.

- [ ] **Step 6: Финальный коммит**

```bash
git add agent/evaluator.py tests/test_evaluator_wiki_quality.py
git commit -m "feat(wiki): quality-aware evaluator wiki char limits (nascent=500, developing=2000, mature=4000)"
```

---

## Self-Review

**Spec coverage:**
- ✅ Add-only synthesis — Task 3 (`_llm_synthesize_aspects` с инструкцией "не удалять")
- ✅ Provenance tracking — Task 4 (`fragment_ids` в meta, обновляется в `run_wiki_lint`)
- ✅ knowledge_aspects в task_types.json — Task 1
- ✅ Quality lifecycle (nascent/developing/mature) — Task 2 (`_page_quality`)
- ✅ [draft] маркер для nascent — Task 5
- ✅ wiki_mature тег в граф — Task 6
- ✅ Evaluator quality-aware — Task 7
- ✅ Promoted sections (Successful pattern, Verified refusal) — сохраняются через `_assemble_page_from_sections` (Task 3)
- ✅ `wiki_graph.py` не меняется — план не трогает этот файл

**Типовая согласованность:**
- `_read_page_meta_from_content(content: str) -> dict` — используется в Task 2 тестах и в Task 4/6 реализации ✅
- `_page_quality(fragment_count: int) -> str` — используется в Task 4 (`run_wiki_lint`) и Task 2 тестах ✅
- `knowledge_aspects(type_name: str) -> list[dict]` — используется в Task 4 (`run_wiki_lint`) и Task 1 тестах ✅
- `_llm_synthesize_aspects(existing_sections, new_entries, aspects, model, cfg) -> dict[str, str]` — Task 3 реализация, Task 3 тест ✅
- `_assemble_page_from_sections(meta, sections, aspects) -> str` — Task 3 реализация и тест ✅
