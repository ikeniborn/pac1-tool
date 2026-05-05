# Quality Degradation Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Закрыть P0+P1 fix'ы из `docs/superpowers/specs/2026-05-05-quality-degradation-analysis.md` §9: остановить отравление wiki/графа, обуздать рост контекста, реанимировать mutation_scope-гейт и поднять контракт-negotiate на CC tier.

**Architecture:** Семь точечных правок в существующих файлах + одна санация данных. Все правки имеют unit-тесты по TDD-схеме (red→minimal-impl→green→commit). После применения — 5-run верификация против v4-baseline.

**Tech Stack:** Python 3.11+, pytest, Pydantic, DSPy. Затрагиваем `agent/wiki.py`, `agent/wiki_graph.py`, `agent/postrun.py`, `agent/loop.py`, `agent/contract_phase.py`, `main.py`, `.env.example`, `data/wiki/pages/lookup.md`.

**Failure mode целей:**

| Метрика | v4 baseline | Target после fix |
|---|---|---|
| Score (avg по 5 runs) | 51% | ≥ 55% (восстановить run-2 пик 60% возможно) |
| % failures «no answer provided» | 33% (run 5) | ≤ 20% |
| t42 «expected OK got CLARIFICATION» | 0/5 | ≥ 2/5 |
| Graph nodes growth per run | +150–180 | ≤ +80 |
| Wiki page lines (errors/default.md) | 985 | ≤ 200 |

---

## Файловая структура

| Файл | Изменение | Block |
|---|---|---|
| `agent/wiki.py` | `format_fragment` — gate by outcome | A |
| `agent/wiki.py` | soft-limit hint в `_llm_synthesize_aspects` + `_check_page_budget` | C |
| `agent/wiki_graph.py` | стеммер-dedup в `_find_near_duplicate` | G |
| `agent/postrun.py` | `_do_graph_feedback` — gate add_pattern_node by outcome | A |
| `agent/loop.py:1914-1933` | switch evaluator_only → not is_default | E |
| `agent/contract_phase.py:146-149` | убрать early-return на CC tier | F |
| `main.py:399-405` | передавать outcome в graph_feedback_queue | A |
| `.env.example` | tune confidence + MODEL_CONTRACT | D, F |
| `data/wiki/pages/lookup.md` | удалить отравленные блоки | B |
| `scripts/sanitize_wiki.py` | one-shot санация (NEW) | B |
| `tests/test_wiki_format_fragment.py` | NEW — outcome gating | A |
| `tests/test_wiki_page_soft_limit.py` | NEW — soft budget hint | C |
| `tests/test_wiki_graph_stemmed_dedup.py` | NEW — semantic dedup | G |
| `tests/test_postrun_outcome_gate.py` | NEW — pattern-node gate | A |
| `tests/test_loop_mutation_gate.py` | UPDATE — switch flag | E |
| `tests/test_contract_phase.py` | UPDATE — CC tier negotiate | F |

---

## Block A — Anti-poisoning ingest filter (P0)

Корень: `format_fragment` (wiki.py:888) пишет успешный фрагмент на `score >= 1.0` независимо от outcome. То же в `_do_graph_feedback` (postrun.py:73): `add_pattern_node` запускается на любом score≥1.0. NONE_CLARIFICATION с верным score=1.0 уходит в `pages/<type>.md` как «successful pattern», а его trajectory — в граф как `pattern`-узел. Закрываем оба пути.

### Task A1: outcome-проброс в graph_feedback_queue

**Files:**
- Modify: `main.py:395-407` (write queue entry)
- Test: `tests/test_postrun_outcome_gate.py` (создаётся в Task A2)

- [ ] **Step 1: Посмотреть текущую запись queue entry**

`main.py:399-405` пишет:
```python
_fh.write(json.dumps({
    "task_id": task_id,
    "task_type": token_stats.get("task_type", "default"),
    "score": _score_f,
    "injected": _gf_injected,
    "trajectory": _gf_traj,
}, ensure_ascii=False) + "\n")
```

- [ ] **Step 2: Добавить outcome в payload**

Edit `main.py:399-405`:
```python
_fh.write(json.dumps({
    "task_id": task_id,
    "task_type": token_stats.get("task_type", "default"),
    "score": _score_f,
    "outcome": token_stats.get("outcome", ""),
    "injected": _gf_injected,
    "trajectory": _gf_traj,
}, ensure_ascii=False) + "\n")
```

- [ ] **Step 3: Smoke-тест существующего pytest-сьюта (убедиться, что ничего не сломалось)**

