# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Python-based AI agent for the BitGN PAC1 benchmark. The agent manages a personal knowledge vault through a 9-tool filesystem interface (`tree`, `find`, `search`, `list`, `read`, `write`, `delete`, `mkdir`, `move`, `report_completion`). Communication with the benchmark harness is via Protocol Buffers / gRPC-Connect.

## Commands

```bash
make sync                        # Install/sync dependencies (uv sync)
make run                         # Run all benchmark tasks
make task TASKS='t01,t02'        # Run specific tasks
uv run python -m pytest tests/   # Run full test suite
uv run pytest tests/test_security_gates.py  # Run single test file
uv run python optimize_prompts.py --target builder   # Optimize prompt builder
uv run python optimize_prompts.py --target evaluator # Optimize evaluator

# Debug: replay trace
uv run python -m agent.tracer logs/<trace_file>.jsonl
```

## Configuration

Environment variables loaded in order (highest priority first):

1. System environment
2. `.secrets` — API keys (`ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`)
3. `.env` — Non-secret config (copy from `.env.example`)

Key variables:

- `LOG_LEVEL=DEBUG` — enables full LLM response logging
- `PARALLEL_TASKS` — concurrent task execution (default `1`)
- `TASK_TIMEOUT_S` — per-task timeout (default `180s`)
- `EVALUATOR_ENABLED` / `PROMPT_BUILDER_ENABLED` — enable/disable DSPy subsystems
- `MODEL_DEFAULT`, `MODEL_EMAIL`, `MODEL_LOOKUP`, `MODEL_WIKI`, etc. — per-task-type model routing (`MODEL_WIKI` controls wiki-lint; all support `claude-code/*` prefix for CC tier)
- `CC_ENABLED=1`, `ICLAUDE_CMD`, `CC_MAX_RETRIES` — Claude Code tier config (see `.env.example`)
- `RESEARCHER_MODE=1` — альтернативный режим (FIX-362); выключает evaluator/stall/timeout, делегирует в `agent/researcher.py`

`models.json` contains per-model provider settings and per-task-type model assignments.

Task types: `think`, `distill`, `email`, `lookup`, `inbox`, `queue`, `capture`, `crm`, `temporal`, `preject`.

### Researcher mode (FIX-362)

Альтернативный режим для сбора данных и ручного разбора сложных задач. Активируется через `RESEARCHER_MODE=1`, normal mode остаётся нетронутым.

**ВАЖНО**: выставлять `PARALLEL_TASKS=1`. Параллельные задачи все загружают `graph.json`/`pages/` одновременно при старте и не видят паттернов друг друга — знание накапливается только при последовательном исполнении.

Что выключено: evaluator (skeptic-гейт, для исследования неуместен), stall-detector, `TASK_TIMEOUT_S`, DSPy prompt_builder, LLM-voting классификатора (работает только regex fast-path).

Поток: внешний цикл ≤ `RESEARCHER_MAX_CYCLES` (default 10). На каждом цикле — inner `run_loop` (`researcher_mode=True`, `max_steps=RESEARCHER_STEPS_PER_CYCLE`). После inner-loop — reflector.py (1 LLM-вызов) структурирует траекторию в `{outcome, what_worked, what_failed, hypothesis_for_next, key_tool_calls, graph_deltas, goal_shape, final_answer, input_tokens, output_tokens}`. Фрагмент пишется в `data/wiki/fragments/research/<task_type>/` (run_wiki_lint этот путь пропускает). Между циклами строится новый addendum: previous-cycle reflections + top-K узлов из графа + существующие wiki patterns. На cycle ≥ 2 — `graph.json` перечитывается с диска и мержится в in-memory (FIX-366) для подхвата паттернов от sequential-задач.

