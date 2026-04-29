# Wiki↔Graph Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Закрыть три разрыва wiki↔graph: страницы → граф, рёбра между узлами, ошибки → граф.

**Architecture:** Три независимых патча в `agent/wiki.py` и `agent/wiki_graph.py`. Патч 1 расширяет `merge_updates` — добавляет text-ref resolution и детерминированные рёбра. Патч 2 добавляет `_run_pages_lint_pass` в конец `run_wiki_lint`. Патч 3 добавляет `_ingest_error_fragments` без LLM-вызова.

**Tech Stack:** Python 3.11+, pathlib, re, `agent/wiki_graph.py:merge_updates`, `agent/wiki.py:run_wiki_lint/_llm_synthesize`.

**FIX labels:** FIX-411 (рёбра), FIX-412 (страницы→граф), FIX-413 (ошибки→граф).

---

## Файлы, затрагиваемые планом

| Файл | Действие |
|------|----------|
| `agent/wiki_graph.py` | modify `merge_updates` (lines 135–208) |
| `agent/wiki.py` | modify `_GRAPH_INSTRUCTION_SUFFIX` (lines 55–67), add `_PAGES_GRAPH_PROMPT`, add `_run_pages_lint_pass`, add `_ingest_error_fragments`, modify `run_wiki_lint` tail |
| `.env.example` | add `WIKI_GRAPH_ERRORS_INGEST` |
| `tests/test_wiki_graph_edges.py` | create — тесты для рёбер |
| `tests/test_wiki_pages_lint.py` | create — тесты для pages lint pass |
| `tests/test_wiki_error_ingest.py` | create — тесты для error ingest |

---

## Task 1: Детерминированные рёбра в `merge_updates` (FIX-411)

**Files:**
- Modify: `agent/wiki_graph.py:149-208`
- Create: `tests/test_wiki_graph_edges.py`

- [ ] **Step 1.1: Написать падающий тест**

Создай `tests/test_wiki_graph_edges.py`:

```python
"""Tests for FIX-411: deterministic and text-reference edges in merge_updates."""
from agent.wiki_graph import Graph, merge_updates


def test_deterministic_edge_antipattern_conflicts_with_rule():
    """antipattern and rule with overlapping tags in same batch → conflicts_with edge."""
    g = Graph()
    updates = {
        "antipatterns": [{"text": "avoid reading twice", "tags": ["email"]}],
        "new_rules":    [{"text": "read before write", "tags": ["email"]}],
    }
    merge_updates(g, updates)
    rels = [(e["from"], e["rel"], e["to"]) for e in g.edges]
    # There should be exactly one conflicts_with edge
    conflicts = [r for r in rels if r[1] == "conflicts_with"]
    assert len(conflicts) == 1, f"expected 1 conflicts_with edge, got: {rels}"
    # from = antipattern, to = rule
    apt_nid, _, rule_nid = conflicts[0]
    assert g.nodes[apt_nid]["type"] == "antipattern"
    assert g.nodes[rule_nid]["type"] == "rule"


def test_deterministic_edge_not_built_when_tags_disjoint():
    """No edge when antipattern and rule have no tag overlap."""
    g = Graph()
    updates = {
        "antipatterns": [{"text": "avoid reading twice", "tags": ["email"]}],
        "new_rules":    [{"text": "read before write", "tags": ["lookup"]}],
    }
    merge_updates(g, updates)
    assert g.edges == [], f"unexpected edges: {g.edges}"


def test_no_duplicate_deterministic_edges():
    """Calling merge_updates twice does not duplicate the edge."""
    g = Graph()
    updates = {
        "antipatterns": [{"text": "avoid reading twice", "tags": ["email"]}],
        "new_rules":    [{"text": "read before write", "tags": ["email"]}],
    }
    merge_updates(g, updates)
    merge_updates(g, updates)  # second call — nodes bump, edges must not duplicate
    conflicts = [e for e in g.edges if e["rel"] == "conflicts_with"]
    assert len(conflicts) == 1, f"duplicate edges: {g.edges}"
```

- [ ] **Step 1.2: Запустить тест — убедиться что падает**

```bash
uv run pytest tests/test_wiki_graph_edges.py -v
```

Ожидаем: FAIL — `assert len(conflicts) == 1` fails (нет детерминированных рёбер).

- [ ] **Step 1.3: Реализовать изменение в `merge_updates`**

Открой `agent/wiki_graph.py`. Замени функцию `merge_updates` (строки 135–208) полностью:

