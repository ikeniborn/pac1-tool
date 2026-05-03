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
uv run python scripts/optimize_prompts.py --target builder   # Optimize prompt builder
uv run python scripts/optimize_prompts.py --target evaluator # Optimize evaluator

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

`models.json` contains per-model provider settings and per-task-type model assignments.

Task types: `think`, `distill`, `email`, `lookup`, `inbox`, `queue`, `capture`, `crm`, `temporal`, `preject`.

### Knowledge Graph (`agent/wiki_graph.py`, `data/wiki/graph.json`)

- Узлы: `insight`, `rule`, `pattern`, `antipattern` с `{tags, confidence, uses, last_seen}`
- Рёбра: `requires`, `conflicts_with`, `generalizes`, `precedes`
- Retrieval: `retrieve_relevant(graph, task_type, task_text, top_k)` — scoring = tag_overlap + text-token overlap + confidence × log(uses). Вариант `retrieve_relevant_with_ids()` дополнительно возвращает list of injected node ids для post-trial reinforcement.
- Инспекция: `uv run python scripts/print_graph.py [--all] [--tag email] [--edges]`

Граф наполняется двумя путями (FIX-389):
- **LLM-extractor** в `run_wiki_lint`: `_llm_synthesize` возвращает `(markdown, deltas)`. Prompt просит модель приложить fenced ```json {graph_deltas: ...}``` после страницы. Агрегируем deltas по всем категориям → один `merge_updates`/`save_graph` в конце lint. Парсинг fail-open: невалидный JSON → пишем только markdown. Гейт: `WIKI_GRAPH_AUTOBUILD=1`.
- **Pattern-extractor + confidence feedback** в `main.py` после `end_trial()`: `score=1.0` → `bump_uses` на узлы из prompt'а + `add_pattern_node` от `step_facts`; `score=0.0` → `degrade_confidence(epsilon)`. Гейт: `WIKI_GRAPH_FEEDBACK=1`.

Граф читается в **system prompt** агента (`agent/__init__.py`), в **DSPy addendum** (`prompt_builder.py:graph_context` InputField) и в **evaluator** (`evaluator.py:_load_graph_insights`). Все три гейчены `WIKI_GRAPH_ENABLED=1`.

`stats["graph_injected_node_ids"]` фиксирует, какие узлы агент видел в этом trial'е — feedback в `main.py` целит ровно по ним.

После расширения `PromptAddendum` Signature полем `graph_context` (FIX-389) ранее скомпилированные DSPy-программы в `data/prompt_builder_*_program.json` могут падать на отсутствующее поле в few-shot demos. `predictor.load()` обёрнут в try/except (fail-open в default-промпт), но для качества рекомендуется перекомпилировать: `uv run python scripts/optimize_prompts.py --target builder`.

Env-переменные: `WIKI_GRAPH_ENABLED`, `WIKI_GRAPH_TOP_K`, `WIKI_GRAPH_CONFIDENCE_EPSILON`, `WIKI_GRAPH_MIN_CONFIDENCE`, `WIKI_PAGE_MAX_PATTERNS`, `WIKI_GRAPH_AUTOBUILD`, `WIKI_GRAPH_FEEDBACK` (все в `.env.example`).

### Task-type registry (FIX-325)

Source of truth: `data/task_types.json`. Loader/API: `agent/task_types.py`.

Registry drives: classifier enum, `ClassifyTask` docstring, `cc_json_schema.task_type.enum` (runtime-injected in `cc_client.py`), regex fast-path in `classify_task()`, `ModelRouter` resolution, `wiki.py` folder map, `prompt_builder._NEEDS_BUILDER`.

Behavior branches that reference specific types (preject short-circuit in `agent/__init__.py`, scope-gates in `security.py`, stall-hints in `loop.py`, per-type system-prompt blocks in `prompt._TASK_BLOCKS`) stay in code and reference registry keys via `TASK_*` constants re-exported from `agent.classifier` / `agent.task_types`.

**Adding a type manually:**
1. Append entry to `data/task_types.json` with fields: `description`, `model_env`, `fallback_chain`, `wiki_folder`, `fast_path`, `needs_builder`, `status`.
2. Optionally set `MODEL_<UPPER>` in `.env` (otherwise `fallback_chain` resolves).
3. Optionally create `data/wiki/fragments/<wiki_folder>/`.
4. If `status: "soft"` → run `uv run python scripts/optimize_prompts.py --target classifier` to recompile DSPy program with the new enum.
5. If the type needs bespoke system-prompt guidance → add an entry to `_TASK_BLOCKS` in `agent/prompt.py`. Otherwise it inherits the `default` block (warn-once on startup).

