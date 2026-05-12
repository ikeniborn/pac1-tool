# Graph Report - .  (2026-05-12)

## Corpus Check
- Corpus is ~16,513 words - fits in a single context window. You may not need a graph.

## Summary
- 382 nodes · 607 edges · 24 communities
- Extraction: 83% EXTRACTED · 17% INFERRED · 0% AMBIGUOUS · INFERRED: 101 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_LLM Dispatch Layer|LLM Dispatch Layer]]
- [[_COMMUNITY_Contract & Eval Models|Contract & Eval Models]]
- [[_COMMUNITY_Prephase & Context Build|Prephase & Context Build]]
- [[_COMMUNITY_SQL Pipeline Execution|SQL Pipeline Execution]]
- [[_COMMUNITY_Orchestrator & Loop|Orchestrator & Loop]]
- [[_COMMUNITY_SQL Security Gates|SQL Security Gates]]
- [[_COMMUNITY_JSON Extraction & Raw LLM|JSON Extraction & Raw LLM]]
- [[_COMMUNITY_Harness & Bitgn Core|Harness & Bitgn Core]]
- [[_COMMUNITY_Prompt Loading & System Build|Prompt Loading & System Build]]
- [[_COMMUNITY_Connect RPC Client|Connect RPC Client]]
- [[_COMMUNITY_Tracer & Logging|Tracer & Logging]]
- [[_COMMUNITY_Harness gRPC Stubs|Harness gRPC Stubs]]
- [[_COMMUNITY_Evaluator & Eval Log|Evaluator & Eval Log]]
- [[_COMMUNITY_Rules Loader|Rules Loader]]
- [[_COMMUNITY_Propose Optimizations Tests|Propose Optimizations Tests]]
- [[_COMMUNITY_CC Client|CC Client]]