```python
def merge_updates(g: Graph, updates: dict) -> list[str]:
    """Merge reflector-extracted deltas into the graph.

    updates schema (any key optional):
        {
          "new_insights":  [{"text": str, "tags": [str], "confidence": float}],
          "new_rules":     [{"text": str, "tags": [str]}],
          "antipatterns":  [{"text": str, "tags": [str]}],
          "reused_patterns": [str],   # existing node ids to bump uses
          "edges":         [{"from": str, "rel": str, "to": str}],
                            # "from"/"to" may be node IDs or node text (FIX-411)
        }

    Returns the list of node ids that were touched (new or bumped).
    """
    touched: list[str] = []
    today = time.strftime("%Y-%m-%d")

    # FIX-411: track batch nodes by type for deterministic edge building
    batch_antipatterns: list[str] = []
    batch_rules: list[str] = []

    def _upsert(kind: str, prefix: str, item: dict) -> str:
        text = (item.get("text") or "").strip()
        if not text:
            return ""
        nid = _mk_node_id(prefix, text)
        tags = item.get("tags") or []
        if nid in g.nodes:
            n = g.nodes[nid]
            n["uses"] = int(n.get("uses", 0)) + 1
            n["last_seen"] = today
            existing_tags = set(n.get("tags", []))
            existing_tags.update(tags)
            n["tags"] = sorted(existing_tags)
            conf = float(n.get("confidence", _DEFAULT_CONFIDENCE))
            n["confidence"] = min(1.0, conf + 0.02)
        else:
            g.nodes[nid] = {
                "type": kind,
                "tags": sorted(set(tags)),
                "text": text,
                "confidence": float(item.get("confidence", _DEFAULT_CONFIDENCE)),
                "uses": 1,
                "last_seen": today,
            }
        return nid

    for item in updates.get("new_insights", []) or []:
        nid = _upsert("insight", "n", item)
        if nid:
            touched.append(nid)
    for item in updates.get("new_rules", []) or []:
        nid = _upsert("rule", "r", item)
        if nid:
            touched.append(nid)
            batch_rules.append(nid)
    for item in updates.get("antipatterns", []) or []:
        nid = _upsert("antipattern", "a", item)
        if nid:
            touched.append(nid)
            batch_antipatterns.append(nid)

    for reused_id in updates.get("reused_patterns", []) or []:
        if reused_id in g.nodes:
            n = g.nodes[reused_id]
            n["uses"] = int(n.get("uses", 0)) + 1
            n["last_seen"] = today
            touched.append(reused_id)

    # FIX-411: edge handling — supports both node-ID and text references.
    # Build text→nid lookup so LLM can reference nodes by their text.
    text_to_nid = {
        _normalize(n["text"]): nid
        for nid, n in g.nodes.items()
        if n.get("text")
    }

    existing_edges = {(e.get("from"), e.get("rel"), e.get("to")) for e in g.edges}

    def _resolve_nid(ref: str) -> str:
        if ref in g.nodes:
            return ref
        return text_to_nid.get(_normalize(ref), "")

    for e in updates.get("edges", []) or []:
        from_nid = _resolve_nid(e.get("from") or "")
        to_nid = _resolve_nid(e.get("to") or "")
        rel = e.get("rel") or ""
        if not (from_nid and rel and to_nid):
            continue
        key = (from_nid, rel, to_nid)
        if key not in existing_edges:
            g.edges.append({"from": from_nid, "rel": rel, "to": to_nid})
            existing_edges.add(key)

    # FIX-411: deterministic edges — antipattern →conflicts_with→ rule when tags overlap.
    # Only within the current batch to avoid O(n²) over the entire graph.
    for apt_nid in batch_antipatterns:
        apt_tags = set(g.nodes[apt_nid].get("tags", []))
        for rule_nid in batch_rules:
            rule_tags = set(g.nodes[rule_nid].get("tags", []))
            if apt_tags & rule_tags:
                key = (apt_nid, "conflicts_with", rule_nid)
                if key not in existing_edges:
                    g.edges.append({"from": apt_nid, "rel": "conflicts_with", "to": rule_nid})
                    existing_edges.add(key)

    return touched
```

- [ ] **Step 1.4: Запустить тест — убедиться что проходит**

```bash
uv run pytest tests/test_wiki_graph_edges.py -v
```

Ожидаем: PASS для всех трёх тестов.

- [ ] **Step 1.5: Прогнать существующие тесты графа**

```bash
uv run pytest tests/test_wiki_graph_scoring.py tests/regression/test_wiki_graph_deltas.py -v
```

Ожидаем: все PASS.

- [ ] **Step 1.6: Коммит**

```bash
git add agent/wiki_graph.py tests/test_wiki_graph_edges.py
git commit -m "feat(graph): FIX-411 deterministic edges and text-ref resolution in merge_updates"
```

---

## Task 2: LLM text-edge resolution — тест + `_GRAPH_INSTRUCTION_SUFFIX` (FIX-411 продолжение)