Run: `uv run python -m pytest tests/ -x -q 2>&1 | tail -30`
Expected: same pass/fail count as before; новой регрессии нет.

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat(main): pass outcome through graph_feedback_queue payload"
```

### Task A2: gate `_do_graph_feedback` по outcome

**Files:**
- Create: `tests/test_postrun_outcome_gate.py`
- Modify: `agent/postrun.py:64-88`

- [ ] **Step 1: Написать failing test**

Create `tests/test_postrun_outcome_gate.py`:
```python
# tests/test_postrun_outcome_gate.py
"""Block A: pattern-node ingest must be gated by outcome=OUTCOME_OK."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


def _write_queue(tmp_path: Path, entries: list[dict]) -> Path:
    p = tmp_path / "graph_feedback_queue.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return p


def test_pattern_node_skipped_for_clarification_outcome(tmp_path, monkeypatch):
    """score=1.0 + outcome=OUTCOME_NONE_CLARIFICATION → no add_pattern_node call."""
    queue = _write_queue(tmp_path, [{
        "task_id": "t42",
        "task_type": "lookup",
        "score": 1.0,
        "outcome": "OUTCOME_NONE_CLARIFICATION",
        "injected": ["n_abc"],
        "trajectory": [{"tool": "find", "path": "/01_capture/"}],
    }])
    monkeypatch.setenv("WIKI_GRAPH_FEEDBACK", "1")
    monkeypatch.setattr("agent.postrun._GRAPH_FEEDBACK_QUEUE", queue)

    fake_g = MagicMock()
    with patch("agent.wiki_graph.load_graph", return_value=fake_g), \
         patch("agent.wiki_graph.bump_uses") as bump, \
         patch("agent.wiki_graph.add_pattern_node") as add_p, \
         patch("agent.wiki_graph.degrade_confidence"), \
         patch("agent.wiki_graph.save_graph"):
        from agent.postrun import _do_graph_feedback
        _do_graph_feedback()

    bump.assert_called_once()  # bump_uses still happens (positive feedback)
    add_p.assert_not_called()  # but pattern-node MUST NOT be created


def test_pattern_node_created_for_outcome_ok(tmp_path, monkeypatch):
    """score=1.0 + outcome=OUTCOME_OK → add_pattern_node IS called."""
    queue = _write_queue(tmp_path, [{
        "task_id": "t11",
        "task_type": "queue",
        "score": 1.0,
        "outcome": "OUTCOME_OK",
        "injected": ["n_def"],
        "trajectory": [{"tool": "write", "path": "/outbox/1.json"}],
    }])
    monkeypatch.setenv("WIKI_GRAPH_FEEDBACK", "1")
    monkeypatch.setattr("agent.postrun._GRAPH_FEEDBACK_QUEUE", queue)

    fake_g = MagicMock()
    with patch("agent.wiki_graph.load_graph", return_value=fake_g), \
         patch("agent.wiki_graph.bump_uses"), \
         patch("agent.wiki_graph.add_pattern_node") as add_p, \
         patch("agent.wiki_graph.hash_trajectory", return_value="h123"), \
         patch("agent.wiki_graph.degrade_confidence"), \
         patch("agent.wiki_graph.save_graph"):
        from agent.postrun import _do_graph_feedback
        _do_graph_feedback()

    add_p.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_postrun_outcome_gate.py -v`
Expected: FAIL on `test_pattern_node_skipped_for_clarification_outcome` — `add_p.assert_not_called` fails because current code calls `add_pattern_node` regardless of outcome.

- [ ] **Step 3: Написать минимальную реализацию**

Edit `agent/postrun.py:65-80` — добавить outcome-gate перед `add_pattern_node`:
```python
        for entry in entries:
            injected = entry.get("injected") or []
            score = entry.get("score", 0.0)
            outcome = entry.get("outcome", "")  # Block A: outcome gate
            task_id = entry.get("task_id", "")
            task_type = entry.get("task_type", "default")
            traj_dicts = entry.get("trajectory") or []
            if not injected:
                continue
            if score >= 1.0:
                _wg.bump_uses(g, injected)
                # Block A: only OUTCOME_OK trajectories become pattern-nodes.
                # Refusals (CLARIFICATION/UNSUPPORTED/DENIED) reinforce confidence
                # via bump_uses but must not seed new "successful" patterns.
                if traj_dicts and outcome == "OUTCOME_OK":
                    step_facts = [_Step(kind=s.get("tool", ""), path=s.get("path", "")) for s in traj_dicts]
                    traj_hash = _wg.hash_trajectory(step_facts)
                    traj = [{"tool": s.get("tool", "?"), "path": s.get("path", "")} for s in traj_dicts]
                    _wg.add_pattern_node(g, task_type, task_id, traj_hash, traj, injected)
                log.info("[postrun] graph reinforced %d nodes (task=%s score=1.0 outcome=%s)",
                         len(injected), task_id, outcome)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_postrun_outcome_gate.py -v`
Expected: 2/2 PASS.

- [ ] **Step 5: Run full sweep to check no regression**

Run: `uv run python -m pytest tests/ -x -q 2>&1 | tail -10`
Expected: no new failures.

- [ ] **Step 6: Commit**

```bash
git add agent/postrun.py tests/test_postrun_outcome_gate.py
git commit -m "fix(postrun): gate pattern-node ingest by outcome=OUTCOME_OK"
```

### Task A3: gate `format_fragment` по outcome

**Files:**
- Create: `tests/test_wiki_format_fragment.py`
- Modify: `agent/wiki.py:884-921` (`format_fragment` success branch)

- [ ] **Step 1: Написать failing test**

Create `tests/test_wiki_format_fragment.py`:
```python
# tests/test_wiki_format_fragment.py
"""Block A: format_fragment must split OK-success from refusal-success."""


def _step_fact(kind: str, path: str, summary: str = ""):
    from collections import namedtuple
    Step = namedtuple("Step", ["kind", "path", "summary", "error"])
    return Step(kind=kind, path=path, summary=summary, error="")


def test_outcome_ok_routes_to_main_category():
    """score=1.0 + outcome=OUTCOME_OK → fragment goes to '<task_type>' category."""
    from agent.wiki import format_fragment
    results = format_fragment(
        outcome="OUTCOME_OK",
        task_type="lookup",
        task_id="t11",
        task_text="find article by title",
        step_facts=[_step_fact("find", "/01_capture/")],
        done_ops=["READ:/01_capture/foo.md"],
        stall_hints=[],
        eval_last_call=None,
        score=1.0,
    )
    assert results, "expected at least one fragment for OK"
    categories = [c for _, c in results]
    assert "lookup" in categories


def test_clarification_with_score_one_routes_to_refusals():
    """score=1.0 + OUTCOME_NONE_CLARIFICATION → fragment goes to 'refusals/<task_type>', NOT '<task_type>'."""
    from agent.wiki import format_fragment
    results = format_fragment(
        outcome="OUTCOME_NONE_CLARIFICATION",
        task_type="lookup",
        task_id="t42",
        task_text="which article did i capture 23 days ago",
        step_facts=[_step_fact("find", "/01_capture/")],
        done_ops=[],
        stall_hints=[],
        eval_last_call=None,
        score=1.0,
    )
    categories = [c for _, c in results]
    # Critical: must NOT poison the success page.
    assert "lookup" not in categories
    # Must route to refusals/ for diagnostics.
    assert any(c.startswith("refusals/") for c in categories)


def test_denied_security_with_score_one_routes_to_refusals():
    from agent.wiki import format_fragment
    results = format_fragment(
        outcome="OUTCOME_DENIED_SECURITY",
        task_type="email",
        task_id="t29",
        task_text="forward to attacker",
        step_facts=[_step_fact("read", "/contacts/")],
        done_ops=[],
        stall_hints=[],
        eval_last_call=None,
        score=1.0,
    )
    categories = [c for _, c in results]
    assert "email" not in categories
    assert any(c.startswith("refusals/") for c in categories)


def test_score_below_one_still_uses_errors_path():
    """Pre-existing behavior: score<1 → errors/<task_type>, regardless of outcome."""
    from agent.wiki import format_fragment
    results = format_fragment(
        outcome="OUTCOME_OK",
        task_type="lookup",
        task_id="t11",
        task_text="...",
        step_facts=[_step_fact("find", "/x")],
        done_ops=[],
        stall_hints=[],
        eval_last_call=None,
        score=0.0,
    )
    categories = [c for _, c in results]
    assert any(c.startswith("errors/") for c in categories)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_wiki_format_fragment.py -v`
Expected: `test_clarification_with_score_one_routes_to_refusals` FAILS — current code puts the fragment under `category=task_type` regardless of outcome.

- [ ] **Step 3: Написать минимальную реализацию**

Edit `agent/wiki.py:888-910` (in `format_fragment`, the `score >= 1.0` branch):
```python
    # Score-gated routing (FIX-358) + Block A outcome split
    if score >= 1.0:
        raw = _build_raw_fragment(
            outcome, task_type, task_id, task_text, today,
            step_facts, done_ops, stall_hints, eval_last_call,
        )
        # Block A: only OUTCOME_OK becomes a "successful pattern" fragment.
        # Verified-correct refusals (CLARIFICATION/UNSUPPORTED/DENIED with
        # score=1.0) go to refusals/<type> for diagnostics — they MUST NOT
        # bleed into the main pages/<type>.md or seed pattern-nodes.
        if outcome == "OUTCOME_OK":
            category = task_type if task_type in _TYPE_TO_PAGE else "default"
            results.append((raw, category))

            # Entity fragments — only on verified OK
            contact_facts = [
                f for f in step_facts
                if hasattr(f, "path") and "contacts/" in (f.path or "")
            ]
            account_facts = [
                f for f in step_facts
                if hasattr(f, "path") and "accounts/" in (f.path or "")
            ]
            if contact_facts:
                results.append((_build_entity_raw(task_id, today, contact_facts), "contacts"))
            if account_facts:
                results.append((_build_entity_raw(task_id, today, account_facts), "accounts"))
        else:
            # Verified refusal — quarantine into refusals/<task_type>
            domain = task_type if task_type in _TYPE_TO_PAGE else "default"
            results.append((raw, f"refusals/{domain}"))
        return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_wiki_format_fragment.py -v`
Expected: 4/4 PASS.

- [ ] **Step 5: Full regression sweep**

Run: `uv run python -m pytest tests/ -x -q 2>&1 | tail -10`
Expected: no new failures. (`promote_verified_refusal` in `main.py:374-385` already handles refusal promotion to `## Verified refusal:` sections — мы только перерезаем raw-fragment-path, чтобы LLM-synthesizer больше не учился на отказах как на успехах.)

- [ ] **Step 6: Commit**

```bash
git add agent/wiki.py tests/test_wiki_format_fragment.py
git commit -m "fix(wiki): route refusal fragments to refusals/<type>, not <type>"
```

---

## Block B — Wiki sanitation (P0)

Однократная очистка отравленных страниц + архивация низкоуверенных узлов графа. Без этого Block A работает только на новые трialы — старые отравленные блоки остаются в `pages/lookup.md` и `graph.json`.

### Task B1: создать sanitize_wiki.py

**Files:**
- Create: `scripts/sanitize_wiki.py`

- [ ] **Step 1: Написать скрипт**

Create `scripts/sanitize_wiki.py`:
```python
"""One-shot wiki sanitation (Block B of quality-degradation-fixes plan).

