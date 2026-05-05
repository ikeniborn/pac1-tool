---
wiki_title: "Architecture Docs Actualization Implementation Plan"
wiki_status: stub
wiki_sources:
  - "docs/superpowers/plans/2026-04-30-architecture-docs-actualization.md"
wiki_updated: "2026-05-06"
tags: [refactor, docs, architecture, hub-spoke, contract, gepa]
---

# Architecture Docs Actualization

**Источник:** `docs/superpowers/plans/2026-04-30-architecture-docs-actualization.md`

## Цель

Обновить 5 файлов `docs/architecture/` чтобы отразить Hub-and-Spoke рефакторинг, contract phase, knowledge graph, GEPA backend и evaluator wiki injection.

## Пять файлов для обновления

| Файл | Что добавить |
|------|-------------|
| `docs/architecture/01-execution-flow.md` | Contract phase step + orchestrator hub |
| `docs/architecture/02-llm-routing.md` | CC tier + GEPA/COPRO backend selection |
| `docs/architecture/03-prompt-system.md` | Wiki graph injection + DSPy addendum |
| `docs/architecture/04-dspy-optimization.md` | Two-backend architecture (COPRO + GEPA) |
| `docs/architecture/05-security.md` | Contract mutation_scope gate + trusted-path whitelist |

## Принцип

Docs обновляются по коду, не наоборот. Все описания синхронизируются с актуальным поведением системы после применения всех фиксов из планов 2026-04-27 — 2026-04-30.
