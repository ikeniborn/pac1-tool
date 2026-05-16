# Wiki Log

<!-- Append-only лог. Новые записи добавляются в конец. -->

## 2026-05-14T00:00:00

**Операция:** ingest
**Источник:** data/prompts/answer.md
**Домен:** документация

**Затронуто страниц:** 2

- СОЗДАНА: `.wiki/документация/pipeline-phases/answer-phase.md` (stub)
- СОЗДАНА: `.wiki/документация/design-decisions/grounding-refs.md` (stub)

---

## 2026-05-14T00:01:00

**Операция:** ingest (batch)
**Источники:** data/prompts/resolve.md, data/prompts/sql_plan.md, docs/superpowers/specs/2026-05-14-active-eval-validation-design.md, docs/superpowers/specs/2026-05-14-api-update-carts-design.md, data/prompts/answer.md (update)
**Домен:** документация

**Затронуто страниц:** 6

- СОЗДАНА: `.wiki/документация/pipeline-phases/resolve-phase.md` (developing)
- СОЗДАНА: `.wiki/документация/pipeline-phases/sql-plan-phase.md` (developing)
- СОЗДАНА: `.wiki/документация/specs/active-eval-validation.md` (developing)
- СОЗДАНА: `.wiki/документация/specs/api-update-carts.md` (developing)
- ОБНОВЛЕНА: `.wiki/документация/pipeline-phases/answer-phase.md` — добавлен раздел Cart Answers, статус stub→developing
- ОБНОВЛЕНА: `.wiki/документация/design-decisions/grounding-refs.md` — добавлен раздел cart grounding_refs, статус stub→developing

---

## 2026-05-14T00:02:00

**Операция:** ingest
**Источник:** scripts/CLAUDE.md
**Домен:** документация (определён по содержимому — файл вне `docs/`, но описывает agent-модуль)

**Затронуто страниц:** 2

- СОЗДАНА: `.wiki/документация/agent-modules/propose-optimizations.md` (developing) — entity_type: agent-module
- СОЗДАНА: `.wiki/документация/design-decisions/eval-optimization-dedup.md` (developing) — entity_type: design-decision

---

## 2026-05-15T00:00:00

**Операция:** ingest
**Источник:** data/prompts/test_gen.md
**Домен:** документация (определён по содержимому — файл вне `docs/`, но описывает pipeline-phase TDD)

**Затронуто страниц:** 1

- СОЗДАНА: `.wiki/документация/pipeline-phases/test-generation-phase.md` (stub) — entity_type: pipeline-phase

---

## 2026-05-16T00:00:00

**Операция:** ingest
**Источник:** .worktrees/mock-validation/data/prompts/mock_gen.md
**Домен:** документация (определён по содержимому — промпт-фаза офлайн-валидации пайплайна агента)

**Затронуто страниц:** 2

- СОЗДАНА: `.wiki/документация/pipeline-phases/mock-gen-phase.md` (stub) — entity_type: pipeline-phase
- СОЗДАНА: `.wiki/документация/design-decisions/mock-validation-offline.md` (stub) — entity_type: design-decision

---