**Files:**
- Modify: `agent/wiki.py:55-67` (`_GRAPH_INSTRUCTION_SUFFIX`)
- Modify: `tests/test_wiki_graph_edges.py` (добавить тест)

- [ ] **Step 2.1: Добавить тест на text-ref edges**

Дозапиши в `tests/test_wiki_graph_edges.py`:

```python
def test_text_reference_edge_resolved():
    """LLM may emit edges with text refs instead of node IDs — must resolve."""
    g = Graph()
    # First upsert the nodes
    updates = {
        "new_rules":    [{"text": "read before write", "tags": ["email"]}],
        "antipatterns": [{"text": "avoid reading twice", "tags": ["email"]}],
        "edges": [
            {
                "from": "avoid reading twice",   # text reference, not ID
                "rel": "conflicts_with",
                "to": "read before write",        # text reference, not ID
            }
        ],
    }
    merge_updates(g, updates)
    assert len(g.edges) >= 1
    rels = {e["rel"] for e in g.edges}
    assert "conflicts_with" in rels


def test_invalid_text_reference_edge_silently_dropped():
    """Edge referencing non-existent text is silently ignored (fail-open)."""
    g = Graph()
    updates = {
        "new_rules": [{"text": "read before write", "tags": ["email"]}],
        "edges": [
            {"from": "this node does not exist", "rel": "requires", "to": "read before write"}
        ],
    }
    merge_updates(g, updates)
    # Invalid edge dropped, valid node exists
    assert len(g.nodes) == 1
    assert g.edges == []
```

- [ ] **Step 2.2: Запустить — убедиться что тесты проходят** (text-ref уже работает после Task 1)

```bash
uv run pytest tests/test_wiki_graph_edges.py -v
```

Ожидаем: все PASS.

- [ ] **Step 2.3: Расширить `_GRAPH_INSTRUCTION_SUFFIX` в `agent/wiki.py`**

Замени строки 55–67 в `agent/wiki.py`:

```python
_GRAPH_INSTRUCTION_SUFFIX = (
    "\n\nAfter the merged Markdown, append a fenced JSON block describing "
    "graph deltas for this category (used by the knowledge graph index):\n"
    "```json\n"
    "{\"graph_deltas\": {\n"
    "  \"new_insights\": [{\"text\": \"<≤120 chars>\", \"tags\": [\"<category>\"], \"confidence\": 0.5}],\n"
    "  \"new_rules\":     [{\"text\": \"<≤120 chars>\", \"tags\": [\"<category>\"]}],\n"
    "  \"antipatterns\":  [{\"text\": \"<≤120 chars>\", \"tags\": [\"<category>\"]}],\n"
    "  \"edges\":         [{\"from\": \"<text of node A>\", \"rel\": \"requires|conflicts_with|generalizes|precedes\", \"to\": \"<text of node B>\"}]\n"
    "}}\n"
    "```\n"
    "Rules: 1-line text only; max 6 items per array; do not duplicate items "
    "already on the existing page; if nothing worth recording, output empty arrays. "
    "Edges: reference nodes by their exact text; only emit edges between nodes in this delta."
)
```

- [ ] **Step 2.4: Коммит**

```bash
git add agent/wiki.py tests/test_wiki_graph_edges.py
git commit -m "feat(wiki): FIX-411 add edges field to _GRAPH_INSTRUCTION_SUFFIX"
```

---

## Task 3: `_ingest_error_fragments` без LLM (FIX-413)

**Files:**
- Modify: `agent/wiki.py` — добавить функцию после `_load_dead_ends` (~line 351)
- Modify: `agent/wiki.py` — добавить `_GRAPH_ERRORS_INGEST` константу (~line 46)
- Create: `tests/test_wiki_error_ingest.py`

- [ ] **Step 3.1: Написать падающий тест**

Создай `tests/test_wiki_error_ingest.py`:

```python
"""Tests for FIX-413: _ingest_error_fragments without LLM."""
import pytest
from pathlib import Path
from agent.wiki import _ingest_error_fragments, _ARCHIVE_DIR


def _write_error_frag(tmp_path: Path, category: str, filename: str, content: str) -> Path:
    d = tmp_path / "errors" / category
    d.mkdir(parents=True, exist_ok=True)
    p = d / filename
    p.write_text(content, encoding="utf-8")
    return p


DEAD_END_FRAGMENT = """\
---
task_id: t11
task_type: email
outcome: OUTCOME_NONE_CLARIFICATION
date: 2026-04-29
task: 'Write email to sam@example.com'
---

DONE OPS:
(none)

STEP FACTS:
- stall:  → You have taken 6 steps without writing

## Dead end: t11
Outcome: OUTCOME_NONE_CLARIFICATION
What failed:
- stall(/outbox): You have taken 6 steps without writing anything meaningful
"""

