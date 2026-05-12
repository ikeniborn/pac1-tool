# Graph Report - .  (2026-05-12)

## Corpus Check
- Corpus is ~14,995 words - fits in a single context window. You may not need a graph.

## Summary
- 353 nodes · 558 edges · 20 communities
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 85 edges (avg confidence: 0.78)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_LLM Dispatch & Routing|LLM Dispatch & Routing]]
- [[_COMMUNITY_BitGN Harness Integration|BitGN Harness Integration]]
- [[_COMMUNITY_Pydantic Models & Contracts|Pydantic Models & Contracts]]
- [[_COMMUNITY_Connect-RPC Client Layer|Connect-RPC Client Layer]]
- [[_COMMUNITY_Prephase & VM Bootstrap|Prephase & VM Bootstrap]]
- [[_COMMUNITY_SQL Pipeline State Machine|SQL Pipeline State Machine]]
- [[_COMMUNITY_SQL Security Gates|SQL Security Gates]]
- [[_COMMUNITY_Prompt Loader & Assembly|Prompt Loader & Assembly]]
- [[_COMMUNITY_Tracer & Logging|Tracer & Logging]]
- [[_COMMUNITY_Pipeline Evaluator|Pipeline Evaluator]]
- [[_COMMUNITY_Rules Loader (YAML)|Rules Loader (YAML)]]
- [[_COMMUNITY_Orchestrator Entry Point|Orchestrator Entry Point]]
- [[_COMMUNITY_CC Client (Claude Code)|CC Client (Claude Code)]]

## God Nodes (most connected - your core abstractions)
1. `load_prompt()` - 19 edges
2. `run_pipeline()` - 16 edges
3. `EcomRuntimeClientSync` - 16 edges
4. `check_sql_queries()` - 15 edges
5. `agent/CLAUDE.md` - 15 edges
6. `PcmRuntimeClientSync` - 14 edges
7. `run_prephase()` - 13 edges
8. `HarnessServiceClientSync` - 12 edges
9. `_call_llm()` - 11 edges
10. `RulesLoader` - 11 edges

## Surprising Connections (you probably didn't know these)
- `_run_single_task()` --calls--> `run_agent()`  [INFERRED]
  main.py → agent/orchestrator.py
- `test_sql_plan_output_valid()` --calls--> `SqlPlanOutput`  [INFERRED]
  tests/test_pipeline_models.py → agent/models.py
- `test_sql_plan_output_requires_reasoning()` --calls--> `SqlPlanOutput`  [INFERRED]
  tests/test_pipeline_models.py → agent/models.py
- `test_sql_plan_output_requires_queries()` --calls--> `SqlPlanOutput`  [INFERRED]
  tests/test_pipeline_models.py → agent/models.py
- `test_empty_directory_returns_empty()` --calls--> `RulesLoader`  [INFERRED]
  tests/test_rules_loader.py → agent/rules_loader.py

## Communities (20 total, 0 thin omitted)

### Community 0 - "LLM Dispatch & Routing"
Cohesion: 0.06
Nodes (46): call_llm_raw(), _call_raw_single_model(), dispatch(), get_anthropic_model_id(), get_provider(), get_response_format(), _get_static_hint(), is_claude_code_model() (+38 more)

### Community 1 - "BitGN Harness Integration"
Cohesion: 0.08
Nodes (33): agent/CLAUDE.md, bitgn/ (generated stubs), BitGN benchmark harness, HarnessServiceClientSync, Connect-RPC, dispatch.py, DSPy optimization, main() (+25 more)

### Community 2 - "Pydantic Models & Contracts"
Cohesion: 0.09
Nodes (32): Contract, ContractRound, EvaluatorResponse, ExecutorProposal, AnswerOutput, EmailOutbox, LearnOutput, NextStep (+24 more)

### Community 3 - "Connect-RPC Client Layer"
Cohesion: 0.06
Nodes (4): ConnectClient, Minimal Connect RPC client using JSON protocol over httpx., EcomRuntimeClientSync, PcmRuntimeClientSync

### Community 4 - "Prephase & VM Bootstrap"
Cohesion: 0.1
Nodes (29): PrephaseResult, run_prephase(), _make_vm(), PrephaseResult now has db_schema field., Normal mode (not dry_run) still calls vm.exec for schema., vm.exec exception → db_schema is empty string, no crash., db_schema content must NOT appear in LLM log messages., PrephaseResult has exactly the expected fields. (+21 more)

### Community 5 - "SQL Pipeline State Machine"
Cohesion: 0.16
Nodes (24): _build_system(), _call_llm_phase(), _csv_has_data(), _exec_result_text(), _gates_summary(), Phase-based SQL pipeline for lookup tasks — replaces run_loop() for task_type='l, Phase-based SQL pipeline. Returns stats dict compatible with run_loop()., Extract stdout/output text from an ExecResponse or test mock. (+16 more)

