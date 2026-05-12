# Graph Report - .  (2026-05-12)

## Corpus Check
- 706 files · ~0 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 706 nodes · 1178 edges · 38 communities (32 shown, 6 thin omitted)
- Extraction: 83% EXTRACTED · 17% INFERRED · 0% AMBIGUOUS · INFERRED: 196 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Pipeline System Builder|Pipeline System Builder]]
- [[_COMMUNITY_Prephase & Schema|Prephase & Schema]]
- [[_COMMUNITY_Evaluator & Contract Models|Evaluator & Contract Models]]
- [[_COMMUNITY_Dispatch (Legacy)|Dispatch (Legacy)]]
- [[_COMMUNITY_CLAUDE.md Docs|CLAUDE.md Docs]]
- [[_COMMUNITY_SQL Security Gates|SQL Security Gates]]
- [[_COMMUNITY_LLM Routing|LLM Routing]]
- [[_COMMUNITY_BitGN Connect Layer|BitGN Connect Layer]]
- [[_COMMUNITY_Orchestrator|Orchestrator]]
- [[_COMMUNITY_Harness & Protobuf|Harness & Protobuf]]
- [[_COMMUNITY_Prompt Builder|Prompt Builder]]
- [[_COMMUNITY_Resolve Phase|Resolve Phase]]
- [[_COMMUNITY_LLM Raw Call|LLM Raw Call]]
- [[_COMMUNITY_Harness Client|Harness Client]]
- [[_COMMUNITY_Tracer|Tracer]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]

## God Nodes (most connected - your core abstractions)
1. `run_pipeline()` - 29 edges
2. `run_prephase()` - 22 edges
3. `check_sql_queries()` - 20 edges
4. `load_prompt()` - 19 edges
5. `main()` - 16 edges
6. `run_agent()` - 15 edges
7. `agent/CLAUDE.md` - 15 edges
8. `EcomRuntimeClientSync` - 14 edges
9. `check_schema_compliance()` - 14 edges
10. `_extract_json_from_text()` - 13 edges

## Surprising Connections (you probably didn't know these)
- `_run_single_task()` --calls--> `run_agent()`  [INFERRED]
  /home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/main.py → agent/orchestrator.py
- `call_llm_raw()` --calls--> `_run()`  [INFERRED]
  /home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/dispatch.py → agent/evaluator.py
- `call_llm_raw()` --calls--> `_call_llm_phase()`  [INFERRED]
  /home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/dispatch.py → agent/pipeline.py
- `dispatch()` --calls--> `run_loop()`  [INFERRED]
  /home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/dispatch.py → agent/loop.py
- `_extract_json_from_text()` --calls--> `_synthesize_security_gate()`  [INFERRED]
  agent/json_extract.py → scripts/propose_optimizations.py

## Communities (38 total, 6 thin omitted)

### Community 0 - "Pipeline System Builder"
Cohesion: 0.05
Nodes (76): _build_answer_user_msg(), _build_learn_user_msg(), _build_sql_user_msg(), _build_static_system(), _build_system(), _call_llm_phase(), _csv_has_data(), _exec_result_text() (+68 more)

### Community 1 - "Prephase & Schema"
Cohesion: 0.05
Nodes (65): _build_schema_digest(), _exec_sql_text(), _parse_csv_rows(), PrephaseResult, run_prephase(), _make_vm(), _make_vm_with_schema(), PrephaseResult now has db_schema field. (+57 more)

### Community 2 - "Evaluator & Contract Models"
Cohesion: 0.06
Nodes (52): Contract, ContractRound, EvaluatorResponse, ExecutorProposal, _compute_eval_metrics(), Compute agents_md_coverage and schema_grounding. Returns dict with both floats., AnswerOutput, EmailOutbox (+44 more)

### Community 3 - "Dispatch (Legacy)"
Cohesion: 0.06
Nodes (48): _call_raw_single_model(), dispatch(), get_anthropic_model_id(), get_provider(), get_response_format(), _get_static_hint(), is_claude_code_model(), is_claude_model() (+40 more)