LEGACY_FRAGMENT = """\
---
task_id: t09
task_type: email
outcome: OUTCOME_FAIL
date: 2026-04-28
task: 'some task'
---

STEP FACTS:
- stall:  → repeated search with no results found
"""


def test_ingest_dead_end_format(tmp_path, monkeypatch):
    """Dead-end block format produces antipattern item."""
    monkeypatch.setattr("agent.wiki._ARCHIVE_DIR", tmp_path)
    _write_error_frag(tmp_path, "email", "t11_001.md", DEAD_END_FRAGMENT)

    items = _ingest_error_fragments("email")
    assert len(items) == 1
    item = items[0]
    assert item["confidence"] == 0.4
    assert "email" in item["tags"]
    assert len(item["text"]) > 5
    # Entity data scrubbed: sam@example.com should not appear
    assert "sam@example.com" not in item["text"]


def test_ingest_legacy_format(tmp_path, monkeypatch):
    """Legacy fragment (no dead-end block) falls back to outcome+stall."""
    monkeypatch.setattr("agent.wiki._ARCHIVE_DIR", tmp_path)
    _write_error_frag(tmp_path, "email", "t09_001.md", LEGACY_FRAGMENT)

    items = _ingest_error_fragments("email")
    assert len(items) == 1
    assert items[0]["confidence"] == 0.4


def test_ingest_respects_n_limit(tmp_path, monkeypatch):
    """Only last N files by mtime are processed."""
    monkeypatch.setattr("agent.wiki._ARCHIVE_DIR", tmp_path)
    for i in range(15):
        _write_error_frag(tmp_path, "email", f"t{i:02d}_001.md", DEAD_END_FRAGMENT)

    items = _ingest_error_fragments("email", n=5)
    assert len(items) <= 5


def test_ingest_missing_category_returns_empty(tmp_path, monkeypatch):
    """Missing category directory returns empty list without error."""
    monkeypatch.setattr("agent.wiki._ARCHIVE_DIR", tmp_path)
    items = _ingest_error_fragments("nonexistent_category")
    assert items == []
