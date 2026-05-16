# Wiki Index

<!-- Этот файл обновляется автоматически при ingest/init/query --save -->

## Страницы по доменам

### документация

#### pipeline-phases
- `.wiki/документация/pipeline-phases/answer-phase.md` — Фаза ANSWER: финальный синтез JSON-ответа по результатам SQL
- `.wiki/документация/pipeline-phases/resolve-phase.md` — Фаза RESOLVE: value-resolution и генерация discovery SQL по идентификаторам задачи
- `.wiki/документация/pipeline-phases/sql-plan-phase.md` — Фаза SQL_PLAN: планирование SQL-запросов, изоляция discovery, cart queries
- `.wiki/документация/pipeline-phases/test-generation-phase.md` — Фаза Test Generation (TDD): генерация acceptance-тестов test_sql/test_answer до фазы ANSWER

#### design-decisions
- `.wiki/документация/design-decisions/grounding-refs.md` — Grounding Refs: механизм ссылок на SKU каталога через AUTO_REFS

#### specs
- `.wiki/документация/specs/active-eval-validation.md` — Active Eval Validation: переход от пассивного к активному eval с validate_recommendation()
- `.wiki/документация/specs/api-update-carts.md` — API Update + Shopping Carts: синхронизация с upstream API, /bin/date /bin/id, поддержка корзин

#### agent-modules
- `.wiki/документация/agent-modules/propose-optimizations.md` — propose_optimizations.py: синтез eval-рекомендаций в кандидат-файлы (rules, security, prompts)

#### design-decisions (additional)
- `.wiki/документация/design-decisions/eval-optimization-dedup.md` — Eval Optimization Deduplication: двухуровневая дедупликация (content-hash + LLM cluster + existing-content injection)
- `.wiki/документация/design-decisions/mock-validation-offline.md` — Офлайн-валидация пайплайна через синтетические моки (mock_results + answer_assertions без ECOM VM)

#### pipeline-phases (additional)
- `.wiki/документация/pipeline-phases/mock-gen-phase.md` — Фаза Mock Gen: генерация синтетических CSV-данных и Python-assertions для офлайн-валидации

