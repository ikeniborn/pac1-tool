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

Что выключено: evaluator (skeptic-гейт, для исследования неуместен), stall-detector, `TASK_TIMEOUT_S`, DSPy prompt_builder, LLM-voting классификатора (работает только regex fast-path).

Поток: внешний цикл ≤ `RESEARCHER_MAX_CYCLES` (default 10). На каждом цикле — inner `run_loop` (`researcher_mode=True`, `max_steps=RESEARCHER_STEPS_PER_CYCLE`). После inner-loop — reflector.py (1 LLM-вызов) структурирует траекторию в `{outcome, what_worked, what_failed, hypothesis_for_next, key_tool_calls, graph_deltas}`. Фрагмент пишется в `data/wiki/fragments/research/<task_type>/` (run_wiki_lint этот путь пропускает). Между циклами строится новый addendum: previous-cycle reflections + top-K узлов из графа + существующие wiki patterns.

Wiki policy:
- **fragments** накапливаются все циклы подряд;
- **pages** обновляются ТОЛЬКО на верифицированном успехе (`reflection.outcome=="solved"` AND агентский `OUTCOME_OK`) через `promote_successful_pattern()` → `## Successful pattern: <task_id> (date)` в `pages/<task_type>.md`. Idempotent по `task_id + hash_trajectory`. Ротация > `WIKI_PAGE_MAX_PATTERNS` → `archive/patterns/`.
- Повторный negative с той же траекторией → `archive/research_negatives/<task_id>_<hash>.json`, затронутые узлы графа получают `degrade_confidence(-epsilon)`; узлы ниже `WIKI_GRAPH_MIN_CONFIDENCE` → `graph_archive.json`.

Knowledge graph (`agent/wiki_graph.py`, `data/wiki/graph.json`):
- Узлы: `insight`, `rule`, `pattern`, `antipattern` с `{tags, confidence, uses, last_seen}`
- Рёбра: `requires`, `conflicts_with`, `generalizes`, `precedes`
- Retrieval при построении addendum: `retrieve_relevant(graph, task_type, task_text, top_k)` — scoring = tag_overlap + text-token overlap + confidence × log(uses)
- Инспекция: `uv run python scripts/print_graph.py [--all] [--tag email] [--edges]`

Env-переменные: `RESEARCHER_MODE`, `RESEARCHER_MAX_CYCLES`, `RESEARCHER_STEPS_PER_CYCLE`, `RESEARCHER_MODEL`, `WIKI_GRAPH_ENABLED`, `WIKI_GRAPH_TOP_K`, `WIKI_GRAPH_CONFIDENCE_EPSILON`, `WIKI_GRAPH_MIN_CONFIDENCE`, `WIKI_PAGE_MAX_PATTERNS` (все в `.env.example`).

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