```

- [ ] **Step 3.2: Запустить тест — убедиться что падает**

```bash
uv run pytest tests/test_wiki_error_ingest.py -v
```

Ожидаем: FAIL — `ImportError: cannot import name '_ingest_error_fragments'`.

- [ ] **Step 3.3: Добавить константу `_GRAPH_ERRORS_INGEST` в `agent/wiki.py`**

После строки 43 (`_GRAPH_AUTOBUILD = ...`) добавь:

```python
# FIX-413: ingest archived error fragments as antipattern nodes (no LLM).
_GRAPH_ERRORS_INGEST = os.environ.get("WIKI_GRAPH_ERRORS_INGEST", "0") == "1"
```

- [ ] **Step 3.4: Добавить функцию `_ingest_error_fragments` в `agent/wiki.py`**

После функции `_load_dead_ends` (~строка 351), перед `_ENTITY_PATTERNS`, вставь:

```python
def _ingest_error_fragments(category: str, n: int = 10) -> list[dict]:
    """FIX-413: parse archived error fragments into antipattern dicts without LLM.

    Reads last N files from archive/errors/{category}/ by mtime (newest first).
    Returns a list of {"text": ..., "tags": [...], "confidence": 0.4} dicts
    suitable for merge_updates(g, {"antipatterns": items}).
    """
    archive_dir = _ARCHIVE_DIR / "errors" / category
    if not archive_dir.exists():
        return []
    try:
        frags = sorted(
            archive_dir.glob("*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:n]
    except OSError:
        return []

    items: list[dict] = []
    for frag_path in frags:
        try:
            text = frag_path.read_text(encoding="utf-8")

            # Try structured dead-end block (FIX-410 format).
            dead_m = re.search(
                r"^## Dead end: \S+\nOutcome: \S+\nWhat failed:\n(.*?)(?=\n## |\Z)",
                text, re.MULTILINE | re.DOTALL,
            )
            if dead_m:
                lines = dead_m.group(1).strip().splitlines()
                first = re.sub(r"^-\s*", "", lines[0]).strip() if lines else ""
                apt_text = first[:120]
            else:
                # Legacy: outcome + first stall description.
                outcome_m = re.search(r"^outcome: (\S+)", text, re.MULTILINE)
                stall_m = re.search(r"- stall:.*?→ (.{10,80})", text)
                outcome = outcome_m.group(1) if outcome_m else "OUTCOME_FAIL"
                stall = stall_m.group(1).strip() if stall_m else ""
                apt_text = f"{outcome}: {stall[:80]}" if stall else outcome

            apt_text = _scrub_entity(apt_text.strip())
            if apt_text and len(apt_text) > 10:
                items.append({"text": apt_text, "tags": [category], "confidence": 0.4})
        except Exception:
            continue

    return items
```

- [ ] **Step 3.5: Запустить тест — убедиться что проходит**

```bash
uv run pytest tests/test_wiki_error_ingest.py -v
```

Ожидаем: все 4 теста PASS.

- [ ] **Step 3.6: Коммит**

```bash
git add agent/wiki.py tests/test_wiki_error_ingest.py
git commit -m "feat(wiki): FIX-413 _ingest_error_fragments — antipattern nodes from error archive"
```

---

## Task 4: `_run_pages_lint_pass` — pages → граф (FIX-412)

**Files:**
- Modify: `agent/wiki.py` — добавить `_PAGES_GRAPH_PROMPT` и `_run_pages_lint_pass`
- Create: `tests/test_wiki_pages_lint.py`

- [ ] **Step 4.1: Написать падающий тест**

Создай `tests/test_wiki_pages_lint.py`:

```python
"""Tests for FIX-412: _run_pages_lint_pass — pages → graph."""
from unittest.mock import patch, MagicMock
from pathlib import Path
from agent.wiki import _run_pages_lint_pass
from agent.wiki_graph import Graph


SAMPLE_PAGE = """\
## Successful pattern: send email

1. Read /outbox/seq.json to get next id.
2. Write email JSON to /outbox/{id}.json.
3. Increment seq and write back.

## Key rules

- Always read seq.json before writing to determine the correct filename.
- Do not overwrite existing emails.
"""


def _make_graph_module(touched_ids):
    """Fake graph module that records merge_updates calls."""
    gm = MagicMock()
    gm.merge_updates.return_value = touched_ids
    return gm


def test_pages_lint_pass_calls_merge_updates(tmp_path, monkeypatch):
    """_run_pages_lint_pass reads a page and calls merge_updates with deltas."""
    # Write a sample page
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "email.md").write_text(SAMPLE_PAGE, encoding="utf-8")

    monkeypatch.setattr("agent.wiki._PAGES_DIR", pages_dir)
    monkeypatch.setattr("agent.wiki._GRAPH_AUTOBUILD", True)

    fake_deltas = {
        "graph_deltas": {
            "new_rules": [{"text": "read seq.json before write", "tags": ["email"], "confidence": 0.7}],
            "new_insights": [],
            "antipatterns": [],
        }
    }
    import json
    llm_response = "```json\n" + json.dumps(fake_deltas) + "\n```"

    graph_module = _make_graph_module(["r_abc123"])
    graph_state = Graph()

    with patch("agent.wiki._llm_synthesize", return_value=("", fake_deltas["graph_deltas"])) as mock_synth:
        _run_pages_lint_pass(graph_module, graph_state, model="test-model", cfg={})

    graph_module.merge_updates.assert_called_once()
    call_args = graph_module.merge_updates.call_args[0]
    deltas_arg = call_args[1]
    rules = deltas_arg.get("new_rules", [])
    assert any("wiki_page" in r.get("tags", []) for r in rules), \
        f"wiki_page tag missing from rules: {rules}"


def test_pages_lint_pass_skips_empty_page(tmp_path, monkeypatch):
    """Empty pages are skipped without calling merge_updates."""
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "email.md").write_text("", encoding="utf-8")

    monkeypatch.setattr("agent.wiki._PAGES_DIR", pages_dir)
    monkeypatch.setattr("agent.wiki._GRAPH_AUTOBUILD", True)

    graph_module = _make_graph_module([])
    graph_state = Graph()

    with patch("agent.wiki._llm_synthesize", return_value=("", {})):
        _run_pages_lint_pass(graph_module, graph_state, model="test-model", cfg={})

    graph_module.merge_updates.assert_not_called()


def test_pages_lint_pass_skipped_when_autobuild_off(tmp_path, monkeypatch):
    """When _GRAPH_AUTOBUILD is False the pass is a no-op."""
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "email.md").write_text(SAMPLE_PAGE, encoding="utf-8")

    monkeypatch.setattr("agent.wiki._PAGES_DIR", pages_dir)
    monkeypatch.setattr("agent.wiki._GRAPH_AUTOBUILD", False)

    graph_module = _make_graph_module([])
    graph_state = Graph()

    with patch("agent.wiki._llm_synthesize") as mock_synth:
        _run_pages_lint_pass(graph_module, graph_state, model="test-model", cfg={})

    mock_synth.assert_not_called()
    graph_module.merge_updates.assert_not_called()
