# Graph Report - .  (2026-05-14)

## Corpus Check
- Corpus is ~11,328 words - fits in a single context window. You may not need a graph.

## Summary
- 934 nodes · 1554 edges · 78 communities (57 shown, 21 thin omitted)
- Extraction: 83% EXTRACTED · 17% INFERRED · 0% AMBIGUOUS · INFERRED: 267 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Trace & Test Generation|Trace & Test Generation]]
- [[_COMMUNITY_Agents MD Parsing + Prephase|Agents MD Parsing + Prephase]]
- [[_COMMUNITY_CC Client|CC Client]]
- [[_COMMUNITY_Security Gates|Security Gates]]
- [[_COMMUNITY_Orchestrator + BitGN Connect|Orchestrator + BitGN Connect]]
- [[_COMMUNITY_JSON Extract + Pipeline Refs|JSON Extract + Pipeline Refs]]
- [[_COMMUNITY_Evaluator|Evaluator]]
- [[_COMMUNITY_Resolve & Lookup|Resolve & Lookup]]
- [[_COMMUNITY_JSON Extraction Core|JSON Extraction Core]]
- [[_COMMUNITY_Propose Optimizations Tests|Propose Optimizations Tests]]
- [[_COMMUNITY_Contract & Answer Models|Contract & Answer Models]]
- [[_COMMUNITY_LLM Routing|LLM Routing]]
- [[_COMMUNITY_Schema Gate|Schema Gate]]
- [[_COMMUNITY_BitGN Harness Client|BitGN Harness Client]]
- [[_COMMUNITY_Pipeline Tests|Pipeline Tests]]
- [[_COMMUNITY_Pipeline Discovery|Pipeline Discovery]]
- [[_COMMUNITY_Prompt Builder|Prompt Builder]]
- [[_COMMUNITY_Pipeline Message Builder|Pipeline Message Builder]]
- [[_COMMUNITY_Tracer|Tracer]]
- [[_COMMUNITY_Pipeline TDD Tests|Pipeline TDD Tests]]
- [[_COMMUNITY_Rules Loader|Rules Loader]]
- [[_COMMUNITY_Agent Package Docs|Agent Package Docs]]
- [[_COMMUNITY_Pipeline Phase Docs|Pipeline Phase Docs]]
- [[_COMMUNITY_Proto & CLAUDE|Proto & CLAUDE.md]]
- [[_COMMUNITY_Build & LLM Docs|Build & LLM Docs]]
- [[_COMMUNITY_Models Cleanup Tests|Models Cleanup Tests]]
- [[_COMMUNITY_Scripts README|Scripts README]]
- [[_COMMUNITY_Orchestrator & Init|Orchestrator & Init]]
- [[_COMMUNITY_Test Runner|Test Runner]]
- [[_COMMUNITY_Answer & Grounding Docs|Answer & Grounding Docs]]
- [[_COMMUNITY_Data Prompts & Rules|Data Prompts & Rules]]
- [[_COMMUNITY_Eval Optimizations|Eval Optimizations]]
- [[_COMMUNITY_Architecture CLAUDE|Architecture CLAUDE.md]]
- [[_COMMUNITY_LLM Phase Calling|LLM Phase Calling]]
- [[_COMMUNITY_Trace Tests|Trace Tests]]
- [[_COMMUNITY_Agent Package CLAUDE|Agent Package CLAUDE.md]]
- [[_COMMUNITY_Knowledge Loader|Knowledge Loader]]
- [[_COMMUNITY_Clean Refs Task|Clean Refs Task]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]

## God Nodes (most connected - your core abstractions)
1. `run_pipeline()` - 48 edges
2. `TraceLogger` - 31 edges
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

## Communities (78 total, 21 thin omitted)

### Community 0 - "Trace & Test Generation"
Cohesion: 0.07
Nodes (36): _run_test_gen(), get_trace(), Thread-local structured JSONL trace logger for per-task pipeline traces., set_trace(), TraceLogger, _collect_trace_records(), _exec_ok(), _make_pre() (+28 more)

### Community 1 - "Agents MD Parsing + Prephase"
Cohesion: 0.06
Nodes (48): parse_agents_md(), Parse AGENTS.MD into {section_name: [lines]} for each ## section., _build_schema_digest(), _exec_sql_text(), _parse_csv_rows(), PrephaseResult, run_prephase(), test_empty_section_has_empty_lines() (+40 more)