Wiki policy:
- **fragments** накапливаются все циклы подряд;
- **pages** обновляются ТОЛЬКО на верифицированном успехе (`reflection.outcome=="solved"` AND агентский `OUTCOME_OK` AND benchmark `score==1.0`) через `promote_successful_pattern()` → `## Successful pattern: <task_id> (date)` в `pages/<task_type>.md`. Idempotent по `task_id + hash_trajectory`. Ротация > `WIKI_PAGE_MAX_PATTERNS` → `archive/patterns/`. Score-gate делается в `main.py` после `end_trial()` (FIX-363a).
- **verified refusals** (FIX-366): terminal refusal (`NONE_CLARIFICATION`/`NONE_UNSUPPORTED`/`DENIED_SECURITY`) + `score==1.0` → `promote_verified_refusal()` записывает `## Verified refusal: <task_id> (date)` в тот же `pages/<task_type>.md`. Отдельный маркер `<!-- refusal: task_id:outcome -->`, ротация в `archive/refusals/<page>/`.
- Повторный negative с той же траекторией → `archive/research_negatives/<task_id>_<hash>.json`, затронутые узлы графа получают `degrade_confidence(-epsilon)`; узлы ниже `WIKI_GRAPH_MIN_CONFIDENCE` → `graph_archive.json`.

Cycle-retry policy (FIX-374): benchmark score недоступен внутри trial'а, поэтому между циклами работают два разных механизма продолжения.
- **Terminal refusal** (`OUTCOME_NONE_CLARIFICATION`/`NONE_UNSUPPORTED`/`DENIED_SECURITY`) — retry с хинтом `REFUSAL_RETRY: ...` в `hypothesis_for_next` до `RESEARCHER_REFUSAL_MAX_RETRIES` раз (default 3), далее принимаем refusal и short-circuit с `pending_refusal`. Evaluator не вызывается (наблюдаемый false-approve на t11). Cap нужен чтобы агент, сходящийся на refusal, не жёг все `max_cycles` впустую.
- **Self-OUTCOME_OK** при `RESEARCHER_EVAL_GATED=1` и `cycle < max_cycles` — вызов `evaluate_completion()` как прокси-score. `approved=False` → `EVAL_REJECTED: ...` в `hypothesis_for_next`, `continue`. `approved=True` → short-circuit + `pending_promotion`. Fail-open на любой ошибке evaluator'а.
- Запись в `pages/` по-прежнему гейчится реальным `score≥1.0` в `main.py`.
- Env: `RESEARCHER_EVAL_GATED` (default 0), `RESEARCHER_EVAL_SKEPTICISM=high`, `RESEARCHER_EVAL_EFFICIENCY=mid`. Refusal-retry всегда включён в researcher mode, флага нет.
- DSPy сбор: при `DSPY_COLLECT=1` + `RESEARCHER_EVAL_GATED=1` последний gate-call записывается в `data/dspy_eval_examples.jsonl` с реальным `score` как label (`score==1.0 → yes`, иначе `no`). Особо ценны false-approves (approved + score=0) — учат evaluator ловить неверные self-OUTCOME_OK. Builder-примеры не собираются (addendum строит reflector).