```

- [ ] **Step 4.2: Запустить тест — убедиться что падает**

```bash
uv run pytest tests/test_wiki_pages_lint.py -v
```

Ожидаем: FAIL — `ImportError: cannot import name '_run_pages_lint_pass'`.

- [ ] **Step 4.3: Добавить `_PAGES_GRAPH_PROMPT` и `_run_pages_lint_pass` в `agent/wiki.py`**

После константы `_GRAPH_INSTRUCTION_SUFFIX` (~строка 67) добавь промпт для pages-пасса:

```python
_PAGES_GRAPH_PROMPT = (
    "You are indexing a wiki page into a knowledge graph.\n"
    "From the Markdown page below, extract concrete insights, rules, and antipatterns.\n"
    "Focus on ## Successful pattern:, ## Verified refusal:, key rules, and pitfall sections.\n"
    "Do NOT rewrite or summarize the page.\n"
    "Output ONLY a fenced JSON block:\n"
    "```json\n"
    "{\"graph_deltas\": {\n"
    "  \"new_insights\": [{\"text\": \"<≤120 chars>\", \"tags\": [\"<category>\"], \"confidence\": 0.7}],\n"
    "  \"new_rules\":    [{\"text\": \"<≤120 chars>\", \"tags\": [\"<category>\"]}],\n"
    "  \"antipatterns\": [{\"text\": \"<≤120 chars>\", \"tags\": [\"<category>\"]}],\n"
    "  \"edges\":        [{\"from\": \"<text of A>\", \"rel\": \"requires|conflicts_with\", \"to\": \"<text of B>\"}]\n"
    "}}\n"
    "```\n"
    "Rules: 1-line text only; max 8 items per array; confidence=0.7 for verified patterns."
)
```

Затем добавь функцию в конец `agent/wiki.py` (после `_sanitize_synthesized_page`):

```python
def _run_pages_lint_pass(graph_module, graph_state, model: str, cfg: dict) -> None:
    """FIX-412: extract graph_deltas from compiled wiki pages.

    Pages contain verified/promoted patterns — confidence=0.7 (above fragment default 0.6).
    Adds 'wiki_page' tag so nodes from this pass can be identified.
    Called at end of run_wiki_lint when graph_module is available.
    """
    if not _GRAPH_AUTOBUILD:
        return
    if not _PAGES_DIR.exists():
        return
    pages = [p for p in sorted(_PAGES_DIR.glob("*.md")) if p.is_file()]
    if not pages:
        return

    n_touched = 0
    for page_path in pages:
        category = page_path.stem  # "email", "lookup", etc.
        try:
            content = page_path.read_text(encoding="utf-8")
            if not content.strip():
                continue
            # Use _llm_synthesize with pages prompt — reuse existing dispatch + retry logic.
            # Temporarily inject the pages prompt by using category key "_pages"
            # which falls through to the _pattern_default prompt; we override here
            # by passing the prompt directly via a one-off category bucket.
            _, deltas = _llm_synthesize(
                existing="",
                new_entries=[content[:6000]],
                category=f"_pages_{category}",
                model=model,
                cfg=cfg,
            )
            if not deltas:
                continue

            # Stamp category tag and add "wiki_page" source tag.
            _stamp_category_tag(deltas, category)
            for key in ("new_insights", "new_rules", "antipatterns"):
                for item in (deltas.get(key) or []):
                    if isinstance(item, dict):
                        tags = item.get("tags") or []
                        if "wiki_page" not in tags:
                            item["tags"] = [*tags, "wiki_page"]

            try:
                touched = graph_module.merge_updates(graph_state, deltas)
                graph_module.save_graph(graph_state)
                n_touched += len(touched)
                print(f"[wiki-graph] pages-lint '{category}': touched {len(touched)} nodes")
            except Exception as exc:
                print(f"[wiki-graph] pages-lint '{category}' merge failed ({exc})")
        except Exception as exc:
            print(f"[wiki-graph] pages-lint '{category}' error ({exc}), skipping")

    if n_touched:
        print(f"[wiki-graph] pages-lint total: {n_touched} node touches")