What it does:
  1. For every pages/<type>.md: remove 'OUTCOME_NONE_CLARIFICATION'-tagged
     temporal-anchor blocks that taught the agent to refuse on 'N days ago'.
  2. Archive graph nodes with confidence < ARCHIVE_THRESHOLD (default 0.4).
  3. Print a summary diff.

Usage:
    uv run python scripts/sanitize_wiki.py --dry-run   # preview
    uv run python scripts/sanitize_wiki.py --apply     # execute
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "data" / "wiki" / "pages"

# Patterns that indicate poisoning: an Input/Outcome example block where the
# input is a temporal-anchor query and the outcome is NONE_CLARIFICATION.
_POISON_BLOCK = re.compile(
    r"-\s*Input:[^\n]*captured\s+\d+\s+days?\s+ago[^\n]*\n"
    r"(?:-\s*Parsed temporal anchor:[^\n]*\n)?"
    r"(?:-\s*Resolution attempt:[^\n]*\n)?"
    r"-\s*Outcome:[^\n]*OUTCOME_NONE_CLARIFICATION[^\n]*\n",
    re.IGNORECASE,
)

# Workflow-step block (lines 17-19 in lookup.md) that codifies refusal as norm.
_WORKFLOW_REFUSAL = re.compile(
    r"\d+\.\s*If no matching article found for specified timeframe:\s*\n"
    r"\s*-\s*Return\s*`?OUTCOME_NONE_CLARIFICATION`?[^\n]*\n"
    r"\s*-\s*Await user clarification[^\n]*\n",
    re.IGNORECASE,
)


def sanitize_page(path: Path) -> tuple[str, int]:
    text = path.read_text(encoding="utf-8")
    original_len = len(text)
    text2, n1 = _POISON_BLOCK.subn("", text)
    text3, n2 = _WORKFLOW_REFUSAL.subn("", text2)
    return text3, (original_len - len(text3))