### Community 6 - "SQL Security Gates"
Cohesion: 0.13
Nodes (23): check_path_access(), check_sql_queries(), _has_where_clause(), _is_select(), load_security_gates(), Security gate evaluation — gates loaded from data/security/*.yaml., Load all gate definitions from *.yaml files in directory, sorted by filename., Apply security gates to SQL queries. Returns error message or None if all pass. (+15 more)

### Community 7 - "Prompt Loader & Assembly"
Cohesion: 0.13
Nodes (21): build_system_prompt(), load_prompt(), System prompt builder — loads blocks from data/prompts/*.md., Return prompt block by file stem name. Returns '' if not found., Assemble system prompt from file-based blocks for the given task type., test_build_system_prompt_fallback_to_default_for_unknown(), test_build_system_prompt_lookup_contains_core_and_catalogue(), test_core_has_ecom_role() (+13 more)

### Community 8 - "Tracer & Logging"
Cohesion: 0.12
Nodes (14): close_tracer(), get_task_tracer(), init_tracer(), Replay tracer for the agent loop (П3).  Writes JSONL event stream to logs/{ts}_{, Store task_id in thread-local so loop.py can access it without signature changes, Return a TaskTracer bound to task_id (falls back to thread-local if not given)., Flush and close the run-level tracer. Call at process exit., Append-only JSONL writer. Fail-open: errors in emit() never propagate. (+6 more)

### Community 9 - "Pipeline Evaluator"
Cohesion: 0.19
Nodes (16): _append_log(), _build_eval_system(), EvalInput, Post-execution pipeline evaluator. Fail-open: any exception returns None., Evaluate pipeline trace. Returns PipelineEvalOutput or None on any failure., _run(), run_evaluator(), _run_evaluator_safe() (+8 more)

### Community 10 - "Rules Loader (YAML)"
Cohesion: 0.22
Nodes (9): Load and append SQL planning rules from data/rules/ (one YAML file per rule)., RulesLoader, _make_rules_dir(), Create a rules directory with two individual rule files., test_append_rule_creates_new_file(), test_append_rule_unique_id(), test_empty_directory_returns_empty(), test_load_all_rules() (+1 more)

### Community 11 - "Orchestrator Entry Point"
Cohesion: 0.2
Nodes (9): Minimal orchestrator for ecom benchmark., Execute a single benchmark task., No-op: wiki subsystem removed., run_agent(), _write_dry_run(), write_wiki_fragment(), _make_vm_mock(), run_agent with task_type=lookup calls run_pipeline, not run_loop. (+1 more)

### Community 12 - "CC Client (Claude Code)"
Cohesion: 0.27
Nodes (8): _build_env(), cc_complete(), _parse_envelope(), Claude Code tier — spawn iclaude CLI as stateless LLM.  Bypasses applied (all re, Spawn iclaude once. Returns (stdout_lines, exit_code, fail_reason).     fail_rea, Stateless LLM call via iclaude subprocess.      Returns assistant text (JSON str, Extract result text and token usage from iclaude --output-format json.     Envel, _spawn_once()

## Knowledge Gaps
- **80 isolated node(s):** `Tee stdout to logs/{ts}_{model}.log. ANSI codes are stripped in file.`, `Execute one benchmark trial.`, `Claude Code tier — spawn iclaude CLI as stateless LLM.  Bypasses applied (all re`, `Extract result text and token usage from iclaude --output-format json.     Envel`, `Spawn iclaude once. Returns (stdout_lines, exit_code, fail_reason).     fail_rea` (+75 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_agent()` connect `Orchestrator Entry Point` to `LLM Dispatch & Routing`, `BitGN Harness Integration`, `Connect-RPC Client Layer`, `Prephase & VM Bootstrap`, `SQL Pipeline State Machine`, `Prompt Loader & Assembly`?**
  _High betweenness centrality (0.390) - this node is a cross-community bridge._
- **Why does `run_pipeline()` connect `SQL Pipeline State Machine` to `Pipeline Evaluator`, `Rules Loader (YAML)`, `Orchestrator Entry Point`, `SQL Security Gates`?**
  _High betweenness centrality (0.271) - this node is a cross-community bridge._
- **Why does `_run_single_task()` connect `BitGN Harness Integration` to `Orchestrator Entry Point`?**
  _High betweenness centrality (0.190) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `load_prompt()` (e.g. with `test_load_prompt_core()` and `test_load_prompt_lookup()`) actually correct?**
  _`load_prompt()` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `run_pipeline()` (e.g. with `run_agent()` and `test_happy_path()`) actually correct?**
  _`run_pipeline()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `EcomRuntimeClientSync` (e.g. with `PrephaseResult` and `ConnectClient`) actually correct?**
  _`EcomRuntimeClientSync` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `check_sql_queries()` (e.g. with `test_ddl_drop_blocked()` and `test_ddl_insert_blocked()`) actually correct?**
  _`check_sql_queries()` has 10 INFERRED edges - model-reasoned connections that need verification._