```

**Важно:** `_llm_synthesize` с category `_pages_{name}` использует промпт `_LINT_PROMPTS["_pattern_default"]` — это НЕ pages-ориентированный промпт. Нам нужен `_PAGES_GRAPH_PROMPT`. Поэтому добавь запись в `_LINT_PROMPTS` для pages-bucket:

В `_LINT_PROMPTS` (строка 76) добавь ключ `"_pages"` (который используется как fallback для `_pages_*`):

Нет — вместо этого, измени `_llm_synthesize` вызов внутри `_run_pages_lint_pass` чтобы напрямую передавать нужный промпт. Лучший подход — вызвать `_llm_synthesize` с явно подставленным промптом через `_LINT_PROMPTS` временно, ИЛИ inline сделать LLM-вызов.

Замени вызов `_llm_synthesize` в `_run_pages_lint_pass` на:

```python
            # Use pages-specific prompt directly — no page rewrite needed.
            if not model:
                continue
            user_msg = (
                f"{_PAGES_GRAPH_PROMPT}\n\n"
                f"PAGE ({category}):\n{content[:6000]}"
            )
            try:
                from .dispatch import call_llm_raw
                response = call_llm_raw(
                    system="You are a knowledge graph curator. Output only the JSON fence block.",
                    user_msg=user_msg,
                    model=model,
                    cfg=cfg,
                    max_tokens=1000,
                    plain_text=True,
                )
            except Exception as exc:
                print(f"[wiki-graph] pages-lint '{category}' LLM failed ({exc}), skipping")
                continue

            if not response:
                continue
            _, deltas = _split_markdown_and_deltas(response)
            if not deltas:
                continue
```

Удали вызов `_llm_synthesize` из функции и используй этот блок вместо него. Финальный вид функции:

```python
def _run_pages_lint_pass(graph_module, graph_state, model: str, cfg: dict) -> None:
    """FIX-412: extract graph_deltas from compiled wiki pages.

    Pages contain verified/promoted patterns — confidence=0.7 (above default 0.6).
    Adds 'wiki_page' tag so nodes from this pass can be identified.
    Called at end of run_wiki_lint when graph_module is available.
    """
    if not _GRAPH_AUTOBUILD:
        return
    if not _PAGES_DIR.exists():
        return
    pages = [p for p in sorted(_PAGES_DIR.glob("*.md")) if p.is_file()]
    if not pages:
        return

    n_touched = 0
    for page_path in pages:
        category = page_path.stem
        try:
            content = page_path.read_text(encoding="utf-8")
            if not content.strip():
                continue
            if not model:
                continue

            user_msg = (
                f"{_PAGES_GRAPH_PROMPT}\n\n"
                f"PAGE ({category}):\n{content[:6000]}"
            )
            try:
                from .dispatch import call_llm_raw
                response = call_llm_raw(
                    system="You are a knowledge graph curator. Output only the JSON fence block.",
                    user_msg=user_msg,
                    model=model,
                    cfg=cfg,
                    max_tokens=1000,
                    plain_text=True,
                )
            except Exception as exc:
                print(f"[wiki-graph] pages-lint '{category}' LLM failed ({exc}), skipping")
                continue

            if not response:
                continue
            _, deltas = _split_markdown_and_deltas(response)
            if not deltas:
                continue

            _stamp_category_tag(deltas, category)
            for key in ("new_insights", "new_rules", "antipatterns"):
                for item in (deltas.get(key) or []):
                    if isinstance(item, dict):
                        tags = item.get("tags") or []
                        if "wiki_page" not in tags:
                            item["tags"] = [*tags, "wiki_page"]

            try:
                touched = graph_module.merge_updates(graph_state, deltas)
                graph_module.save_graph(graph_state)
                n_touched += len(touched)
                print(f"[wiki-graph] pages-lint '{category}': touched {len(touched)} nodes")
            except Exception as exc:
                print(f"[wiki-graph] pages-lint '{category}' merge failed ({exc})")
        except Exception as exc:
            print(f"[wiki-graph] pages-lint '{category}' error ({exc}), skipping")

    if n_touched:
        print(f"[wiki-graph] pages-lint total: {n_touched} node touches")
```

Затем обнови тест `test_pages_lint_pass_calls_merge_updates` — он мокает `_llm_synthesize`, но теперь надо мокать `call_llm_raw`. Замени его body:

```python
def test_pages_lint_pass_calls_merge_updates(tmp_path, monkeypatch):
    """_run_pages_lint_pass reads a page and calls merge_updates with wiki_page tag."""
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "email.md").write_text(SAMPLE_PAGE, encoding="utf-8")

    monkeypatch.setattr("agent.wiki._PAGES_DIR", pages_dir)
    monkeypatch.setattr("agent.wiki._GRAPH_AUTOBUILD", True)

    import json
    fake_deltas_obj = {
        "graph_deltas": {
            "new_rules": [{"text": "read seq.json before write", "tags": ["email"], "confidence": 0.7}],
            "new_insights": [],
            "antipatterns": [],
        }
    }
    llm_response = "```json\n" + json.dumps(fake_deltas_obj) + "\n```"

    graph_module = _make_graph_module(["r_abc123"])
    graph_state = Graph()

    with patch("agent.wiki.call_llm_raw", return_value=llm_response):
        _run_pages_lint_pass(graph_module, graph_state, model="test-model", cfg={})

    graph_module.merge_updates.assert_called_once()
    call_args = graph_module.merge_updates.call_args[0]
    deltas_arg = call_args[1]
    rules = deltas_arg.get("new_rules", [])
    assert any("wiki_page" in r.get("tags", []) for r in rules), \
        f"wiki_page tag missing: {rules}"