### Community 2 - "CC Client"
Cohesion: 0.06
Nodes (45): _build_env(), cc_complete(), _parse_envelope(), Claude Code tier — spawn iclaude CLI as stateless LLM.  Bypasses applied (all re, Spawn iclaude once. Returns (stdout_lines, exit_code, fail_reason).     fail_rea, Stateless LLM call via iclaude subprocess.      Returns assistant text (JSON str, Extract result text and token usage from iclaude --output-format json.     Envel, _spawn_once() (+37 more)

### Community 3 - "Security Gates"
Cohesion: 0.06
Nodes (47): _get_security_gates(), check_grounding_refs(), check_learn_output(), check_path_access(), check_retry_loop(), check_sql_queries(), check_where_literals(), _has_where_clause() (+39 more)

### Community 4 - "Orchestrator + BitGN Connect"
Cohesion: 0.05
Nodes (14): Minimal orchestrator for ecom benchmark., Execute a single benchmark task., run_agent(), ConnectClient, Minimal Connect RPC client using JSON protocol over httpx., EcomRuntimeClientSync, _make_vm_mock(), run_agent calls run_pipeline for all tasks. (+6 more)

### Community 5 - "JSON Extract + Pipeline Refs"
Cohesion: 0.06
Nodes (45): _obj_mutation_tool(), Return the mutation tool name if obj is a write/delete/exec action, else None., _build_answer_user_msg(), _extract_sku_refs(), Extract /proc/catalog/{sku}.json paths from SQL results that contain a sku colum, Extract /proc/catalog/{sku}.json paths from SQL results that contain a sku colum, Extract catalogue paths from SQL results. Uses 'path' column when present,     f, Extract catalogue paths from SQL results. Uses 'path' column when present,     f (+37 more)

### Community 6 - "Evaluator"
Cohesion: 0.1
Nodes (31): _append_log(), _build_eval_system(), _compute_eval_metrics(), EvalInput, Post-execution pipeline evaluator. Fail-open: any exception returns None., Compute agents_md_coverage and schema_grounding. Returns dict with both floats., Compute agents_md_coverage and schema_grounding. Returns dict with both floats., Evaluate pipeline trace. Returns PipelineEvalOutput or None on any failure. (+23 more)

### Community 7 - "Resolve & Lookup"
Cohesion: 0.12
Nodes (34): _all_values(), _build_resolve_system(), _exec_sql(), _first_value(), Resolve phase: confirm task identifiers against DB before pipeline cycles., Deprecated shim — kept for test backward compat. Use _all_values., Resolve identifiers in task_text against DB. Returns confirmed_values or {} on f, Resolve identifiers in task_text against DB. Returns confirmed_values or {} on f (+26 more)

### Community 8 - "JSON Extraction Core"
Cohesion: 0.11
Nodes (32): _extract_json_from_text(), JSON extraction from free-form LLM text output.  Public API:   _obj_mutation_too, Try json5 parse; raises on failure (ImportError or parse error)., Lower tuple = preferred. Used by min() to break ties among same-tier candidates., Lower tuple = preferred. Used by min() to break ties among same-tier candidates., Extract the most actionable valid JSON object from free-form model output., Extract the most actionable valid JSON object from free-form model output., _richness_key() (+24 more)

### Community 9 - "Propose Optimizations Tests"
Cohesion: 0.17
Nodes (33): _base_patches(), _eval_entry(), Ensure propose_optimizations imports rules text from knowledge_loader, not its o, _cluster_recs returns fewer items when LLM merges duplicates., _cluster_recs returns items as-is when LLM call fails., All hashes in a cluster group are marked processed after writing the representat, Second rule synthesis receives updated rules_md after first write., Returns None when LLM says OK. (+25 more)

### Community 10 - "Contract & Answer Models"
Cohesion: 0.15
Nodes (28): Contract, ContractRound, EvaluatorResponse, ExecutorProposal, AnswerOutput, LearnOutput, PipelineEvalOutput, ResolveCandidate (+20 more)

### Community 11 - "LLM Routing"
Cohesion: 0.08
Nodes (26): _call_raw_single_model(), get_anthropic_model_id(), get_provider(), get_response_format(), _get_static_hint(), is_claude_code_model(), is_claude_model(), is_ollama_model() (+18 more)

### Community 12 - "Schema Gate"
Cohesion: 0.1
Nodes (29): _build_alias_map(), _check_query(), check_schema_compliance(), _known_cols_by_table(), Schema-aware SQL validator: unknown columns, unverified literals, double-key JOI, Check queries against schema. Returns first error string or None if all pass., Return {table_name_lower: {col_name_lower, ...}}., Return {alias_lower: table_name_lower} from FROM and JOIN clauses. (+21 more)

### Community 13 - "BitGN Harness Client"
Cohesion: 0.13
Nodes (16): HarnessServiceClientSync, _log_stats(), main(), _print_table_header(), _print_table_row(), Execute one benchmark trial., Execute one benchmark trial., Execute one benchmark trial. (+8 more)

### Community 14 - "Pipeline Tests"
Cohesion: 0.13
Nodes (27): _answer_json(), _make_exec_result(), _make_pre(), 3 cycles all fail → OUTCOME_NONE_CLARIFICATION without ANSWER LLM call., DDL query → security gate blocks → LEARN → retry → success., DDL query → security gate blocks → LEARN → retry → success., LEARN updates session_rules but does not write rule files (append_rule removed)., LEARN updates session_rules but does not write rule files (append_rule removed). (+19 more)

### Community 15 - "Pipeline Discovery"
Cohesion: 0.12
Nodes (23): _extract_discovery_results(), _format_confirmed_values(), Update confirmed_values in-place from DISTINCT query results., Update confirmed_values in-place from DISTINCT query results., Update confirmed_values in-place from DISTINCT query results., Update confirmed_values in-place from DISTINCT query results., LEARN sgr_trace entry must contain 'error_type' field., LEARN sgr_trace entry must contain 'error_type' field. (+15 more)

### Community 16 - "Prompt Builder"
Cohesion: 0.13
Nodes (21): build_system_prompt(), load_prompt(), System prompt builder — loads blocks from data/prompts/*.md., Return prompt block by file stem name. Returns '' if not found., Assemble system prompt from file-based blocks for the given task type., test_build_system_prompt_fallback_to_default_for_unknown(), test_build_system_prompt_lookup_contains_core_and_catalogue(), test_core_has_ecom_role() (+13 more)

### Community 17 - "Pipeline Message Builder"
Cohesion: 0.14
Nodes (20): _build_learn_user_msg(), _build_sql_user_msg(), _build_static_system(), _csv_has_data(), _exec_result_text(), _format_schema_digest(), _gates_summary(), Phase-based SQL pipeline for lookup tasks — replaces run_loop() for task_type='l (+12 more)

### Community 18 - "Tracer"
Cohesion: 0.12
Nodes (14): close_tracer(), get_task_tracer(), init_tracer(), Replay tracer for the agent loop (П3).  Writes JSONL event stream to logs/{ts}_{, Store task_id in thread-local so loop.py can access it without signature changes, Return a TaskTracer bound to task_id (falls back to thread-local if not given)., Flush and close the run-level tracer. Call at process exit., Append-only JSONL writer. Fail-open: errors in emit() never propagate. (+6 more)

### Community 19 - "Pipeline TDD Tests"
Cohesion: 0.29
Nodes (15): _answer_json(), _make_exec_result(), _make_pre(), sql_tests fail → LEARN + SQL_PLAN retry (_skip_sql=False) → sql_tests pass → ANS, answer_tests fail → LEARN + _skip_sql=True → next cycle skips SQL, retries ANSWE, TEST_GEN returns garbage → vm.answer(OUTCOME_NONE_CLARIFICATION), SQL never runs, TDD_ENABLED=0 → pipeline identical to current; run_tests never called., TDD_ENABLED=1 + all tests pass → OUTCOME_OK, vm.answer called once. (+7 more)

### Community 20 - "Rules Loader"
Cohesion: 0.22
Nodes (8): _get_rules_loader(), Load SQL planning rules from data/rules/ (one YAML file per rule)., RulesLoader, _make_rules_dir(), Create a rules directory with two individual rule files., test_empty_directory_returns_empty(), test_load_all_rules(), test_load_verified_rules_only()

### Community 21 - "Agent Package Docs"
Cohesion: 0.19
Nodes (13): AGENTS.MD vault rules, bitgn/, evaluator.py, main.py, orchestrator.py:run_agent(), prephase.py:run_prephase(), proto/, run_agent (+5 more)

### Community 22 - "Pipeline Phase Docs"
Cohesion: 0.24
Nodes (11): EXECUTE phase, json_extract.py, pipeline.py, pipeline execution phases, resolve.py:run_resolve(), run_pipeline, schema_gate.py:check_schema_compliance(), SQL_PLAN phase (+3 more)

### Community 23 - "Proto & CLAUDE.md"
Cohesion: 0.18
Nodes (9): `bitgn/harness.proto` — Benchmark lifecycle, `bitgn/vm/ecom/ecom.proto` — ECOM vault runtime (current), `bitgn/vm/pcm.proto` — PCM vault runtime (legacy), code:bash (# From project root (ecom1-agent/)), code:block2 (main.py), Parent project architecture (brief), Proto files, Regenerating stubs (+1 more)

### Community 24 - "Build & LLM Docs"
Cohesion: 0.22
Nodes (11): build_system_prompt, call_llm_raw, cc_client.py, data/prompts/*.md, data/security/*.yaml, llm.py:call_llm_raw(), LLM routing strategy, load_prompt(phase) (+3 more)

### Community 25 - "Models Cleanup Tests"
Cohesion: 0.24
Nodes (8): Test that all vault classes have been removed from models.py, Test that models.py contains exactly 7 BaseModel classes (4 pipeline + 2 resolve, Test that the 4 pipeline models are present in models.py, test_models_has_exactly_seven_classes(), test_models_has_exactly_six_classes(), test_pipeline_models_present(), test_test_gen_output_fields(), test_vault_models_removed()

### Community 26 - "Scripts README"
Cohesion: 0.2
Nodes (9): code:bash (cp .env.example .env        # добавить MODEL_EVALUATOR=anthr), code:bash (EVAL_ENABLED=1 uv run python main.py   # собрать eval_log), code:bash (uv run python scripts/propose_optimizations.py), code:bash (# Просмотреть предложенные правила), scripts/propose_optimizations.py, Запуск, Предварительные требования, Проверка и применение (+1 more)

### Community 27 - "Orchestrator & Init"
Cohesion: 0.2
Nodes (7): _write_dry_run(), dry_run=True: 2 vm.read calls, bin_sql_content populated., bin_sql content must NOT appear in LLM log messages., _write_dry_run writes correct JSON fields to jsonl., test_dry_run_bin_sql_not_in_log(), test_dry_run_reads_bin_sql(), test_write_dry_run_format()

### Community 28 - "Test Runner"
Cohesion: 0.29
Nodes (8): Subprocess test runner for TDD pipeline., Run test_code in isolated subprocess. Returns (passed, error_message)., run_tests(), test_answer_tests_signature(), test_failing_assert(), test_passing_assert(), test_syntax_error_in_test_code(), test_timeout()

### Community 29 - "Answer & Grounding Docs"
Cohesion: 0.22
Nodes (9): ANSWER phase, AnswerOutput, grounding_refs (AnswerOutput field), LEARN phase (_run_learn), LearnOutput, models.py Pydantic models, Answer.outcome values, PipelineEvalOutput (+1 more)

### Community 30 - "Data Prompts & Rules"
Cohesion: 0.29
Nodes (8): data/prompts/optimized/, data/rules/*.yaml, data/eval_log.jsonl, optimization output channels, scripts/propose_optimizations.py, rules_loader.py:RulesLoader, adding a new optimization channel, propose_optimizations script

### Community 31 - "Eval Optimizations"
Cohesion: 0.25
Nodes (6): .eval_optimizations_processed, Adding a New Channel, code:bash (# Preview what would be written (no files changed)), Commands, Deduplication, What This Script Does

### Community 32 - "Architecture CLAUDE.md"
Cohesion: 0.29
Nodes (5): Architecture, code:bash (uv sync                                          # install a), Commands, Key Data Files, Notable Constraints

### Community 33 - "LLM Phase Calling"
Cohesion: 0.29
Nodes (7): _call_llm_phase(), SGR LLM call: returns (parsed_output_or_None, sgr_trace_entry, tok_info)., SGR LLM call: returns (parsed_output_or_None, sgr_trace_entry, tok_info)., SGR LLM call: returns (parsed_output_or_None, sgr_trace_entry, tok_info)., _call_llm_phase returns (obj, sgr, tok) — tok has input/output keys., _call_llm_phase returns (obj, sgr, tok) — tok has input/output keys., test_call_llm_phase_returns_three_tuple()

### Community 35 - "Trace Tests"
Cohesion: 0.33
Nodes (5): Verify main.py creates/closes TraceLogger and calls log_header + log_task_result, main.log must contain stats rows but NOT pipeline cycle lines., After _run_single_task: .jsonl created, no .log file, log_header + log_task_resu, test_main_log_contains_only_stats(), test_run_single_task_creates_jsonl_and_removes_log()

### Community 37 - "Agent Package CLAUDE.md"
Cohesion: 0.33
Nodes (4): Agent Package Architecture, code:bash (uv sync                                          # install a), Commands, Notable Constraints

### Community 39 - "Clean Refs Task"
Cohesion: 0.6
Nodes (5): check_grounding_refs, clean_refs, p.path SQL column, sku_refs, t16 grounding refs bug

### Community 41 - "Community 41"
Cohesion: 0.5
Nodes (4): Evaluator thread starts even when all cycles fail., Evaluator thread starts even when all cycles fail., Evaluator thread starts even when all cycles fail., test_evaluator_thread_starts_on_failure()

### Community 42 - "Community 42"
Cohesion: 0.67
Nodes (3): _run_learn with error_type='llm_fail' must not add to session_rules., _run_learn with error_type='llm_fail' must not add to session_rules., test_learn_llm_fail_does_not_add_session_rule()

### Community 43 - "Community 43"
Cohesion: 0.67
Nodes (3): _build_static_system does not include IN-SESSION RULE (those go to user_msg)., _build_static_system does not include IN-SESSION RULE (those go to user_msg)., test_build_static_system_no_session_rules()

### Community 44 - "Community 44"
Cohesion: 0.67
Nodes (3): total_in_tok and total_out_tok are non-zero after successful pipeline run., total_in_tok and total_out_tok are non-zero after successful pipeline run., test_pipeline_token_counts_nonzero()

## Knowledge Gaps
- **277 isolated node(s):** `Tee stdout to logs/{ts}_{model}.log. ANSI codes are stripped in file.`, `Execute one benchmark trial.`, `Claude Code tier — spawn iclaude CLI as stateless LLM.  Bypasses applied (all re`, `Extract result text and token usage from iclaude --output-format json.     Envel`, `Spawn iclaude once. Returns (stdout_lines, exit_code, fail_reason).     fail_rea` (+272 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **21 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_pipeline()` connect `Pipeline Message Builder` to `Trace & Test Generation`, `LLM Phase Calling`, `Security Gates`, `Orchestrator + BitGN Connect`, `JSON Extract + Pipeline Refs`, `Resolve & Lookup`, `Community 41`, `Schema Gate`, `Community 44`, `Pipeline Tests`, `Pipeline Discovery`, `Pipeline TDD Tests`, `Rules Loader`, `Test Runner`?**
  _High betweenness centrality (0.241) - this node is a cross-community bridge._
- **Why does `run_agent()` connect `Orchestrator + BitGN Connect` to `Agents MD Parsing + Prephase`, `BitGN Harness Client`, `Pipeline Message Builder`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Why does `run_prephase()` connect `Agents MD Parsing + Prephase` to `Orchestrator + BitGN Connect`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `run_pipeline()` (e.g. with `run_agent()` and `test_happy_path()`) actually correct?**
  _`run_pipeline()` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `TraceLogger` (e.g. with `_run_single_task()` and `test_set_and_get_trace()`) actually correct?**
  _`TraceLogger` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `check_sql_queries()` (e.g. with `test_ddl_drop_blocked()` and `test_ddl_insert_blocked()`) actually correct?**
  _`check_sql_queries()` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `load_prompt()` (e.g. with `_build_eval_system()` and `test_load_prompt_core()`) actually correct?**
  _`load_prompt()` has 15 INFERRED edges - model-reasoned connections that need verification._