## God Nodes (most connected - your core abstractions)
1. `load_prompt()` - 19 edges
2. `run_pipeline()` - 17 edges
3. `check_sql_queries()` - 15 edges
4. `agent/CLAUDE.md` - 15 edges
5. `EcomRuntimeClientSync` - 14 edges
6. `run_prephase()` - 13 edges
7. `PcmRuntimeClientSync` - 13 edges
8. `main()` - 13 edges
9. `_extract_json_from_text()` - 11 edges
10. `_call_llm()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `_run()` --calls--> `call_llm_raw()`  [INFERRED]
  agent/evaluator.py → /home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/dispatch.py
- `_call_llm_phase()` --calls--> `call_llm_raw()`  [INFERRED]
  agent/pipeline.py → /home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/dispatch.py
- `run_loop()` --calls--> `dispatch()`  [INFERRED]
  agent/loop.py → /home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/dispatch.py
- `_call_openai_tier()` --calls--> `_extract_json_from_text()`  [INFERRED]
  agent/loop.py → /home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/json_extract.py
- `_call_llm()` --calls--> `_extract_json_from_text()`  [INFERRED]
  agent/loop.py → /home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/json_extract.py

## Communities (24 total, 0 thin omitted)

### Community 0 - "LLM Dispatch Layer"
Cohesion: 0.08
Nodes (35): _call_raw_single_model(), dispatch(), get_anthropic_model_id(), get_provider(), get_response_format(), _get_static_hint(), is_claude_code_model(), is_claude_model() (+27 more)

### Community 1 - "Contract & Eval Models"
Cohesion: 0.09
Nodes (32): Contract, ContractRound, EvaluatorResponse, ExecutorProposal, AnswerOutput, EmailOutbox, LearnOutput, NextStep (+24 more)

### Community 2 - "Prephase & Context Build"
Cohesion: 0.11
Nodes (27): PrephaseResult, run_prephase(), _make_vm(), PrephaseResult now has db_schema field., Normal mode (not dry_run) still calls vm.exec for schema., vm.exec exception → db_schema is empty string, no crash., db_schema content must NOT appear in LLM log messages., PrephaseResult has exactly the expected fields. (+19 more)

### Community 3 - "SQL Pipeline Execution"
Cohesion: 0.15
Nodes (27): _build_system(), _call_llm_phase(), _csv_has_data(), _exec_result_text(), _gates_summary(), Phase-based SQL pipeline for lookup tasks — replaces run_loop() for task_type='l, Phase-based SQL pipeline. Returns stats dict compatible with run_loop()., Extract stdout/output text from an ExecResponse or test mock. (+19 more)

### Community 4 - "Orchestrator & Loop"
Cohesion: 0.08
Nodes (12): Minimal orchestrator for ecom benchmark., Execute a single benchmark task., No-op: wiki subsystem removed., run_agent(), _write_dry_run(), write_wiki_fragment(), EcomRuntimeClientSync, _make_vm_mock() (+4 more)

### Community 5 - "SQL Security Gates"
Cohesion: 0.12
Nodes (25): check_path_access(), check_sql_queries(), _has_where_clause(), _is_select(), load_security_gates(), Security gate evaluation — gates loaded from data/security/*.yaml., Load all gate definitions from *.yaml files in directory, sorted by filename., Apply security gates to SQL queries. Returns error message or None if all pass. (+17 more)

### Community 6 - "JSON Extraction & Raw LLM"
Cohesion: 0.13
Nodes (24): call_llm_raw(), Call LLM with MODEL_FALLBACK retry (FIX-417). Primary model through all tiers fi, _extract_json_from_text(), _obj_mutation_tool(), JSON extraction from free-form LLM text output.  Extracted from loop.py to reduc, Try json5 parse; raises on failure (ImportError or parse error)., Return the mutation tool name if obj is a write/delete/move/mkdir action, else N, Lower tuple = preferred. Used by min() to break ties when multiple candidates sh (+16 more)

### Community 7 - "Harness & Bitgn Core"
Cohesion: 0.14
Nodes (26): agent/CLAUDE.md, bitgn/ (generated stubs), BitGN benchmark harness, bitgn/harness_connect.py, Connect-RPC, dispatch.py, DSPy optimization, bitgn/vm/ecom/ecom.proto (+18 more)

### Community 8 - "Prompt Loading & System Build"
Cohesion: 0.13
Nodes (21): build_system_prompt(), load_prompt(), System prompt builder — loads blocks from data/prompts/*.md., Return prompt block by file stem name. Returns '' if not found., Assemble system prompt from file-based blocks for the given task type., test_build_system_prompt_fallback_to_default_for_unknown(), test_build_system_prompt_lookup_contains_core_and_catalogue(), test_core_has_ecom_role() (+13 more)

### Community 9 - "Connect RPC Client"
Cohesion: 0.1
Nodes (3): ConnectClient, Minimal Connect RPC client using JSON protocol over httpx., PcmRuntimeClientSync

### Community 10 - "Tracer & Logging"
Cohesion: 0.12
Nodes (14): close_tracer(), get_task_tracer(), init_tracer(), Replay tracer for the agent loop (П3).  Writes JSONL event stream to logs/{ts}_{, Store task_id in thread-local so loop.py can access it without signature changes, Return a TaskTracer bound to task_id (falls back to thread-local if not given)., Flush and close the run-level tracer. Call at process exit., Append-only JSONL writer. Fail-open: errors in emit() never propagate. (+6 more)

### Community 11 - "Harness gRPC Stubs"
Cohesion: 0.13
Nodes (9): HarnessServiceClientSync, main(), _print_table_header(), _print_table_row(), Execute one benchmark trial., Tee stdout to logs/{ts}_{model}.log. ANSI codes are stripped in file., _run_single_task(), _setup_log_tee() (+1 more)

### Community 12 - "Evaluator & Eval Log"
Cohesion: 0.2
Nodes (15): _append_log(), _build_eval_system(), EvalInput, Post-execution pipeline evaluator. Fail-open: any exception returns None., Evaluate pipeline trace. Returns PipelineEvalOutput or None on any failure., _run(), run_evaluator(), _make_eval_input() (+7 more)

### Community 13 - "Rules Loader"
Cohesion: 0.24
Nodes (7): Load SQL planning rules from data/rules/ (one YAML file per rule)., RulesLoader, _make_rules_dir(), Create a rules directory with two individual rule files., test_empty_directory_returns_empty(), test_load_all_rules(), test_load_verified_rules_only()

### Community 14 - "Propose Optimizations Tests"
Cohesion: 0.6
Nodes (10): _base_patches(), _eval_entry(), _setup(), test_dedup_skips_processed(), test_dry_run_writes_nothing(), test_missing_model_evaluator_exits(), test_writes_prompt_md(), test_writes_rule_yaml() (+2 more)

### Community 15 - "CC Client"
Cohesion: 0.27
Nodes (8): _build_env(), cc_complete(), _parse_envelope(), Claude Code tier — spawn iclaude CLI as stateless LLM.  Bypasses applied (all re, Spawn iclaude once. Returns (stdout_lines, exit_code, fail_reason).     fail_rea, Stateless LLM call via iclaude subprocess.      Returns assistant text (JSON str, Extract result text and token usage from iclaude --output-format json.     Envel, _spawn_once()

## Knowledge Gaps
- **82 isolated node(s):** `Tee stdout to logs/{ts}_{model}.log. ANSI codes are stripped in file.`, `Execute one benchmark trial.`, `Claude Code tier — spawn iclaude CLI as stateless LLM.  Bypasses applied (all re`, `Extract result text and token usage from iclaude --output-format json.     Envel`, `Spawn iclaude once. Returns (stdout_lines, exit_code, fail_reason).     fail_rea` (+77 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_agent()` connect `Orchestrator & Loop` to `LLM Dispatch Layer`, `Prephase & Context Build`, `SQL Pipeline Execution`, `Prompt Loading & System Build`, `Harness gRPC Stubs`?**
  _High betweenness centrality (0.316) - this node is a cross-community bridge._
- **Why does `run_pipeline()` connect `SQL Pipeline Execution` to `SQL Security Gates`, `Orchestrator & Loop`, `Rules Loader`?**
  _High betweenness centrality (0.246) - this node is a cross-community bridge._
- **Why does `EcomRuntimeClientSync` connect `Orchestrator & Loop` to `Connect RPC Client`?**
  _High betweenness centrality (0.124) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `load_prompt()` (e.g. with `_build_eval_system()` and `_build_system()`) actually correct?**
  _`load_prompt()` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `run_pipeline()` (e.g. with `run_agent()` and `test_happy_path()`) actually correct?**
  _`run_pipeline()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `check_sql_queries()` (e.g. with `test_ddl_drop_blocked()` and `test_ddl_insert_blocked()`) actually correct?**
  _`check_sql_queries()` has 10 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Tee stdout to logs/{ts}_{model}.log. ANSI codes are stripped in file.`, `Execute one benchmark trial.`, `Claude Code tier — spawn iclaude CLI as stateless LLM.  Bypasses applied (all re` to the rest of the system?**
  _82 weakly-connected nodes found - possible documentation gaps or missing edges._