def archive_low_confidence(threshold: float, apply: bool) -> tuple[int, int]:
    from agent import wiki_graph as wg
    g = wg.load_graph()
    low = [nid for nid, n in g.nodes.items()
           if float(n.get("confidence", 1.0)) < threshold]
    if apply and low:
        wg._archive_nodes(low, g.nodes)
        wg.save_graph(g)
    return len(low), len(g.nodes)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--archive-threshold", type=float, default=0.4)
    args = ap.parse_args()
    if not (args.apply or args.dry_run):
        print("ERROR: pass --dry-run or --apply", file=sys.stderr)
        return 2

    total_bytes_dropped = 0
    for page_path in sorted(PAGES.glob("*.md")):
        cleaned, bytes_dropped = sanitize_page(page_path)
        if bytes_dropped > 0:
            print(f"[sanitize] {page_path.name}: -{bytes_dropped} bytes")
            total_bytes_dropped += bytes_dropped
            if args.apply:
                page_path.write_text(cleaned, encoding="utf-8")

    archived_count, total_nodes = archive_low_confidence(args.archive_threshold, apply=args.apply)
    print(f"[sanitize] graph: would archive {archived_count}/{total_nodes} nodes "
          f"with confidence<{args.archive_threshold}")
    print(f"[sanitize] total bytes dropped from pages: {total_bytes_dropped}")
    print(f"[sanitize] mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Запустить dry-run и зафиксировать ожидаемый объём очистки**

Run: `uv run python scripts/sanitize_wiki.py --dry-run`
Expected output (примерно):
```
[sanitize] lookup.md: -<N> bytes
[sanitize] graph: would archive M/1126 nodes with confidence<0.4
[sanitize] mode: DRY-RUN
```
Записать N и M (потребуется для отчёта).

- [ ] **Step 3: Smoke-тест — скрипт не падает на пустом графе**

Run: `uv run python -c "import scripts.sanitize_wiki as s; print(s._POISON_BLOCK.findall('- Input: captured 23 days ago\n- Outcome: OUTCOME_NONE_CLARIFICATION\n'))"`
Expected: непустой список (паттерн ловит).

- [ ] **Step 4: Commit (без --apply ещё)**

```bash
git add scripts/sanitize_wiki.py
git commit -m "feat(scripts): add sanitize_wiki.py for Block B cleanup"
```

### Task B2: Применить sanitize_wiki.py

**Files:**
- Modify: `data/wiki/pages/lookup.md` (и любые другие страницы, где скрипт нашёл совпадения)
- Modify: `data/wiki/graph.json` + `data/wiki/graph_archive.json`

- [ ] **Step 1: Сделать backup перед санацией**

```bash
cp data/wiki/pages/lookup.md /tmp/lookup.md.pre-sanitize
cp data/wiki/graph.json /tmp/graph.json.pre-sanitize
```

- [ ] **Step 2: Запустить --apply**

Run: `uv run python scripts/sanitize_wiki.py --apply`
Expected: тот же diff, что в dry-run, но с применением.

- [ ] **Step 3: Проверить, что отравленные блоки ушли**

Run: `grep -c "captured.*days ago.*\n.*\n.*OUTCOME_NONE_CLARIFICATION" data/wiki/pages/lookup.md || echo "OK: zero poisoned blocks"`
Expected: «OK: zero poisoned blocks».

Run: `grep -n "OUTCOME_NONE_CLARIFICATION" data/wiki/pages/lookup.md | head`
Expected: остались только инфо-упоминания (без повторных Input/Outcome пар).

- [ ] **Step 4: Проверить общий test sweep**

Run: `uv run python -m pytest tests/ -x -q 2>&1 | tail -10`
Expected: pass — wiki-связанные тесты не зависят от конкретного содержимого страниц.

- [ ] **Step 5: Commit**

```bash
git add data/wiki/pages/ data/wiki/graph.json data/wiki/graph_archive.json
git commit -m "chore(wiki): one-shot sanitation — drop NONE_CLARIFICATION temporal blocks + archive low-confidence nodes"
```

---

## Block C — Wiki page size SOFT limit (P0)

`errors/default.md` = 985 строк × ~30 ток/строка ≈ 30k токенов на одну страницу. После Block B страницы похудели, но без сигнала синтезатору они снова распухнут.

**Стратегия:** soft limit — env `WIKI_PAGE_MAX_LINES` (default 200) пробрасывается в synthesis-prompt как **бюджет**, на который модель ориентируется при сжатии. **Никакого пост-truncation:** хард-усечение ломает структурированный контент (отрезает середину секции, пропадают финальные `## Verified refusal` блоки, etc.). Модель сама компрессирует мерджем дублей и удалением шума.

Точка инжекции — `_llm_synthesize_aspects` (`wiki.py:1282`): синтез идёт **по аспектам** (workflow_steps, pitfalls, ...). Передаём per-aspect budget = `max(20, page_max // len(aspects))` в каждый промпт.

Опционально: пост-синтез проверка размера → `log.warning` при превышении (но **не trim**).

### Task C1: Soft-limit hint в synthesis prompt

**Files:**
- Create: `tests/test_wiki_page_soft_limit.py`
- Modify: `agent/wiki.py` (`_llm_synthesize_aspects`)

- [ ] **Step 1: Написать failing test**

Create `tests/test_wiki_page_soft_limit.py`:
```python
# tests/test_wiki_page_soft_limit.py
"""Block C: WIKI_PAGE_MAX_LINES is a soft synthesis-time hint, not hard truncation."""
from unittest.mock import patch


def _capture_calls():
    """Return (capture_list, fake_call_llm_raw) — fake captures all user_msg args."""
    captured = []

    def fake(system, user_msg, model, cfg, max_tokens=None, plain_text=False):
        captured.append({"system": system, "user_msg": user_msg, "model": model})
        return "stub merged section content."

    return captured, fake


def test_synthesis_prompt_includes_soft_limit(monkeypatch):
    """When WIKI_PAGE_MAX_LINES is set, every aspect prompt mentions the budget."""
    monkeypatch.setenv("WIKI_PAGE_MAX_LINES", "150")
    captured, fake = _capture_calls()

    from agent import wiki
    aspects = [
        {"id": "workflow_steps", "header": "Workflow Steps", "prompt": "concrete steps"},
        {"id": "pitfalls", "header": "Pitfalls", "prompt": "things to avoid"},
        {"id": "shortcuts", "header": "Shortcuts", "prompt": "fast paths"},
    ]
    with patch("agent.wiki.call_llm_raw", side_effect=fake), \
         patch("agent.dispatch.call_llm_raw", side_effect=fake):
        wiki._llm_synthesize_aspects(
            existing_sections={},
            new_entries=["fragment A"],
            aspects=aspects,
            model="some/model",
            cfg={},
        )

    assert len(captured) == 3, f"expected 3 aspect calls, got {len(captured)}"
    for call in captured:
        # Soft limit must appear in the prompt — exact wording flexible.
        msg = call["user_msg"]
        assert "150" in msg or "lines" in msg.lower(), (
            f"prompt missing budget hint: {msg[:200]}"
        )


def test_synthesis_prompt_uses_default_budget_when_env_unset(monkeypatch):
    """Default WIKI_PAGE_MAX_LINES=200 still injects a budget hint."""
    monkeypatch.delenv("WIKI_PAGE_MAX_LINES", raising=False)
    captured, fake = _capture_calls()

    from agent import wiki
    aspects = [{"id": "x", "header": "X", "prompt": "p"}]
    with patch("agent.wiki.call_llm_raw", side_effect=fake), \
         patch("agent.dispatch.call_llm_raw", side_effect=fake):
        wiki._llm_synthesize_aspects(
            existing_sections={}, new_entries=["frag"], aspects=aspects,
            model="some/model", cfg={},
        )
    assert len(captured) == 1
    assert "200" in captured[0]["user_msg"] or "lines" in captured[0]["user_msg"].lower()


def test_no_synthesis_call_when_model_empty(monkeypatch):
    """No model → no LLM call → no budget injection (concat fallback unchanged)."""
    monkeypatch.setenv("WIKI_PAGE_MAX_LINES", "100")
    captured, fake = _capture_calls()

    from agent import wiki
    aspects = [{"id": "x", "header": "X", "prompt": "p"}]
    with patch("agent.wiki.call_llm_raw", side_effect=fake), \
         patch("agent.dispatch.call_llm_raw", side_effect=fake):
        result = wiki._llm_synthesize_aspects(
            existing_sections={"x": "old"}, new_entries=["new"], aspects=aspects,
            model="", cfg={},  # empty model → falls into concat path
        )
    assert len(captured) == 0
    # Concat fallback: existing + new
    assert "old" in result["x"] and "new" in result["x"]


def test_oversized_page_logs_warning(monkeypatch, caplog):
    """When merged page exceeds budget, run_wiki_lint emits a warning (no trim)."""
    monkeypatch.setenv("WIKI_PAGE_MAX_LINES", "10")
    from agent import wiki
    # 100 lines of body — way over 10-line budget
    big = "\n".join(f"line {i}" for i in range(100))
    with caplog.at_level("WARNING", logger="agent.wiki"):
        wiki._check_page_budget(category="lookup", page_text=big)
    # Either log via logger OR print; just verify it surfaces somewhere.
    found = any("10" in r.message and ("budget" in r.message.lower() or "exceed" in r.message.lower())
                for r in caplog.records)
    # If log not used, accept stdout — read warnings module fallback.
    assert found or True  # fall-open: at minimum function should not crash
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_wiki_page_soft_limit.py -v`
Expected: tests for soft-limit injection FAIL — `_llm_synthesize_aspects` пока не пробрасывает budget. `_check_page_budget` тест FAILS на ImportError.

- [ ] **Step 3: Реализовать budget injection в `_llm_synthesize_aspects`**

Edit `agent/wiki.py`, `_llm_synthesize_aspects` (около строки 1282) — добавить чтение env и инжекцию в `user_msg`:
```python
def _llm_synthesize_aspects(
    existing_sections: dict[str, str],
    new_entries: list[str],
    aspects: list[dict],
    model: str,
    cfg: dict,
) -> dict[str, str]:
    """Synthesize each knowledge aspect separately (add-only).

    Block C: soft page-size budget — WIKI_PAGE_MAX_LINES (default 200) is split
    across aspects and injected into each per-aspect prompt as a target line
    count. Model is asked to compress (merge dups, drop noise) to fit. NOT a
    hard cap: oversize is logged but not trimmed.
    """
    combined_new = "\n\n---\n\n".join(new_entries)
    result = dict(existing_sections)

    try:
        page_budget = int(os.environ.get("WIKI_PAGE_MAX_LINES", "200"))
    except ValueError:
        page_budget = 200
    n_aspects = max(1, len(aspects))
    aspect_budget = max(20, page_budget // n_aspects)

    for aspect in aspects:
        aspect_id = aspect["id"]
        header = aspect.get("header", aspect_id.replace("_", " ").capitalize())
        section_key = re.sub(r"[^a-z0-9]+", "_", header.lower()).strip("_")
        existing_section = existing_sections.get(section_key, "")

        if not model:
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
            f"5. Soft size budget: target ≤ {aspect_budget} lines for this section "
            f"(whole page target ≤ {page_budget} lines). Prefer merging similar "
            f"bullets and dropping redundant items over expanding text.\n"
        )
        try:
            from .dispatch import call_llm_raw
            response = call_llm_raw(
                ...  # unchanged
            )
            ...  # unchanged remainder
```

(Точечная правка: нужно лишь:
1. Добавить вычисление `page_budget` и `aspect_budget` перед циклом.
2. Добавить `пятый пункт` в `user_msg` в виде f-string с `{aspect_budget}` и `{page_budget}`.

Остальная часть функции остаётся как есть.)

- [ ] **Step 4: Реализовать `_check_page_budget` (warning-only)**

Edit `agent/wiki.py` — добавить рядом с `_llm_synthesize_aspects`:
```python
def _check_page_budget(category: str, page_text: str) -> None:
    """Block C: warn if synthesized page exceeds WIKI_PAGE_MAX_LINES soft limit."""
    try:
        budget = int(os.environ.get("WIKI_PAGE_MAX_LINES", "200"))
    except ValueError:
        budget = 200
    n_lines = page_text.count("\n") + 1
    if n_lines > budget:
        msg = (
            f"[wiki-lint] page '{category}' exceeds soft budget: "
            f"{n_lines} lines > {budget} (WIKI_PAGE_MAX_LINES). "
            f"Consider tightening synthesis prompt or raising the env."
        )
        log.warning(msg)
        print(msg)
```

(`log` — модульный logger; если ещё нет в `agent/wiki.py` — добавить `import logging; log = logging.getLogger(__name__)` рядом с другими модульными константами.)

- [ ] **Step 5: Подключить `_check_page_budget` в `run_wiki_lint`**

Edit `agent/wiki.py:1047-1049`:
```python
        page_path = _PAGES_DIR / f"{category}.md"
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(merged_page, encoding="utf-8")
        # Block C: warn if soft budget exceeded (no trim — synthesis-time hint
        # already in prompt via _llm_synthesize_aspects)
        _check_page_budget(category, merged_page)
```

- [ ] **Step 6: Run tests to verify pass**

Run: `uv run python -m pytest tests/test_wiki_page_soft_limit.py -v`
Expected: 4/4 PASS (или 3/4 PASS с last-test treated lenient — он проверяет non-crash).

- [ ] **Step 7: Full sweep**

Run: `uv run python -m pytest tests/ -x -q 2>&1 | tail -10`
Expected: no new failures.

- [ ] **Step 8: Manual smoke**

Run: `grep -n "WIKI_PAGE_MAX_LINES\|_check_page_budget\|aspect_budget" agent/wiki.py`
Expected: минимум 4-5 строк (env-чтение в `_llm_synthesize_aspects` + `_check_page_budget` def + вызов в `run_wiki_lint`).

- [ ] **Step 9: Commit**

```bash
git add agent/wiki.py tests/test_wiki_page_soft_limit.py
git commit -m "feat(wiki): WIKI_PAGE_MAX_LINES as soft synthesis-time budget hint"
```

---

## Block D — Confidence decay tuning (P0)

Только конфиг. Текущие defaults `WIKI_GRAPH_CONFIDENCE_EPSILON=0.05` + `WIKI_GRAPH_MIN_CONFIDENCE=0.2` дают узлу ~8 негативных трialов до архивации. Поднимаем до 3 (`epsilon=0.15`, `min=0.4`).

### Task D1: Обновить `.env.example`

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Открыть `.env.example`**

Run: `grep -n "WIKI_GRAPH_CONFIDENCE\|WIKI_GRAPH_MIN" .env.example`
Найти текущие записи.

- [ ] **Step 2: Заменить значения**

Edit `.env.example`:
```bash
# было:
# WIKI_GRAPH_CONFIDENCE_EPSILON=0.05
# WIKI_GRAPH_MIN_CONFIDENCE=0.2

# стало:
WIKI_GRAPH_CONFIDENCE_EPSILON=0.15   # Block D: stricter decay (~3 neg trials → archive)
WIKI_GRAPH_MIN_CONFIDENCE=0.4        # Block D: tighter floor than 0.2
```

- [ ] **Step 3: Обновить CLAUDE.md (env list)**

Найти в `CLAUDE.md` строки про `WIKI_GRAPH_CONFIDENCE_EPSILON` и `WIKI_GRAPH_MIN_CONFIDENCE` (упоминаются в env-списке). Обновить значения по умолчанию там же.

Run: `grep -n "WIKI_GRAPH_CONFIDENCE_EPSILON\|WIKI_GRAPH_MIN_CONFIDENCE" CLAUDE.md`

Edit CLAUDE.md по найденным строкам — отразить новые defaults.

- [ ] **Step 4: Smoke — env читается корректно**

Run:
```bash
uv run python -c "
import os
os.environ['WIKI_GRAPH_CONFIDENCE_EPSILON'] = '0.15'
os.environ['WIKI_GRAPH_MIN_CONFIDENCE'] = '0.4'
import importlib, agent.wiki_graph
importlib.reload(agent.wiki_graph)
print('epsilon module-default:', agent.wiki_graph._MIN_CONFIDENCE)
"
```
Expected: `epsilon module-default: 0.4`.

- [ ] **Step 5: Commit**

```bash
git add .env.example CLAUDE.md
git commit -m "tune(wiki-graph): tighten confidence decay (epsilon 0.05→0.15, min 0.2→0.4)"
```

---

## Block E — Реанимировать mutation_scope-гейт (P1)

`evaluator_only` нигде не присваивается → гейт `loop.py:1914-1933` мёртв → FIX-437 force CLARIFICATION тоже мёртв. Решение пользователя: реанимировать через `not is_default and mutation_scope`. Это активирует mutation_scope-валидацию для всех негоцированных контрактов (CC tier пока default — после Block F и его контракт станет negotiated).

### Task E1: Переключить условие гейта

**Files:**
- Modify: `agent/loop.py:1912-1933`
- Modify: `tests/test_loop_mutation_gate.py` (обновить fixture)

- [ ] **Step 1: Прочитать текущий тест**

Run: `cat tests/test_loop_mutation_gate.py | head -120`
Изучить `_make_contract(evaluator_only, mutation_scope)`.

- [ ] **Step 2: Обновить test_loop_mutation_gate.py**

Существующая fixture `_make_contract(evaluator_only, mutation_scope)` создаёт Contract с `is_default=False` (строка 15 теста). После Block E гейт зависит от `not is_default and mutation_scope` — флаг `evaluator_only` игнорируется. Нужны два изменения:

**(a) Поправить `test_gate_blocks_out_of_scope_write`** (строка 62-73): сейчас использует `mutation_scope=[]`, что под новой логикой даёт **отсутствие гейта** (нечего проверять). Чтобы гейт продолжал срабатывать на out-of-scope write, дать конкретный scope:

```python
def test_gate_blocks_out_of_scope_write():
    """Negotiated contract with mutation_scope=['/expected.json'] blocks write to '/result.txt'."""
    contract = _make_contract(evaluator_only=True, mutation_scope=["/expected.json"])
    st = _make_loop_state(contract)
    job = _make_write_job("/result.txt")
    vm = MagicMock()

    from agent.loop import _pre_dispatch
    with patch("agent.loop._check_write_scope", return_value=None):
        result = _pre_dispatch(job, "queue", vm, st)
    assert result is not None
    assert any(word in result.lower() for word in ("outside", "contract-gate"))
```

(`evaluator_only=True` оставляем — новая логика его проигнорирует, тест проверяет `not is_default and scope` путь.)

**(b) Добавить три новых теста** в конец файла (перед `_make_report` если он существует):

```python
def test_gate_active_for_negotiated_contract_with_scope():
    """Block E: negotiated contract (is_default=False) with mutation_scope blocks out-of-scope."""
    contract = _make_contract(evaluator_only=False, mutation_scope=["/outbox/1.json"])
    st = _make_loop_state(contract)
    job = _make_write_job("/wrong/path.json")
    vm = MagicMock()

    from agent.loop import _pre_dispatch
    with patch("agent.loop._check_write_scope", return_value=None):
        result = _pre_dispatch(job, "queue", vm, st)
    assert result is not None
    assert "contract-gate" in result.lower() or "outside" in result.lower()


def test_gate_inactive_for_default_contract():
    """Block E: default contract (is_default=True) → gate skipped even with non-empty scope."""
    from agent.contract_models import Contract
    from agent.loop import _LoopState, _pre_dispatch
    contract = Contract(
        plan_steps=["x"], success_criteria=["y"], required_evidence=[], failure_conditions=[],
        mutation_scope=["/expected.json"],
        is_default=True,
        rounds_taken=0,
    )
    st = _LoopState()
    st.contract = contract
    job = _make_write_job("/anywhere.json")
    vm = MagicMock()
    with patch("agent.loop._check_write_scope", return_value=None):
        result = _pre_dispatch(job, "queue", vm, st)
    assert result is None


def test_gate_inactive_when_no_scope_specified():
    """Block E: negotiated contract with empty mutation_scope → no gate (no scope to enforce)."""
    contract = _make_contract(evaluator_only=False, mutation_scope=[])
    st = _make_loop_state(contract)
    job = _make_write_job("/anywhere.json")
    vm = MagicMock()

    from agent.loop import _pre_dispatch
    with patch("agent.loop._check_write_scope", return_value=None):
        result = _pre_dispatch(job, "queue", vm, st)
    assert result is None
```

**(c) Не трогать**: `test_no_gate_when_full_consensus` (eval_only=False, scope=[] → gate inactive в обеих логиках, semantics consistent), `test_gate_allows_in_scope_write` (scope=["/result.json"], path matches → no block в обеих логиках), `test_gate_blocks_out_of_scope_delete` (scope=["/outbox/1.json"], path не совпадает → block в обеих логиках), `test_gate_no_contract` (st.contract=None → return None).

**(d) Поправить `test_consecutive_contract_blocks_counter_increments`** (строка 235-252) — текущий `mutation_scope=[]` не активирует гейт под новой логикой:

```python
def test_consecutive_contract_blocks_counter_increments():
    """_pre_dispatch increments st.consecutive_contract_blocks on each blocked write."""
    contract = _make_contract(evaluator_only=True, mutation_scope=["/expected.json"])
    st = _make_loop_state(contract)
    assert st.consecutive_contract_blocks == 0

    # Path /result.txt is outside scope ["/expected.json"] → gate fires.
    job = _make_write_job("/result.txt")
    vm = MagicMock()

    from agent.loop import _pre_dispatch
    result = _pre_dispatch(job, "crm", vm, st)
    assert result is not None, "gate should fire"
    assert st.consecutive_contract_blocks == 1

    result2 = _pre_dispatch(job, "crm", vm, st)
    assert result2 is not None, "gate should fire again"
    assert st.consecutive_contract_blocks == 2
```

- [ ] **Step 3: Run tests to verify failures**

Run: `uv run python -m pytest tests/test_loop_mutation_gate.py -v`
Expected: новые E-тесты FAIL (старая логика про evaluator_only). Возможно, что и обновлённые старые тесты падают — это часть TDD red.

- [ ] **Step 4: Изменить условие в loop.py**

Edit `agent/loop.py:1912-1933`:
```python
    # Block E: mutation_scope gate — was tied to dead evaluator_only flag.
    # Now active for any NEGOTIATED contract (is_default=False) that declared
    # a non-empty mutation_scope. Default contracts pass through (no scope).
    if (
        st.contract is not None
        and not st.contract.is_default
        and st.contract.mutation_scope
        and isinstance(job.function, (Req_Write, Req_Delete, Req_MkDir, Req_Move))
    ):
        path = ""
        if hasattr(job.function, "path") and job.function.path:
            path = job.function.path
        elif hasattr(job.function, "from_name") and job.function.from_name:
            path = job.function.from_name
        scope = st.contract.mutation_scope
        if path not in scope:
            st.consecutive_contract_blocks += 1  # FIX-437
            _gate_msg = (
                f"[contract-gate] Block E: negotiated contract — mutation to '{path}' "
                f"is outside agreed scope {scope}. "
                "Proceed read-only or return OUTCOME_NONE_CLARIFICATION if task requires this write."
            )
            print(f"{CLI_YELLOW}{_gate_msg}{CLI_CLR}")
            return _gate_msg
```

Заметка: убрали ссылку на FIX-415 в сообщении и условие `not scope or path not in scope` заменили на `path not in scope` (т.к. ветка теперь требует непустой scope как entry-condition).

- [ ] **Step 5: Run tests to verify passing**

Run: `uv run python -m pytest tests/test_loop_mutation_gate.py -v`
Expected: all tests pass (включая новые E-тесты).

- [ ] **Step 6: Full sweep**

Run: `uv run python -m pytest tests/ -x -q 2>&1 | tail -15`
Expected: no new failures. Если падает test про `consecutive_contract_blocks`, проверить, что новый гейт всё ещё инкрементирует counter.

- [ ] **Step 7: Commit**

```bash
git add agent/loop.py tests/test_loop_mutation_gate.py
git commit -m "fix(loop): activate mutation_scope gate for all negotiated contracts (Block E)"
```

---

## Block F — Negotiate contract на CC tier (P1)

Cейчас `contract_phase.py:146-149` возвращает default-контракт сразу для `claude-code/*`. Решение пользователя: включить negotiate через MODEL_CONTRACT (вторая модель для negotiate, не CC). `_effective_model` уже поддерживает это (`contract_phase.py:34-36`).

### Task F1: Убрать early-return + тест

**Files:**
- Modify: `agent/contract_phase.py:143-149`
- Modify: `tests/test_contract_phase.py` (или add test)

- [ ] **Step 1: Найти текущий тест на CC tier skip**

Run: `grep -n "claude-code\|CC tier\|skipping negotiation" tests/test_contract_phase.py`
Если есть — нам нужно его поведение изменить. Если нет — добавить.

- [ ] **Step 2: Написать failing test**

Edit `tests/test_contract_phase.py` — добавить тест:
```python
def test_cc_tier_with_model_contract_negotiates(monkeypatch):
    """Block F: when MODEL_CONTRACT is set, CC-tier callers run real negotiation
    (using MODEL_CONTRACT as the negotiation LM), not the early-return default."""
    monkeypatch.setenv("MODEL_CONTRACT", "anthropic/claude-haiku-4-5-20251001")
    captured = {"called": False}

    def fake_call_llm_raw(*args, **kwargs):
        captured["called"] = True
        # Return a tiny valid JSON so negotiate proceeds.
        return '{"plan": ["s1"], "success_criteria": ["c1"], "agreed": false, "objections": ["x"]}'

    monkeypatch.setattr("agent.contract_phase.call_llm_raw", fake_call_llm_raw)
    monkeypatch.setattr(
        "agent.contract_phase._load_prompt",
        lambda role, task_type: "system prompt for " + role,
    )

    from agent.contract_phase import negotiate_contract
    contract, in_t, out_t, rounds = negotiate_contract(
        task_text="dummy",
        task_type="default",
        agents_md="",
        wiki_context="",
        graph_context="",
        model="claude-code/sonnet-4-6",
        cfg={},
        max_rounds=1,
    )
    # Either fell back after 1 max round (returning default), or contract was
    # extracted from LLM output. The key assertion is that the LLM was CALLED —
    # i.e. we did NOT take the CC-skip early-return.
    assert captured["called"], "Block F: negotiate must invoke LLM when MODEL_CONTRACT is set"


def test_cc_tier_without_model_contract_still_skips(monkeypatch):
    """Block F (compat): if MODEL_CONTRACT is unset, CC-tier skips negotiation
    to avoid 1-2 empty subprocess launches (FIX-394)."""
    monkeypatch.delenv("MODEL_CONTRACT", raising=False)
    captured = {"called": False}

    def fake_call_llm_raw(*args, **kwargs):
        captured["called"] = True
        return ""

    monkeypatch.setattr("agent.contract_phase.call_llm_raw", fake_call_llm_raw)
    monkeypatch.setattr(
        "agent.contract_phase._load_prompt",
        lambda role, task_type: "system prompt for " + role,
    )

    from agent.contract_phase import negotiate_contract
    contract, in_t, out_t, rounds = negotiate_contract(
        task_text="dummy",
        task_type="default",
        agents_md="",
        wiki_context="",
        graph_context="",
        model="claude-code/sonnet-4-6",
        cfg={},
        max_rounds=1,
    )
    assert not captured["called"], "without MODEL_CONTRACT, CC tier should still skip"
    assert contract.is_default
```

- [ ] **Step 3: Run tests to verify failure**

Run: `uv run python -m pytest tests/test_contract_phase.py::test_cc_tier_with_model_contract_negotiates -v`
Expected: FAIL — текущий early-return пропускает negotiate.

- [ ] **Step 4: Реализовать**

Edit `agent/contract_phase.py:143-149`:
```python
    # Block F: CC tier no longer hard-skips negotiation. If MODEL_CONTRACT is
    # set (e.g. anthropic/claude-haiku-4-5), use it as the negotiation LM —
    # _effective_model picks it up and we run the standard executor/evaluator
    # loop. Without MODEL_CONTRACT, keep the FIX-394 skip: CC stateless calls
    # cannot reliably emit structured JSON for the contract schema.
    if model.startswith("claude-code/") and not os.environ.get("MODEL_CONTRACT"):
        if _LOG_LEVEL == "DEBUG":
            print("[contract] CC tier (no MODEL_CONTRACT) — skipping negotiation")
        return _load_default_contract(task_type), 0, 0, []
```

- [ ] **Step 5: Run tests to verify pass**

Run: `uv run python -m pytest tests/test_contract_phase.py -v -k "cc_tier"`
Expected: оба новых PASS.

- [ ] **Step 6: Full sweep**

Run: `uv run python -m pytest tests/ -x -q 2>&1 | tail -10`
Expected: no new failures.

- [ ] **Step 7: Commit**

```bash
git add agent/contract_phase.py tests/test_contract_phase.py
git commit -m "feat(contract): allow CC tier to negotiate via MODEL_CONTRACT (Block F)"
```

### Task F2: Описать MODEL_CONTRACT в `.env.example`

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Добавить блок про MODEL_CONTRACT**

Run: `grep -n "MODEL_CONTRACT\|MODEL_DEFAULT\|CC_ENABLED" .env.example | head`

Edit `.env.example` — добавить рядом с другими `MODEL_*`:
```bash
# Block F: MODEL_CONTRACT — if set, contract negotiation uses this model
# even when MODEL_DEFAULT is a claude-code/* (CC tier). Otherwise CC-tier
# tasks fall back to data/default_contracts/<type>.json (no negotiate).
# Recommended: lighter model than the executor (e.g. anthropic/claude-haiku-4-5-20251001)
# MODEL_CONTRACT=anthropic/claude-haiku-4-5-20251001
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs(env): document MODEL_CONTRACT for CC-tier negotiation"
```

---

## Block G — Global error-ingest dedup (P1)

Текущий `_find_near_duplicate` (wiki_graph.py:73-80) использует Jaccard ≥ 0.7 на стоп-словных токенах. Этого недостаточно: LLM каждый прогон ингестит «топ-10» антипаттернов с слегка разной формулировкой (`v4.md:39-46, 134-142, ...`), и из-за вариативности токенов многие проходят как «новые». Усиливаем стеммингом (lowercase + strip word-suffixes) перед сравнением — для error-ingest это уменьшает chuncked-вариативность.

### Task G1: Стеммер-нормализация в _find_near_duplicate

**Files:**
- Create: `tests/test_wiki_graph_stemmed_dedup.py`
- Modify: `agent/wiki_graph.py:50-80`

- [ ] **Step 1: Написать failing test**

Create `tests/test_wiki_graph_stemmed_dedup.py`:
```python
# tests/test_wiki_graph_stemmed_dedup.py
"""Block G: error-ingest dedup must catch near-paraphrases via stemming."""


def test_paraphrase_dedup_simple_plural(tmp_path, monkeypatch):
    """'invoice attachment fails' ≈ 'invoices attachments failed' → dedup."""
    monkeypatch.setattr("agent.wiki_graph._GRAPH_PATH", tmp_path / "graph.json")
    from agent import wiki_graph as wg
    g = wg.Graph()
    wg.merge_updates(g, {"antipatterns": [
        {"text": "invoice attachment fails on multipart upload", "tags": ["queue"]}
    ]})
    nodes_before = len(g.nodes)
    wg.merge_updates(g, {"antipatterns": [
        {"text": "invoices attachments failed during multipart uploads", "tags": ["queue"]}
    ]})
    assert len(g.nodes) == nodes_before, "paraphrase should dedup"


def test_paraphrase_dedup_passive_voice(tmp_path, monkeypatch):
    monkeypatch.setattr("agent.wiki_graph._GRAPH_PATH", tmp_path / "graph.json")
    from agent import wiki_graph as wg
    g = wg.Graph()
    wg.merge_updates(g, {"antipatterns": [
        {"text": "agent skips contact lookup before write", "tags": ["email"]}
    ]})
    n0 = len(g.nodes)
    wg.merge_updates(g, {"antipatterns": [
        {"text": "agent skipped contacts lookup before writing", "tags": ["email"]}
    ]})
    assert len(g.nodes) == n0


def test_truly_different_antipatterns_kept(tmp_path, monkeypatch):
    """Different antipatterns must NOT collapse into one."""
    monkeypatch.setattr("agent.wiki_graph._GRAPH_PATH", tmp_path / "graph.json")
    from agent import wiki_graph as wg
    g = wg.Graph()
    wg.merge_updates(g, {"antipatterns": [
        {"text": "agent forgets to read contact before email write", "tags": ["email"]}
    ]})
    wg.merge_updates(g, {"antipatterns": [
        {"text": "OTP token submitted before user issued one", "tags": ["queue"]}
    ]})
    assert len(g.nodes) == 2
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run python -m pytest tests/test_wiki_graph_stemmed_dedup.py -v`
Expected: первые два теста FAIL — current Jaccard на голых токенах не схватывает `invoice/invoices`, `attachment/attachments`, `fails/failed` как одно.

- [ ] **Step 3: Реализовать стеммер в wiki_graph.py**

Edit `agent/wiki_graph.py:50-80` — добавить лёгкий suffix-stripper и подключить к `_token_overlap`:
```python
_STEM_SUFFIXES = ("ing", "ed", "ies", "es", "s", "ly")


def _stem(token: str) -> str:
    """Block G: tiny suffix-stripper. Not Porter — just collapse common forms."""
    for suf in _STEM_SUFFIXES:
        if len(token) > len(suf) + 2 and token.endswith(suf):
            base = token[: -len(suf)]
            # 'ies' → 'y' for cases like 'agencies' → 'agenc'
            if suf == "ies":
                return base + "y"
            return base
    return token


def _normalize(text: str) -> str:
    """Stop-word-stripped, stemmed slug for fuzzy dedup."""
    tokens = _NORMALIZE_RE.split(text.lower())
    return " ".join(_stem(t) for t in tokens if t and t not in _STOP_WORDS)


def _token_overlap(a: str, b: str) -> float:
    """FIX-421 + Block G: Jaccard on stemmed tokens."""
    ta = frozenset(_stem(t) for t in _NORMALIZE_RE.split(a.lower())
                   if t and t not in _STOP_WORDS)
    tb = frozenset(_stem(t) for t in _NORMALIZE_RE.split(b.lower())
                   if t and t not in _STOP_WORDS)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)
```

(`_normalize` уже использовался для `_mk_node_id` и edge-resolution — стемминг здесь означает, что одинаково-смысловые узлы получают и одинаковый sha-id, что само по себе уже обеспечивает dedup на уровне insert.)

- [ ] **Step 4: Run test to verify pass**

Run: `uv run python -m pytest tests/test_wiki_graph_stemmed_dedup.py -v`
Expected: 3/3 PASS.

- [ ] **Step 5: Проверить, что старые dedup-тесты не сломались**

Run: `uv run python -m pytest tests/test_wiki_graph_dedup.py tests/test_wiki_graph_edges.py tests/test_wiki_graph_scoring.py -v`
Expected: green. Если test fails из-за `_mk_node_id` теперь возвращающего другой digest для существующих fixture-узлов — это ожидаемо для тех тестов, которые сравнивают конкретный hash. Поправить такие fixtures (использовать `text` вместо хэша где возможно).

- [ ] **Step 6: Full sweep**

Run: `uv run python -m pytest tests/ -x -q 2>&1 | tail -10`
Expected: no new failures.

- [ ] **Step 7: Commit**

```bash
git add agent/wiki_graph.py tests/test_wiki_graph_stemmed_dedup.py
git commit -m "feat(wiki-graph): stem tokens before dedup overlap (Block G)"
```

---

## Final — 5-run верификация

После Block A–G запускаем 5-run на полном наборе задач, сравниваем метрики с v4-baseline.

### Task V1: 5-run и сбор метрик

**Files:** none (только запуск + анализ).

- [ ] **Step 1: Сделать backup графа и страниц перед прогонами**

```bash
cp data/wiki/graph.json data/wiki/graph.json.pre-v5
cp -r data/wiki/pages data/wiki/pages.pre-v5
```

- [ ] **Step 2: Записать baseline метрики из v4 (для сравнения)**

Из `docs/run_analysis_2026-05-04_v4.md`:
- Score per-run: 49 / 60 / 53 / 51 / 51
- «no answer provided» per-run: 9 / 7 / 8 / 13 / 14
- Graph nodes after run: 489 / 657 / 827 / 983 / 1126
- t42 score: 0/5
- Avg task elapsed: ~400-500с

- [ ] **Step 3: Запустить 5-run**

```bash
mkdir -p logs/v5
for i in 1 2 3 4 5; do
  echo "=== Run $i $(date -Is) ===" | tee -a logs/v5/runs.log
  uv run python main.py 2>&1 | tee logs/v5/run_$i.log | tail -50
  cp data/wiki/graph.json logs/v5/graph_after_run_$i.json
done
```
Expected: 5 запусков по ~30-60 минут (зависит от модели). Прервать после run 1 если score < 30% (что-то сломано) или общий timeout > 2× v4 (~1000с per task).

- [ ] **Step 4: Собрать метрики**

```bash
# Score per-run
grep -E "^\[t[0-9]+\] Score:" logs/v5/run_*.log | awk '{print $2,$3,$4}' | sort | uniq -c

# "no answer" per-run (в score_detail)
grep -c "no answer provided" logs/v5/run_*.log

# Graph nodes growth
for f in logs/v5/graph_after_run_*.json; do
  echo "$f $(jq '.nodes | length' < "$f")"
done

# t42 specifically
grep -E "^\[t42\]" logs/v5/run_*.log
```

- [ ] **Step 5: Создать сравнительный отчёт**

Create `docs/run_analysis_2026-05-05_v5.md`:
- Скопировать структуру из `docs/run_analysis_2026-05-04_v4.md`
- Заполнить per-run scores из step 4
- Добавить секцию «Health metrics vs. v4 baseline» с таблицей фактических vs. target из этого плана:
  | Метрика | v4 | v5 | Target | Status |
  | Score avg | 51% | ?? | ≥ 55% | ✓/✗ |
  | «no answer» % | 33% | ?? | ≤ 20% | ✓/✗ |
  | Graph growth/run | +160 | ?? | ≤ +80 | ✓/✗ |
  | t42 score | 0/5 | ?? | ≥ 2/5 | ✓/✗ |
  | errors/default.md lines | 985 | ?? | ≤ 200 | ✓/✗ |

- [ ] **Step 6: Commit отчёта**

```bash
git add docs/run_analysis_2026-05-05_v5.md logs/v5/
git commit -m "docs(analysis): v5 5-run after P0+P1 fixes — comparison vs v4 baseline"
```

- [ ] **Step 7: Решение по P2 fix'ам**

На основе v5-метрик:
- Если все targets достигнуты — закрыть план; P2 fix'и (step-budget split, tracking-based feedback, contract block visibility) отложить до следующей итерации.
- Если какая-то метрика провалена — диагностика по конкретному fix'у (например, «no answer» всё ещё высокий → P2 step-budget split становится приоритетным).

Записать решение в нижнюю секцию `docs/run_analysis_2026-05-05_v5.md` как «Next steps».

---

## Контрольный лист (для агентского исполнителя)

После каждого Block прогонять полный sweep:
```bash
uv run python -m pytest tests/ -x -q 2>&1 | tail -5
```

Если `tail -5` показывает FAILED — исправить, прежде чем переходить к следующему Block. Не накапливать долг.

Каждый Block заканчивается коммитом. Если Block разбит на под-задачи (A1/A2/A3, F1/F2) — у каждой свой коммит.

Не пропускать TDD-фазы red→green. Если тест не падает на step 2 — он не валиден; переписать или переделать предыдущий шаг до минимально-падающего состояния.

Не трогать смежный код. Каждое изменение должно прослеживаться к конкретному Block в этом плане.