```

Также замени мок в `test_pages_lint_pass_skips_empty_page` на `patch("agent.wiki.call_llm_raw", return_value="")`.

Для `test_pages_lint_pass_skipped_when_autobuild_off` мок `_llm_synthesize` замени на `patch("agent.wiki.call_llm_raw")`.

- [ ] **Step 4.4: Запустить тест — убедиться что проходит**

```bash
uv run pytest tests/test_wiki_pages_lint.py -v
```

Ожидаем: все 3 теста PASS.

- [ ] **Step 4.5: Коммит**

```bash
git add agent/wiki.py tests/test_wiki_pages_lint.py
git commit -m "feat(wiki): FIX-412 _run_pages_lint_pass — pages → graph via LLM graph_deltas"
```

---

## Task 5: Подключить обе функции в `run_wiki_lint` + `.env.example`

**Files:**
- Modify: `agent/wiki.py:run_wiki_lint` (хвост функции, ~строки 808–813)
- Modify: `.env.example`

- [ ] **Step 5.1: Подключить `_run_pages_lint_pass` в `run_wiki_lint`**

В конец функции `run_wiki_lint`, после строки:
```python
    if graph_module is not None and n_total_items:
        print(
            f"[wiki-graph] run total: {n_total_items} delta items, {n_total_touched} node touches"
        )
```

Добавь:

```python
    # FIX-412: pages lint pass — extract graph_deltas from compiled pages.
    if graph_module is not None and graph_state is not None:
        try:
            _run_pages_lint_pass(graph_module, graph_state, model, cfg)
        except Exception as _plp_exc:
            print(f"[wiki-graph] pages-lint pass failed ({_plp_exc})")

    # FIX-413: error fragment ingest — antipattern nodes from archive/errors/.
    if graph_module is not None and graph_state is not None and _GRAPH_ERRORS_INGEST:
        _errors_dir = _ARCHIVE_DIR / "errors"
        _error_cats = (
            [c.name for c in _errors_dir.iterdir() if c.is_dir()]
            if _errors_dir.exists() else []
        )
        for _ec in _error_cats:
            _items = _ingest_error_fragments(_ec)
            if _items:
                try:
                    _touched = graph_module.merge_updates(graph_state, {"antipatterns": _items})
                    graph_module.save_graph(graph_state)
                    print(f"[wiki-graph] error-ingest '{_ec}': {len(_touched)} antipattern nodes")
                except Exception as _ei_exc:
                    print(f"[wiki-graph] error-ingest '{_ec}' failed ({_ei_exc})")
```

- [ ] **Step 5.2: Добавить `WIKI_GRAPH_ERRORS_INGEST` в `.env.example`**

После строки `# WIKI_GRAPH_FEEDBACK=1  ...` (~строка 111) добавь:

```
# WIKI_GRAPH_ERRORS_INGEST=0           # FIX-413: 1 = build antipattern nodes from
#                                    # archive/errors/ without LLM (conf=0.4).
#                                    # Default off — enable after first full run.
```

- [ ] **Step 5.3: Прогнать полный тест-сьют**

```bash
uv run pytest tests/ -v --ignore=tests/regression -x
```

Ожидаем: все тесты PASS. Если есть падения — исправить до коммита.

- [ ] **Step 5.4: Прогнать regression тесты**

```bash
uv run pytest tests/regression/ -v
```

Ожидаем: все PASS.

- [ ] **Step 5.5: Финальный коммит**

```bash
git add agent/wiki.py .env.example
git commit -m "feat(wiki): FIX-412/413 wire pages lint pass and error ingest into run_wiki_lint"
```

---

## Self-review чеклист (выполнен)

- [x] **Spec coverage:** все три разрыва закрыты — Task 1-2 (рёбра), Task 3 (ошибки→граф), Task 4-5 (страницы→граф)
- [x] **Placeholders:** нет TBD/TODO
- [x] **Type consistency:** `merge_updates(g: Graph, updates: dict)` → используется одинаково во всех задачах; `_ingest_error_fragments(category: str, n: int) -> list[dict]` → возвращает список dict, вызывается с `{"antipatterns": items}` в Task 5
- [x] **Примечание:** в Task 4 тест мокает `call_llm_raw` а не `_llm_synthesize` — это соответствует реализации (прямой вызов `call_llm_raw` из `_run_pages_lint_pass`)
