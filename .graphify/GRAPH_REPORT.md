# Graph Report - .  (2026-05-13)

## Corpus Check
- 694 files · ~0 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 694 nodes · 1086 edges · 59 communities (40 shown, 19 thin omitted)
- Extraction: 79% EXTRACTED · 21% INFERRED · 0% AMBIGUOUS · INFERRED: 223 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Pipeline Core|Pipeline Core]]
- [[_COMMUNITY_Agent Contracts & Services|Agent Contracts & Services]]
- [[_COMMUNITY_LLM Dispatch|LLM Dispatch]]
- [[_COMMUNITY_Contract Models|Contract Models]]
- [[_COMMUNITY_Prephase & Schema|Prephase & Schema]]
- [[_COMMUNITY_SQL Security Gates|SQL Security Gates]]
- [[_COMMUNITY_Connect RPC Client|Connect RPC Client]]
- [[_COMMUNITY_LLM Routing|LLM Routing]]
- [[_COMMUNITY_JSON Extraction|JSON Extraction]]
- [[_COMMUNITY_Trace Logging|Trace Logging]]
- [[_COMMUNITY_Schema Gate (sqlglot)|Schema Gate (sqlglot)]]
- [[_COMMUNITY_Prompt Builder|Prompt Builder]]
- [[_COMMUNITY_Resolve Phase|Resolve Phase]]
- [[_COMMUNITY_Harness Client|Harness Client]]
- [[_COMMUNITY_Task Tracer|Task Tracer]]
- [[_COMMUNITY_Trace Pipeline|Trace Pipeline]]
- [[_COMMUNITY_Evaluator|Evaluator]]
- [[_COMMUNITY_Optimization Tests|Optimization Tests]]
- [[_COMMUNITY_Orchestrator|Orchestrator]]
- [[_COMMUNITY_Rules Loader|Rules Loader]]
- [[_COMMUNITY_AGENTS.MD Parser|AGENTS.MD Parser]]
- [[_COMMUNITY_CC Client|CC Client]]
- [[_COMMUNITY_Scripts & Dry Run|Scripts & Dry Run]]
- [[_COMMUNITY_Singleton|Singleton]]
- [[_COMMUNITY_Singleton|Singleton]]
- [[_COMMUNITY_Singleton|Singleton]]
- [[_COMMUNITY_Singleton|Singleton]]
- [[_COMMUNITY_Singleton|Singleton]]
- [[_COMMUNITY_Singleton|Singleton]]
- [[_COMMUNITY_Singleton|Singleton]]
- [[_COMMUNITY_Singleton|Singleton]]
- [[_COMMUNITY_Singleton|Singleton]]
- [[_COMMUNITY_Singleton|Singleton]]
- [[_COMMUNITY_Singleton|Singleton]]
- [[_COMMUNITY_Singleton|Singleton]]
- [[_COMMUNITY_Singleton|Singleton]]
- [[_COMMUNITY_Singleton|Singleton]]
- [[_COMMUNITY_Singleton|Singleton]]
- [[_COMMUNITY_Singleton|Singleton]]
- [[_COMMUNITY_Singleton|Singleton]]
- [[_COMMUNITY_Singleton|Singleton]]
- [[_COMMUNITY_Singleton|Singleton]]
- [[_COMMUNITY_Singleton|Singleton]]
- [[_COMMUNITY_Singleton|Singleton]]

## God Nodes (most connected - your core abstractions)
1. `run_pipeline()` - 29 edges
2. `TraceLogger` - 27 edges
3. `load_prompt()` - 20 edges
4. `check_schema_compliance()` - 20 edges
5. `check_sql_queries()` - 19 edges
6. `run_prephase()` - 16 edges
7. `EcomRuntimeClientSync` - 15 edges
8. `main()` - 15 edges
9. `PcmRuntimeClientSync` - 14 edges
10. `HarnessServiceClientSync` - 12 edges