**Soft-label workflow (open-set):** when the LLM classifier proposes a type outside `VALID_TYPES`, it's logged to `data/task_type_candidates.jsonl` (zero extra LLM calls). Passive summary via `agent/maintenance/candidates.py` (`log_candidates()`). Interactive promotion requires editing `data/task_types.json` manually.

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

**Evaluator uses wiki knowledge (FIX-367)**: `evaluate_completion()` injects two extra InputFields into `EvaluateCompletion`: `reference_patterns` (content of `data/wiki/pages/<task_type>.md` — Successful patterns + Verified refusals, score-gated) and `graph_insights` (top-K relevant nodes via `wiki_graph.retrieve_relevant`). Wiki/graph are ADVISORY — on conflict with hardcoded INBOX/ENTITY rules the hardcoded rules win. Env-gates: `EVALUATOR_WIKI_ENABLED`, `EVALUATOR_WIKI_MAX_CHARS_NASCENT/DEVELOPING/MATURE` (per-quality char limits, defaults 500/2000/4000), `EVALUATOR_GRAPH_TOP_K` (graph additionally gated behind `WIKI_GRAPH_ENABLED`). Recompile per-type evaluator programs after wiki pages grow: `uv run python scripts/optimize_prompts.py --target evaluator`.

**Stall Detection** (`stall.py`): Detects same-tool loops (3×), repeated path errors (2×), exploration stalls (6+ steps without write/delete). Adaptive hints escalate at 12+ steps.

**Security Gates** (`security.py`): Injection normalization (leet speak, zero-width chars, homoglyphs), contamination detection, write-scope enforcement (emails only to `/outbox/`, blocks system paths), OTP verification for admin elevation.

**Prefix-Compaction** (`log_compaction.py`): Preserves first system prompt + few-shot pair; compacts middle to last 5. Keeps context window manageable without losing task understanding.

### FIX-N Labels

Every non-trivial behavioral fix is tagged with a sequential `FIX-N` comment in code (current: `FIX-102+`). When fixing issues:

1. Add the next sequential `FIX-N` label to the relevant code.
2. Note it in `CHANGELOG.md`.

## Optimization Workflow

PAC1-tool supports two DSPy optimizer backends — **COPRO** (legacy) and **GEPA** (Genetic-Pareto Reflective Prompt Evolution). Selection is per-target via env:

| Env | Default | Effect |
|---|---|---|
| `OPTIMIZER_DEFAULT` | `copro` | Fallback for all targets |
| `OPTIMIZER_BUILDER` | (inherits) | Override for `prompt_builder` |
| `OPTIMIZER_EVALUATOR` | (inherits) | Override for `evaluator` |
| `OPTIMIZER_CLASSIFIER` | (inherits) | Override for `classifier` |
| `GEPA_AUTO` | `light` | `light|medium|heavy` budget preset |
| `GEPA_BUDGET_OVERRIDE` | (unset) | Fine-grained: `max_full_evals=N` or `max_metric_calls=N` |

1. Collect real examples — auto-saved to `data/dspy_examples.jsonl` (with `stall_detected`/`write_scope_violations` for richer GEPA feedback):
   ```bash
   uv run python main.py
   ```

2. Run optimizer (per-target backend selection):
   ```bash
   # Default: all targets via COPRO
   uv run python scripts/optimize_prompts.py --target builder

   # Mix-and-match: GEPA for builder, COPRO for evaluator
   OPTIMIZER_BUILDER=gepa uv run python scripts/optimize_prompts.py --target all
   ```

3. Compiled programs saved to `data/{builder,evaluator,classifier}_program.json` (and per-task_type variants). GEPA additionally saves Pareto frontier to `data/<target>_program_pareto/{0..N}.json` + `index.json` (advisory; agent loads only the main program).

4. Programs are loaded at agent startup automatically.

**Migration tips:**
- A/B comparison: run twice with different `OPTIMIZER_*` settings, compare benchmark scores.
- Roll back: unset `OPTIMIZER_*=gepa`; the existing COPRO-compiled JSON keeps working.
- Logs at `data/optimize_runs.jsonl` differentiate `target=builder/global` (task LM), `/meta` (COPRO prompt LM), `/reflection` (GEPA reflection LM).

## Protocol / Harness

- `proto/bitgn/vm/pcm.proto` — 9-tool RPC service definition.
- `bitgn/` — Generated Python stubs. **Do not edit manually** — regenerated by `make proto` and manual changes will be overwritten.
- Regenerate stubs:
  ```bash
  make proto
  # or, if make target unavailable:
  buf generate
  ```
