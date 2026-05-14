# Graph Report - .  (2026-05-14)

## Corpus Check
- Corpus is ~10,688 words - fits in a single context window. You may not need a graph.

## Summary
- 847 nodes · 1398 edges · 72 communities (51 shown, 21 thin omitted)
- Extraction: 83% EXTRACTED · 17% INFERRED · 0% AMBIGUOUS · INFERRED: 241 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Pipeline Core|Pipeline Core]]
- [[_COMMUNITY_Prephase & Schema Parsing|Prephase & Schema Parsing]]
- [[_COMMUNITY_Security & Grounding Checks|Security & Grounding Checks]]
- [[_COMMUNITY_Trace & Logging|Trace & Logging]]
- [[_COMMUNITY_LLM Dispatch|LLM Dispatch]]
- [[_COMMUNITY_Evaluator|Evaluator]]
- [[_COMMUNITY_Resolve Phase|Resolve Phase]]
- [[_COMMUNITY_JSON Extraction|JSON Extraction]]
- [[_COMMUNITY_Optimization Tests|Optimization Tests]]
- [[_COMMUNITY_BitGN Connect RPC|BitGN Connect RPC]]
- [[_COMMUNITY_LLM Routing|LLM Routing]]
- [[_COMMUNITY_Contract Models|Contract Models]]
- [[_COMMUNITY_Schema Gate|Schema Gate]]
- [[_COMMUNITY_Harness RPC|Harness RPC]]
- [[_COMMUNITY_Prompt Builder|Prompt Builder]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]