## Surprising Connections (you probably didn't know these)
- `_run_single_task()` --calls--> `TraceLogger`  [INFERRED]
  main.py → agent/trace.py
- `_run_single_task()` --calls--> `set_trace()`  [INFERRED]
  main.py → agent/trace.py
- `_run_single_task()` --calls--> `run_agent()`  [INFERRED]
  main.py → agent/orchestrator.py
- `_run_single_task()` --calls--> `get_trace()`  [INFERRED]
  main.py → agent/trace.py
- `dispatch()` --calls--> `run_loop()`  [INFERRED]
  /home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/dispatch.py → agent/loop.py

## Communities (59 total, 19 thin omitted)

### Community 0 - "Pipeline Core"
Cohesion: 0.06
Nodes (63): _build_answer_user_msg(), _build_learn_user_msg(), _build_sql_user_msg(), _build_static_system(), _csv_has_data(), _exec_result_text(), _extract_discovery_results(), _extract_sku_refs() (+55 more)

### Community 1 - "Agent Contracts & Services"
Cohesion: 0.05
Nodes (48): AGENTS.MD, AnswerOutput, bitgn/, build_system_prompt, call_llm_raw, cc_client.py, data/prompts/*.md, data/prompts/optimized/ (+40 more)

### Community 2 - "LLM Dispatch"
Cohesion: 0.07
Nodes (37): call_llm_raw(), _call_raw_single_model(), dispatch(), get_anthropic_model_id(), get_provider(), get_response_format(), _get_static_hint(), is_claude_code_model() (+29 more)

### Community 3 - "Contract Models"
Cohesion: 0.09
Nodes (36): Contract, ContractRound, EvaluatorResponse, ExecutorProposal, _compute_eval_metrics(), Compute agents_md_coverage and schema_grounding. Returns dict with both floats., AnswerOutput, LearnOutput (+28 more)

### Community 4 - "Prephase & Schema"
Cohesion: 0.08
Nodes (38): _build_schema_digest(), _exec_sql_text(), _parse_csv_rows(), PrephaseResult, run_prephase(), _make_vm(), _make_vm_with_schema(), PrephaseResult has agents_md_index and schema_digest fields. (+30 more)

### Community 5 - "SQL Security Gates"
Cohesion: 0.08
Nodes (36): _get_security_gates(), check_path_access(), check_sql_queries(), _has_where_clause(), _is_select(), load_security_gates(), Security gate evaluation — gates loaded from data/security/*.yaml., Load all gate definitions from *.yaml files in directory, sorted by filename. (+28 more)

### Community 6 - "Connect RPC Client"
Cohesion: 0.06
Nodes (4): ConnectClient, Minimal Connect RPC client using JSON protocol over httpx., EcomRuntimeClientSync, PcmRuntimeClientSync

### Community 7 - "LLM Routing"
Cohesion: 0.08
Nodes (26): _call_raw_single_model(), get_anthropic_model_id(), get_provider(), get_response_format(), _get_static_hint(), is_claude_code_model(), is_claude_model(), is_ollama_model() (+18 more)

### Community 8 - "JSON Extraction"
Cohesion: 0.1
Nodes (30): _extract_json_from_text(), _obj_mutation_tool(), JSON extraction from free-form LLM text output.  Public API:   _obj_mutation_too, Try json5 parse; raises on failure (ImportError or parse error)., Return the mutation tool name if obj is a write/delete/exec action, else None., Lower tuple = preferred. Used by min() to break ties among same-tier candidates., Extract the most actionable valid JSON object from free-form model output., _richness_key() (+22 more)

### Community 9 - "Trace Logging"
Cohesion: 0.13
Nodes (15): get_trace(), Thread-local structured JSONL trace logger for per-task pipeline traces., TraceLogger, _read_records(), test_gate_check_not_blocked(), test_gate_check_record(), test_get_trace_none_by_default(), test_header_record() (+7 more)

### Community 10 - "Schema Gate (sqlglot)"
Cohesion: 0.1
Nodes (29): _build_alias_map(), _check_query(), check_schema_compliance(), _known_cols_by_table(), Schema-aware SQL validator: unknown columns, unverified literals, double-key JOI, Check queries against schema. Returns first error string or None if all pass., Return {table_name_lower: {col_name_lower, ...}}., Return {alias_lower: table_name_lower} from FROM and JOIN clauses. (+21 more)

### Community 11 - "Prompt Builder"
Cohesion: 0.13
Nodes (21): build_system_prompt(), load_prompt(), System prompt builder — loads blocks from data/prompts/*.md., Return prompt block by file stem name. Returns '' if not found., Assemble system prompt from file-based blocks for the given task type., test_build_system_prompt_fallback_to_default_for_unknown(), test_build_system_prompt_lookup_contains_core_and_catalogue(), test_core_has_ecom_role() (+13 more)

### Community 12 - "Resolve Phase"
Cohesion: 0.16
Nodes (23): _build_resolve_system(), _exec_sql(), _first_value(), Resolve phase: confirm task identifiers against DB before pipeline cycles., Resolve identifiers in task_text against DB. Returns confirmed_values or {} on f, _run(), run_resolve(), _security_check() (+15 more)

### Community 13 - "Harness Client"
Cohesion: 0.15
Nodes (12): HarnessServiceClientSync, main(), _print_table_header(), _print_table_row(), Execute one benchmark trial., Execute one benchmark trial., Execute one benchmark trial., Tee stdout to logs/{ts}_{model}.log. ANSI codes are stripped in file. (+4 more)

### Community 14 - "Task Tracer"
Cohesion: 0.12
Nodes (14): close_tracer(), get_task_tracer(), init_tracer(), Replay tracer for the agent loop (П3).  Writes JSONL event stream to logs/{ts}_{, Store task_id in thread-local so loop.py can access it without signature changes, Return a TaskTracer bound to task_id (falls back to thread-local if not given)., Flush and close the run-level tracer. Call at process exit., Append-only JSONL writer. Fail-open: errors in emit() never propagate. (+6 more)

### Community 15 - "Trace Pipeline"
Cohesion: 0.19
Nodes (16): set_trace(), _collect_trace_records(), _exec_ok(), _make_pre(), Verify pipeline instruments TraceLogger at all required points., sql_validate + sql_execute records written on successful cycle., Happy path: sql_plan + answer llm_call records written., gate_check records for security + schema gates written every cycle. (+8 more)

### Community 16 - "Evaluator"
Cohesion: 0.19
Nodes (16): _append_log(), _build_eval_system(), EvalInput, Post-execution pipeline evaluator. Fail-open: any exception returns None., Evaluate pipeline trace. Returns PipelineEvalOutput or None on any failure., _run(), run_evaluator(), _run_evaluator_safe() (+8 more)

### Community 17 - "Optimization Tests"
Cohesion: 0.35
Nodes (12): _base_patches(), _eval_entry(), _setup(), test_dedup_skips_processed(), test_dry_run_writes_nothing(), test_missing_model_evaluator_exits(), test_synthesize_prompt_patch_receives_existing_context(), test_synthesize_security_gate_receives_existing_context() (+4 more)

### Community 18 - "Orchestrator"
Cohesion: 0.18
Nodes (10): Minimal orchestrator for ecom benchmark., Execute a single benchmark task., run_agent(), _make_vm_mock(), run_agent calls run_pipeline for all tasks., run_agent() result must not contain builder_*/contract_*/eval_rejection_count fi, run_agent() always returns a plain dict (public API unchanged)., test_lookup_routes_to_pipeline() (+2 more)