### Community 4 - "CLAUDE.md Docs"
Cohesion: 0.05
Nodes (49): AGENTS.MD, bitgn/harness_connect.py:EndTrialRequest, build_system_prompt, call_llm_raw, .cache/capability_cache.json, data/prompts/*.md, data/prompts/optimized/, data/rules/*.yaml (+41 more)

### Community 5 - "SQL Security Gates"
Cohesion: 0.11
Nodes (35): check_path_access(), check_sql_queries(), _has_where_clause(), _is_select(), load_security_gates(), Security gate evaluation — gates loaded from data/security/*.yaml., Load all gate definitions from *.yaml files in directory, sorted by filename., Apply security gates to SQL queries. Returns error message or None if all pass. (+27 more)

### Community 6 - "LLM Routing"
Cohesion: 0.07
Nodes (30): _call_raw_single_model(), get_anthropic_model_id(), get_provider(), get_response_format(), _get_static_hint(), is_claude_code_model(), is_claude_model(), is_ollama_model() (+22 more)

### Community 7 - "BitGN Connect Layer"
Cohesion: 0.06
Nodes (4): ConnectClient, Minimal Connect RPC client using JSON protocol over httpx., EcomRuntimeClientSync, PcmRuntimeClientSync

### Community 8 - "Orchestrator"
Cohesion: 0.1
Nodes (19): Minimal orchestrator for ecom benchmark., Execute a single benchmark task., Execute a single benchmark task., Execute a single benchmark task., No-op: wiki subsystem removed., No-op: wiki subsystem removed., run_agent(), _write_dry_run() (+11 more)

### Community 9 - "Harness & Protobuf"
Cohesion: 0.14
Nodes (26): agent/CLAUDE.md, bitgn/ (generated stubs), BitGN benchmark harness, bitgn/harness_connect.py, Connect-RPC, dispatch.py, DSPy optimization, bitgn/vm/ecom/ecom.proto (+18 more)

### Community 10 - "Prompt Builder"
Cohesion: 0.13
Nodes (21): build_system_prompt(), load_prompt(), System prompt builder — loads blocks from data/prompts/*.md., Return prompt block by file stem name. Returns '' if not found., Assemble system prompt from file-based blocks for the given task type., test_build_system_prompt_fallback_to_default_for_unknown(), test_build_system_prompt_lookup_contains_core_and_catalogue(), test_core_has_ecom_role() (+13 more)

### Community 11 - "Resolve Phase"
Cohesion: 0.16
Nodes (23): _build_resolve_system(), _exec_sql(), _first_value(), Resolve phase: confirm task identifiers against DB before pipeline cycles., Resolve identifiers in task_text against DB. Returns confirmed_values or {} on f, _run(), run_resolve(), _security_check() (+15 more)

### Community 12 - "LLM Raw Call"
Cohesion: 0.22
Nodes (20): call_llm_raw(), Call LLM with MODEL_FALLBACK retry (FIX-417). Primary model through all tiers fi, call_llm_raw(), Call LLM with MODEL_FALLBACK retry (FIX-417). Primary model through all tiers fi, Call LLM with MODEL_FALLBACK retry (FIX-417). Primary model through all tiers fi, _entry_hash(), _existing_prompts_text(), _existing_rules_text() (+12 more)

### Community 13 - "Harness Client"
Cohesion: 0.14
Nodes (11): HarnessServiceClientSync, main(), _print_table_header(), _print_table_row(), Execute one benchmark trial., Execute one benchmark trial., Tee stdout to logs/{ts}_{model}.log. ANSI codes are stripped in file., _require_env() (+3 more)

### Community 14 - "Tracer"
Cohesion: 0.12
Nodes (14): close_tracer(), get_task_tracer(), init_tracer(), Replay tracer for the agent loop (П3).  Writes JSONL event stream to logs/{ts}_{, Store task_id in thread-local so loop.py can access it without signature changes, Return a TaskTracer bound to task_id (falls back to thread-local if not given)., Flush and close the run-level tracer. Call at process exit., Append-only JSONL writer. Fail-open: errors in emit() never propagate. (+6 more)

### Community 15 - "Community 15"
Cohesion: 0.19
Nodes (16): _append_log(), _build_eval_system(), EvalInput, Post-execution pipeline evaluator. Fail-open: any exception returns None., Evaluate pipeline trace. Returns PipelineEvalOutput or None on any failure., Evaluate pipeline trace. Returns PipelineEvalOutput or None on any failure., _run(), run_evaluator() (+8 more)

### Community 16 - "Community 16"
Cohesion: 0.37
Nodes (12): _base_patches(), _eval_entry(), _setup(), test_dedup_skips_processed(), test_dry_run_writes_nothing(), test_missing_model_evaluator_exits(), test_synthesize_prompt_patch_receives_existing_context(), test_synthesize_security_gate_receives_existing_context() (+4 more)

### Community 17 - "Community 17"
Cohesion: 0.21
Nodes (14): check_schema_compliance(), Schema-aware SQL validator: unknown columns, unverified literals, double-key JOI, Check queries against schema. Returns first error string or None if all pass., test_confirmed_literal_passes(), test_double_key_join_detected(), test_empty_digest_skips_column_check(), test_empty_queries_passes(), test_known_columns_pass() (+6 more)

### Community 18 - "Community 18"
Cohesion: 0.24
Nodes (7): Load SQL planning rules from data/rules/ (one YAML file per rule)., RulesLoader, _make_rules_dir(), Create a rules directory with two individual rule files., test_empty_directory_returns_empty(), test_load_all_rules(), test_load_verified_rules_only()

### Community 19 - "Community 19"
Cohesion: 0.31
Nodes (10): parse_agents_md(), Parse AGENTS.MD into {section_name: [lines]} for each ## section., test_empty_section_has_empty_lines(), test_empty_string_returns_empty_dict(), test_h1_heading_not_treated_as_section(), test_leading_content_before_first_section_ignored(), test_multiple_sections(), test_no_sections_returns_empty_dict() (+2 more)

### Community 20 - "Community 20"
Cohesion: 0.27
Nodes (8): _build_env(), cc_complete(), _parse_envelope(), Claude Code tier — spawn iclaude CLI as stateless LLM.  Bypasses applied (all re, Spawn iclaude once. Returns (stdout_lines, exit_code, fail_reason).     fail_rea, Stateless LLM call via iclaude subprocess.      Returns assistant text (JSON str, Extract result text and token usage from iclaude --output-format json.     Envel, _spawn_once()

### Community 21 - "Community 21"
Cohesion: 0.29
Nodes (7): Test that all vault classes have been removed from models.py, Test that models.py contains exactly 6 BaseModel classes (4 pipeline + 2 resolve, Test that the 4 pipeline models are present in models.py, test_models_has_exactly_four_classes(), test_models_has_exactly_six_classes(), test_pipeline_models_present(), test_vault_models_removed()

## Knowledge Gaps
- **193 isolated node(s):** `Tee stdout to logs/{ts}_{model}.log. ANSI codes are stripped in file.`, `Execute one benchmark trial.`, `Claude Code tier — spawn iclaude CLI as stateless LLM.  Bypasses applied (all re`, `Extract result text and token usage from iclaude --output-format json.     Envel`, `Spawn iclaude once. Returns (stdout_lines, exit_code, fail_reason).     fail_rea` (+188 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_pipeline()` connect `Pipeline System Builder` to `SQL Security Gates`, `Orchestrator`, `Resolve Phase`, `Community 17`, `Community 18`?**
  _High betweenness centrality (0.221) - this node is a cross-community bridge._
- **Why does `run_agent()` connect `Orchestrator` to `Pipeline System Builder`, `Prephase & Schema`, `Dispatch (Legacy)`, `BitGN Connect Layer`, `Prompt Builder`, `Harness Client`?**
  _High betweenness centrality (0.211) - this node is a cross-community bridge._
- **Why does `run_prephase()` connect `Prephase & Schema` to `Orchestrator`, `Community 19`?**
  _High betweenness centrality (0.155) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `run_pipeline()` (e.g. with `run_agent()` and `RulesLoader`) actually correct?**
  _`run_pipeline()` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `run_prephase()` (e.g. with `run_agent()` and `test_normal_mode_reads_only_agents_md()`) actually correct?**
  _`run_prephase()` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `check_sql_queries()` (e.g. with `test_ddl_drop_blocked()` and `test_ddl_insert_blocked()`) actually correct?**
  _`check_sql_queries()` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `load_prompt()` (e.g. with `_build_eval_system()` and `_build_system()`) actually correct?**
  _`load_prompt()` has 16 INFERRED edges - model-reasoned connections that need verification._