OUTCOME_FLIP_HINT + diversification detector (FIX-375): два симметричных механизма выхода из local minimum reflector'а.
- **OK-side flip**: в ветке evaluator reject при ≥2 rejection'ах с Jaccard-similarity reason'ов ≥ threshold ИЛИ монотонности последних `K+1` сырых `hypothesis_for_next` — в `hypothesis_for_next` добавляется `OUTCOME_FLIP_HINT: ...consider OUTCOME_NONE_CLARIFICATION/UNSUPPORTED`. Цель: t43-класс (reflector залип на одной интерпретации, evaluator отклоняет с одним и тем же reason).
- **Refusal last-chance**: после `RESEARCHER_REFUSAL_MAX_RETRIES` exhausted вместо сразу accept — один extra цикл с зеркальным `OUTCOME_FLIP_HINT: ...attempt any plausible interpretation where task IS answerable`. Цель: t11/t19-класс (агент упорно refuse'ит, но задача может быть решаема).
- Env: `RESEARCHER_FLIP_HINT_ENABLED=1`, `RESEARCHER_FLIP_REASON_SIMILARITY_THRESHOLD=0.5`, `RESEARCHER_FLIP_HYP_MONOTONIC_K=2`, `RESEARCHER_FLIP_HYP_SIMILARITY_THRESHOLD=0.6`, `RESEARCHER_REFUSAL_LAST_CHANCE=1`. Stats: `researcher_flip_hints_injected`.

OK-loop hardening (FIX-375b) — три связанных изменения от наблюдения t43 (15 циклов OUTCOME_OK с одним и тем же final_answer, evaluator не вызывался ни разу из-за reflector.is_solved=False):
- **(A) evaluator-primary gate**: `_gate_relevant` снимает `reflection.is_solved` из условия — evaluator теперь судит любой `OUTCOME_OK` при `RESEARCHER_EVAL_GATED=1`. Reflector становится контекстом, не блокатором. Evaluator approve при `is_solved=False` → researcher переписывает `reflection.outcome="solved"` для consistency с promotion-блоком.
- **(B) reflector outcome-history**: `reflect()` принимает `outcome_history: list[str]` (последние 5 циклов), включает блок `PREVIOUS_OUTCOMES (last N cycles): ...` в user_msg с подсказкой «consider whether the task is truly answerable». Раньше reflector видел только текущий цикл изолированно, не замечая 14× повторов.
- **(C) hard guard**: после `RESEARCHER_OK_LOOP_LIMIT` (default 5) consecutive OUTCOME_OK с identical final_answer (trim+lowercase) — forced short-circuit с `pending_refusal{outcome=OUTCOME_NONE_CLARIFICATION}`. Срабатывает ДО evaluator gate (не тратит LLM-вызовы на повторное rejection). Counter resets когда `agent_outcome != OUTCOME_OK` или final_answer изменился.
- Stats: `researcher_ok_loop_break: True` (флаг trip'а), `researcher_early_stop="OUTCOME_NONE_CLARIFICATION"`. Pending_refusal записывается через тот же score-gate что и обычный refusal в `main.py`.

Knowledge graph (`agent/wiki_graph.py`, `data/wiki/graph.json`):
- Узлы: `insight`, `rule`, `pattern`, `antipattern` с `{tags, confidence, uses, last_seen}`
- Рёбра: `requires`, `conflicts_with`, `generalizes`, `precedes`
- Retrieval при построении addendum: `retrieve_relevant(graph, task_type, task_text, top_k)` — scoring = tag_overlap + text-token overlap + confidence × log(uses)
- Инспекция: `uv run python scripts/print_graph.py [--all] [--tag email] [--edges]`

Env-переменные: `RESEARCHER_MODE`, `RESEARCHER_MAX_CYCLES`, `RESEARCHER_STEPS_PER_CYCLE`, `MODEL_RESEARCHER`, `RESEARCHER_LOG_ENABLED`, `RESEARCHER_NEGATIVES_ENABLED`/`RESEARCHER_NEGATIVES_TOP_K` (FIX-370), `RESEARCHER_SHORT_CIRCUIT`/`RESEARCHER_SHORT_CIRCUIT_THRESHOLD` (FIX-371, offline-only), `RESEARCHER_DRIFT_HINTS`/`RESEARCHER_DRIFT_PREFIX_LEN` (FIX-372), `RESEARCHER_EVAL_GATED`/`RESEARCHER_EVAL_SKEPTICISM`/`RESEARCHER_EVAL_EFFICIENCY` (FIX-374), `RESEARCHER_FLIP_HINT_ENABLED`/`RESEARCHER_FLIP_REASON_SIMILARITY_THRESHOLD`/`RESEARCHER_FLIP_HYP_MONOTONIC_K`/`RESEARCHER_FLIP_HYP_SIMILARITY_THRESHOLD`/`RESEARCHER_REFUSAL_LAST_CHANCE` (FIX-375), `RESEARCHER_OK_LOOP_LIMIT` (FIX-375b), `RESEARCHER_EVAL_FAIL_CLOSED`/`RESEARCHER_HINT_FORCING`/`RESEARCHER_HINT_MAX_INJECTIONS`/`RESEARCHER_MIDCYCLE_BREAKOUT`/`RESEARCHER_MIDCYCLE_CHECK_EVERY`/`RESEARCHER_MIDCYCLE_REPEAT_THRESHOLD`/`RESEARCHER_REFLECTOR_DIVERSIFY`/`RESEARCHER_REFLECTOR_PRIOR_WINDOW`/`RESEARCHER_STEPS_ADAPTIVE`/`RESEARCHER_STEPS_MAX`/`RESEARCHER_TOTAL_STEP_BUDGET`/`RESEARCHER_SOFT_STALL`/`RESEARCHER_REFUSAL_DYNAMIC`/`RESEARCHER_REFUSAL_MIN_CYCLES_LEFT`/`RESEARCHER_GRAPH_QUARANTINE`/`RESEARCHER_GRAPH_MIN_CONF`/`RESEARCHER_DRIFT_FULL_TRACE`/`RESEARCHER_DRIFT_LCS_MIN` (FIX-376, все default OFF; FIX-376e — global escape ladder через `RESEARCHER_TOTAL_STEP_BUDGET=180` cumulative cap), `WIKI_GRAPH_ENABLED`, `WIKI_GRAPH_TOP_K`, `WIKI_GRAPH_CONFIDENCE_EPSILON`, `WIKI_GRAPH_MIN_CONFIDENCE`, `WIKI_PAGE_MAX_PATTERNS` (все в `.env.example`).

CC-tier совместим: reflector и inner-loop используют `dispatch.call_llm_raw`, роутинг по `provider` в `models.json`.

### Task-type registry (FIX-325)

Source of truth: `data/task_types.json`. Loader/API: `agent/task_types.py`.

Registry drives: classifier enum, `ClassifyTask` docstring, `cc_json_schema.task_type.enum` (runtime-injected in `cc_client.py`), regex fast-path in `classify_task()`, `ModelRouter` resolution, `wiki.py` folder map, `prompt_builder._NEEDS_BUILDER`.

Behavior branches that reference specific types (preject short-circuit in `agent/__init__.py`, scope-gates in `security.py`, stall-hints in `loop.py`, per-type system-prompt blocks in `prompt._TASK_BLOCKS`) stay in code and reference registry keys via `TASK_*` constants re-exported from `agent.classifier` / `agent.task_types`.

**Adding a type manually:**
1. Append entry to `data/task_types.json` with fields: `description`, `model_env`, `fallback_chain`, `wiki_folder`, `fast_path`, `needs_builder`, `status`.
2. Optionally set `MODEL_<UPPER>` in `.env` (otherwise `fallback_chain` resolves).
3. Optionally create `data/wiki/fragments/<wiki_folder>/`.
4. If `status: "soft"` → run `uv run python optimize_prompts.py --target classifier` to recompile DSPy program with the new enum.
5. If the type needs bespoke system-prompt guidance → add an entry to `_TASK_BLOCKS` in `agent/prompt.py`. Otherwise it inherits the `default` block (warn-once on startup).

**Soft-label workflow (open-set):** when the LLM classifier proposes a type outside `VALID_TYPES`, it's logged to `data/task_type_candidates.jsonl` (zero extra LLM calls). Aggregate + promote via:

```bash
uv run python scripts/analyze_task_types.py                     # summary
uv run python scripts/analyze_task_types.py --promote           # interactive add
uv run python scripts/analyze_task_types.py --min-count 3       # override threshold
```

Promoted types start with `status: "soft"` — they're in the enum and system prompt, but the compiled DSPy classifier won't predict them until recompiled.

## Architecture

### Execution Flow

```
main.py → run_agent()
  1. classify task type + select model  (classifier.py)
  2. prephase: load vault tree + AGENTS.MD  (prephase.py)
  3. build system prompt  (prompt.py)
  4. build_dynamic_addendum (DSPy)  (prompt_builder.py)
  5. main agent loop ≤30 steps  (loop.py)
       ├─ dispatch LLM call  (dispatch.py)
       ├─ stall detection  (stall.py)
       ├─ security gates  (security.py)
       ├─ evaluator review before submission  (evaluator.py)
       └─ PCM tool execution  (bitgn/)
```

### Key Patterns

**Tool-Based Architecture** (`prompt.py`): The system prompt instructs the agent to emit structured JSON commands (validated via Pydantic `NextStep`) that name one of the 9 PCM tools. The dispatcher parses the JSON and invokes the matching protobuf RPC against the PCM harness. Claude-native function calling (`tools=`, `tool_use`/`tool_result` blocks) is **not** used — the model is a pure text generator producing JSON. For the Claude Code tier (`cc_client.py`), all built-in tools are explicitly banned via `--disallowed-tools` (FIX-340).

**Discovery-First Prompting**: No vault paths are hardcoded in the system prompt. The agent discovers folder roles from `AGENTS.MD`, pre-loaded in prephase.

**Four-Tier LLM Dispatch** (`dispatch.py`): Anthropic SDK / Claude Code → OpenRouter → Ollama, with automatic retry on `429`/`502`/`503`. Tier is picked by `provider` in `models.json`: `claude-code/*` models route to `cc_client.cc_complete()` (stateless `iclaude` subprocess over OAuth) instead of the Anthropic SDK — mutually exclusive, not cascade. Env-gated by `CC_ENABLED=1`.

**DSPy Prompt Optimization**: `prompt_builder.py` generates 3–6 bullet points of task-specific guidance; `evaluator.py` does quality review. Both are compiled via COPRO and stored in `data/`. They fail-open if compiled programs are missing.

**Evaluator consumes researcher knowledge (FIX-367)**: `evaluate_completion()` injects two extra InputFields into `EvaluateCompletion`: `reference_patterns` (content of `data/wiki/pages/<task_type>.md` — Successful patterns + Verified refusals score-gated promoted by researcher) and `graph_insights` (top-K relevant nodes via `wiki_graph.retrieve_relevant`). Wiki/graph are ADVISORY — on conflict with hardcoded INBOX/ENTITY rules the hardcoded rules win. Env-gates: `EVALUATOR_WIKI_ENABLED`, `EVALUATOR_WIKI_MAX_CHARS`, `EVALUATOR_GRAPH_TOP_K` (graph additionally gated behind `WIKI_GRAPH_ENABLED`). After growing researcher corpus recompile per-type evaluator programs: `uv run python optimize_prompts.py --target evaluator`.

**Stall Detection** (`stall.py`): Detects same-tool loops (3×), repeated path errors (2×), exploration stalls (6+ steps without write/delete). Adaptive hints escalate at 12+ steps.

**Security Gates** (`security.py`): Injection normalization (leet speak, zero-width chars, homoglyphs), contamination detection, write-scope enforcement (emails only to `/outbox/`, blocks system paths), OTP verification for admin elevation.

**Prefix-Compaction** (`log_compaction.py`): Preserves first system prompt + few-shot pair; compacts middle to last 5. Keeps context window manageable without losing task understanding.

### FIX-N Labels

Every non-trivial behavioral fix is tagged with a sequential `FIX-N` comment in code (current: `FIX-102+`). When fixing issues:

1. Add the next sequential `FIX-N` label to the relevant code.
2. Note it in `CHANGELOG.md`.

## Optimization Workflow

1. Collect real examples — auto-saved to `data/dspy_examples.jsonl`:
   ```bash
   uv run python main.py
   ```
2. Run optimizer:
   ```bash
   uv run python optimize_prompts.py --target builder
   ```
3. Compiled programs saved to `data/prompt_builder_program.json` and `data/evaluator_program.json`.
4. Programs are loaded at agent startup automatically.

## Protocol / Harness

- `proto/bitgn/vm/pcm.proto` — 9-tool RPC service definition.
- `bitgn/` — Generated Python stubs. **Do not edit manually** — regenerated by `make proto` and manual changes will be overwritten.
- Regenerate stubs:
  ```bash
  make proto
  # or, if make target unavailable:
  buf generate
  ```