### Community 19 - "Rules Loader"
Cohesion: 0.22
Nodes (8): _get_rules_loader(), Load SQL planning rules from data/rules/ (one YAML file per rule)., RulesLoader, _make_rules_dir(), Create a rules directory with two individual rule files., test_empty_directory_returns_empty(), test_load_all_rules(), test_load_verified_rules_only()

### Community 20 - "AGENTS.MD Parser"
Cohesion: 0.27
Nodes (10): parse_agents_md(), Parse AGENTS.MD into {section_name: [lines]} for each ## section., test_empty_section_has_empty_lines(), test_empty_string_returns_empty_dict(), test_h1_heading_not_treated_as_section(), test_leading_content_before_first_section_ignored(), test_multiple_sections(), test_no_sections_returns_empty_dict() (+2 more)

### Community 21 - "CC Client"
Cohesion: 0.27
Nodes (8): _build_env(), cc_complete(), _parse_envelope(), Claude Code tier — spawn iclaude CLI as stateless LLM.  Bypasses applied (all re, Spawn iclaude once. Returns (stdout_lines, exit_code, fail_reason).     fail_rea, Stateless LLM call via iclaude subprocess.      Returns assistant text (JSON str, Extract result text and token usage from iclaude --output-format json.     Envel, _spawn_once()

### Community 22 - "Scripts & Dry Run"
Cohesion: 0.2
Nodes (7): _write_dry_run(), dry_run=True: 2 vm.read calls, bin_sql_content populated., bin_sql content must NOT appear in LLM log messages., _write_dry_run writes correct JSON fields to jsonl., test_dry_run_bin_sql_not_in_log(), test_dry_run_reads_bin_sql(), test_write_dry_run_format()

### Community 23 - "Singleton"
Cohesion: 0.29
Nodes (6): Test that all vault classes have been removed from models.py, Test that models.py contains exactly 6 BaseModel classes (4 pipeline + 2 resolve, Test that the 4 pipeline models are present in models.py, test_models_has_exactly_six_classes(), test_pipeline_models_present(), test_vault_models_removed()

### Community 25 - "Singleton"
Cohesion: 0.5
Nodes (3): Verify main.py creates/closes TraceLogger and calls log_header + log_task_result, After _run_single_task: .jsonl created, no .log file, log_header + log_task_resu, test_run_single_task_creates_jsonl_and_removes_log()

## Knowledge Gaps
- **178 isolated node(s):** `Tee stdout to logs/{ts}_{model}.log. ANSI codes are stripped in file.`, `Execute one benchmark trial.`, `Claude Code tier — spawn iclaude CLI as stateless LLM.  Bypasses applied (all re`, `Extract result text and token usage from iclaude --output-format json.     Envel`, `Spawn iclaude once. Returns (stdout_lines, exit_code, fail_reason).     fail_rea` (+173 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_pipeline()` connect `Pipeline Core` to `SQL Security Gates`, `JSON Extraction`, `Trace Logging`, `Schema Gate (sqlglot)`, `Resolve Phase`, `Trace Pipeline`, `Orchestrator`, `Rules Loader`?**
  _High betweenness centrality (0.216) - this node is a cross-community bridge._
- **Why does `run_agent()` connect `Orchestrator` to `Pipeline Core`, `Prephase & Schema`, `Harness Client`, `Connect RPC Client`?**
  _High betweenness centrality (0.136) - this node is a cross-community bridge._
- **Why does `run_prephase()` connect `Prephase & Schema` to `Orchestrator`, `AGENTS.MD Parser`?**
  _High betweenness centrality (0.104) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `run_pipeline()` (e.g. with `run_agent()` and `test_happy_path()`) actually correct?**
  _`run_pipeline()` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `TraceLogger` (e.g. with `_run_single_task()` and `test_set_and_get_trace()`) actually correct?**
  _`TraceLogger` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `load_prompt()` (e.g. with `test_load_prompt_core()` and `test_load_prompt_lookup()`) actually correct?**
  _`load_prompt()` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `check_schema_compliance()` (e.g. with `test_valid_query_passes()` and `test_unknown_column_detected()`) actually correct?**
  _`check_schema_compliance()` has 16 INFERRED edges - model-reasoned connections that need verification._