## God Nodes (most connected - your core abstractions)
1. `run_pipeline()` - 38 edges
2. `TraceLogger` - 27 edges
3. `check_sql_queries()` - 21 edges
4. `load_prompt()` - 20 edges
5. `check_schema_compliance()` - 20 edges
6. `main()` - 18 edges
7. `run_prephase()` - 16 edges
8. `EcomRuntimeClientSync` - 15 edges
9. `_write_eval_log()` - 15 edges
10. `_eval_entry()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `t16 grounding refs bug` --related_to--> `grounding_refs (AnswerOutput field)`  [INFERRED]
  task.txt → agent/CLAUDE.md
- `_run_single_task()` --calls--> `TraceLogger`  [INFERRED]
  main.py → agent/trace.py
- `_run_single_task()` --calls--> `set_trace()`  [INFERRED]
  main.py → agent/trace.py
- `_run_single_task()` --calls--> `run_agent()`  [INFERRED]
  main.py → agent/orchestrator.py
- `_run_single_task()` --calls--> `get_trace()`  [INFERRED]
  main.py → agent/trace.py

## Communities (72 total, 21 thin omitted)

### Community 0 - "Pipeline Core"
Cohesion: 0.06
Nodes (72): _build_learn_user_msg(), _build_sql_user_msg(), _build_static_system(), _call_llm_phase(), _csv_has_data(), _exec_result_text(), _extract_discovery_results(), _format_confirmed_values() (+64 more)

### Community 1 - "Prephase & Schema Parsing"
Cohesion: 0.06
Nodes (48): parse_agents_md(), Parse AGENTS.MD into {section_name: [lines]} for each ## section., _build_schema_digest(), _exec_sql_text(), _parse_csv_rows(), PrephaseResult, run_prephase(), test_empty_section_has_empty_lines() (+40 more)

### Community 2 - "Security & Grounding Checks"
Cohesion: 0.06
Nodes (47): check_grounding_refs(), check_learn_output(), check_path_access(), check_retry_loop(), check_sql_queries(), check_where_literals(), _has_where_clause(), _is_select() (+39 more)

### Community 3 - "Trace & Logging"
Cohesion: 0.08
Nodes (31): get_trace(), Thread-local structured JSONL trace logger for per-task pipeline traces., set_trace(), TraceLogger, _collect_trace_records(), _exec_ok(), _make_pre(), Verify pipeline instruments TraceLogger at all required points. (+23 more)

### Community 4 - "LLM Dispatch"
Cohesion: 0.07
Nodes (37): call_llm_raw(), _call_raw_single_model(), dispatch(), get_anthropic_model_id(), get_provider(), get_response_format(), _get_static_hint(), is_claude_code_model() (+29 more)

### Community 5 - "Evaluator"
Cohesion: 0.1
Nodes (32): _append_log(), _build_eval_system(), _compute_eval_metrics(), EvalInput, Post-execution pipeline evaluator. Fail-open: any exception returns None., Compute agents_md_coverage and schema_grounding. Returns dict with both floats., Compute agents_md_coverage and schema_grounding. Returns dict with both floats., Evaluate pipeline trace. Returns PipelineEvalOutput or None on any failure. (+24 more)

### Community 6 - "Resolve Phase"
Cohesion: 0.12
Nodes (34): _all_values(), _build_resolve_system(), _exec_sql(), _first_value(), Resolve phase: confirm task identifiers against DB before pipeline cycles., Deprecated shim — kept for test backward compat. Use _all_values., Resolve identifiers in task_text against DB. Returns confirmed_values or {} on f, Resolve identifiers in task_text against DB. Returns confirmed_values or {} on f (+26 more)

### Community 7 - "JSON Extraction"
Cohesion: 0.11
Nodes (32): _extract_json_from_text(), _obj_mutation_tool(), JSON extraction from free-form LLM text output.  Public API:   _obj_mutation_too, Try json5 parse; raises on failure (ImportError or parse error)., Return the mutation tool name if obj is a write/delete/exec action, else None., Lower tuple = preferred. Used by min() to break ties among same-tier candidates., Extract the most actionable valid JSON object from free-form model output., _richness_key() (+24 more)

### Community 8 - "Optimization Tests"
Cohesion: 0.17
Nodes (33): _base_patches(), _eval_entry(), Ensure propose_optimizations imports rules text from knowledge_loader, not its o, _cluster_recs returns fewer items when LLM merges duplicates., _cluster_recs returns items as-is when LLM call fails., All hashes in a cluster group are marked processed after writing the representat, Second rule synthesis receives updated rules_md after first write., Returns None when LLM says OK. (+25 more)

### Community 9 - "BitGN Connect RPC"
Cohesion: 0.06
Nodes (4): ConnectClient, Minimal Connect RPC client using JSON protocol over httpx., EcomRuntimeClientSync, PcmRuntimeClientSync

### Community 10 - "LLM Routing"
Cohesion: 0.08
Nodes (26): _call_raw_single_model(), get_anthropic_model_id(), get_provider(), get_response_format(), _get_static_hint(), is_claude_code_model(), is_claude_model(), is_ollama_model() (+18 more)

### Community 11 - "Contract Models"
Cohesion: 0.15
Nodes (27): Contract, ContractRound, EvaluatorResponse, ExecutorProposal, AnswerOutput, LearnOutput, PipelineEvalOutput, ResolveCandidate (+19 more)

### Community 12 - "Schema Gate"
Cohesion: 0.1
Nodes (29): _build_alias_map(), _check_query(), check_schema_compliance(), _known_cols_by_table(), Schema-aware SQL validator: unknown columns, unverified literals, double-key JOI, Check queries against schema. Returns first error string or None if all pass., Return {table_name_lower: {col_name_lower, ...}}., Return {alias_lower: table_name_lower} from FROM and JOIN clauses. (+21 more)

### Community 13 - "Harness RPC"
Cohesion: 0.13
Nodes (16): HarnessServiceClientSync, _log_stats(), main(), _print_table_header(), _print_table_row(), Execute one benchmark trial., Execute one benchmark trial., Execute one benchmark trial. (+8 more)

### Community 14 - "Prompt Builder"
Cohesion: 0.13
Nodes (21): build_system_prompt(), load_prompt(), System prompt builder — loads blocks from data/prompts/*.md., Return prompt block by file stem name. Returns '' if not found., Assemble system prompt from file-based blocks for the given task type., test_build_system_prompt_fallback_to_default_for_unknown(), test_build_system_prompt_lookup_contains_core_and_catalogue(), test_core_has_ecom_role() (+13 more)

### Community 15 - "Community 15"
Cohesion: 0.12
Nodes (14): close_tracer(), get_task_tracer(), init_tracer(), Replay tracer for the agent loop (П3).  Writes JSONL event stream to logs/{ts}_{, Store task_id in thread-local so loop.py can access it without signature changes, Return a TaskTracer bound to task_id (falls back to thread-local if not given)., Flush and close the run-level tracer. Call at process exit., Append-only JSONL writer. Fail-open: errors in emit() never propagate. (+6 more)

### Community 16 - "Community 16"
Cohesion: 0.15
Nodes (17): _build_answer_user_msg(), _extract_sku_refs(), Extract /proc/catalog/{sku}.json paths from SQL results that contain a sku colum, Extract /proc/catalog/{sku}.json paths from SQL results that contain a sku colum, Extract catalogue paths from SQL results. Uses 'path' column when present,     f, Raw hierarchical paths stored verbatim in sku_refs., AUTO_REFS block shows short-form refs regardless of raw path depth., clean_refs accepts model output in any format, outputs short-form. (+9 more)

### Community 17 - "Community 17"
Cohesion: 0.18
Nodes (10): Minimal orchestrator for ecom benchmark., Execute a single benchmark task., run_agent(), _make_vm_mock(), run_agent calls run_pipeline for all tasks., run_agent() result must not contain builder_*/contract_*/eval_rejection_count fi, run_agent() always returns a plain dict (public API unchanged)., test_lookup_routes_to_pipeline() (+2 more)

### Community 18 - "Community 18"
Cohesion: 0.24
Nodes (7): Load SQL planning rules from data/rules/ (one YAML file per rule)., RulesLoader, _make_rules_dir(), Create a rules directory with two individual rule files., test_empty_directory_returns_empty(), test_load_all_rules(), test_load_verified_rules_only()

### Community 19 - "Community 19"
Cohesion: 0.24
Nodes (11): EXECUTE phase, json_extract.py, pipeline.py, pipeline execution phases, resolve.py:run_resolve(), run_pipeline, schema_gate.py:check_schema_compliance(), SQL_PLAN phase (+3 more)

### Community 20 - "Community 20"
Cohesion: 0.18
Nodes (9): `bitgn/harness.proto` — Benchmark lifecycle, `bitgn/vm/ecom/ecom.proto` — ECOM vault runtime (current), `bitgn/vm/pcm.proto` — PCM vault runtime (legacy), code:bash (# From project root (ecom1-agent/)), code:block2 (main.py), Parent project architecture (brief), Proto files, Regenerating stubs (+1 more)

### Community 21 - "Community 21"
Cohesion: 0.27
Nodes (8): _build_env(), cc_complete(), _parse_envelope(), Claude Code tier — spawn iclaude CLI as stateless LLM.  Bypasses applied (all re, Spawn iclaude once. Returns (stdout_lines, exit_code, fail_reason).     fail_rea, Stateless LLM call via iclaude subprocess.      Returns assistant text (JSON str, Extract result text and token usage from iclaude --output-format json.     Envel, _spawn_once()

### Community 22 - "Community 22"
Cohesion: 0.2
Nodes (9): code:bash (cp .env.example .env        # добавить MODEL_EVALUATOR=anthr), code:bash (EVAL_ENABLED=1 uv run python main.py   # собрать eval_log), code:bash (uv run python scripts/propose_optimizations.py), code:bash (# Просмотреть предложенные правила), scripts/propose_optimizations.py, Запуск, Предварительные требования, Проверка и применение (+1 more)

### Community 23 - "Community 23"
Cohesion: 0.2
Nodes (7): _write_dry_run(), dry_run=True: 2 vm.read calls, bin_sql_content populated., bin_sql content must NOT appear in LLM log messages., _write_dry_run writes correct JSON fields to jsonl., test_dry_run_bin_sql_not_in_log(), test_dry_run_reads_bin_sql(), test_write_dry_run_format()

### Community 24 - "Community 24"
Cohesion: 0.31
Nodes (9): AGENTS.MD vault rules, build_system_prompt, data/prompts/*.md, evaluator.py, load_prompt(phase), prephase.py:run_prephase(), prompt.py:load_prompt(), run_agent (+1 more)

### Community 25 - "Community 25"
Cohesion: 0.22
Nodes (9): ANSWER phase, AnswerOutput, grounding_refs (AnswerOutput field), LEARN phase (_run_learn), LearnOutput, models.py Pydantic models, Answer.outcome values, PipelineEvalOutput (+1 more)

### Community 26 - "Community 26"
Cohesion: 0.29
Nodes (8): data/prompts/optimized/, data/security/*.yaml, data/eval_log.jsonl, optimization output channels, scripts/propose_optimizations.py, sql_security.py, adding a new optimization channel, propose_optimizations script

### Community 27 - "Community 27"
Cohesion: 0.25
Nodes (6): .eval_optimizations_processed, Adding a New Channel, code:bash (# Preview what would be written (no files changed)), Commands, Deduplication, What This Script Does

### Community 28 - "Community 28"
Cohesion: 0.29
Nodes (8): bitgn/, main.py, orchestrator.py:run_agent(), proto/, buf CLI, EcomRuntime, HarnessService, PcmRuntime (legacy)

### Community 29 - "Community 29"
Cohesion: 0.29
Nodes (6): Test that all vault classes have been removed from models.py, Test that models.py contains exactly 6 BaseModel classes (4 pipeline + 2 resolve, Test that the 4 pipeline models are present in models.py, test_models_has_exactly_six_classes(), test_pipeline_models_present(), test_vault_models_removed()

### Community 30 - "Community 30"
Cohesion: 0.29
Nodes (5): Architecture, code:bash (uv sync                                          # install a), Commands, Key Data Files, Notable Constraints

### Community 31 - "Community 31"
Cohesion: 0.29
Nodes (7): call_llm_raw, cc_client.py, data/rules/*.yaml, llm.py:call_llm_raw(), LLM routing strategy, rules_loader.py:RulesLoader, Synthesizer Behavior

### Community 33 - "Community 33"
Cohesion: 0.33
Nodes (5): Verify main.py creates/closes TraceLogger and calls log_header + log_task_result, main.log must contain stats rows but NOT pipeline cycle lines., After _run_single_task: .jsonl created, no .log file, log_header + log_task_resu, test_main_log_contains_only_stats(), test_run_single_task_creates_jsonl_and_removes_log()

### Community 35 - "Community 35"
Cohesion: 0.33
Nodes (4): Agent Package Architecture, code:bash (uv sync                                          # install a), Commands, Notable Constraints

### Community 37 - "Community 37"
Cohesion: 0.6
Nodes (5): check_grounding_refs, clean_refs, p.path SQL column, sku_refs, t16 grounding refs bug

## Knowledge Gaps
- **241 isolated node(s):** `Tee stdout to logs/{ts}_{model}.log. ANSI codes are stripped in file.`, `Execute one benchmark trial.`, `Claude Code tier — spawn iclaude CLI as stateless LLM.  Bypasses applied (all re`, `Extract result text and token usage from iclaude --output-format json.     Envel`, `Spawn iclaude once. Returns (stdout_lines, exit_code, fail_reason).     fail_rea` (+236 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **21 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_pipeline()` connect `Pipeline Core` to `Security & Grounding Checks`, `Trace & Logging`, `Resolve Phase`, `Schema Gate`, `Community 16`, `Community 17`?**
  _High betweenness centrality (0.190) - this node is a cross-community bridge._
- **Why does `run_agent()` connect `Community 17` to `Pipeline Core`, `BitGN Connect RPC`, `Harness RPC`, `Prephase & Schema Parsing`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._
- **Why does `run_prephase()` connect `Prephase & Schema Parsing` to `Community 17`?**
  _High betweenness centrality (0.076) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `run_pipeline()` (e.g. with `run_agent()` and `test_happy_path()`) actually correct?**
  _`run_pipeline()` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `TraceLogger` (e.g. with `_run_single_task()` and `test_set_and_get_trace()`) actually correct?**
  _`TraceLogger` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `check_sql_queries()` (e.g. with `test_ddl_drop_blocked()` and `test_ddl_insert_blocked()`) actually correct?**
  _`check_sql_queries()` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `load_prompt()` (e.g. with `_build_eval_system()` and `test_load_prompt_core()`) actually correct?**
  _`load_prompt()` has 15 INFERRED edges - model-reasoned connections that need verification._