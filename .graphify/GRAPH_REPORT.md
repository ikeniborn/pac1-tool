# Graph Report - .  (2026-05-12)

## Corpus Check
- 0 files · ~0 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 339 nodes · 540 edges · 19 communities
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 85 edges (avg confidence: 0.78)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_LLM Dispatch & Routing|LLM Dispatch & Routing]]
- [[_COMMUNITY_Connect-RPC  BitGN Harness|Connect-RPC / BitGN Harness]]
- [[_COMMUNITY_Agent Orchestration|Agent Orchestration]]
- [[_COMMUNITY_Pydantic Models & Contracts|Pydantic Models & Contracts]]
- [[_COMMUNITY_Architecture & Config|Architecture & Config]]
- [[_COMMUNITY_Pipeline & SQL Execution|Pipeline & SQL Execution]]
- [[_COMMUNITY_Prompt Builder|Prompt Builder]]
- [[_COMMUNITY_SQL Security Gates|SQL Security Gates]]
- [[_COMMUNITY_Evaluator|Evaluator]]
- [[_COMMUNITY_Rules Loader|Rules Loader]]
- [[_COMMUNITY_CC Client|CC Client]]
- [[_COMMUNITY_BitGN Init Stubs|BitGN Init Stubs]]

## God Nodes (most connected - your core abstractions)
1. `load_prompt()` - 19 edges
2. `run_pipeline()` - 16 edges
3. `EcomRuntimeClientSync` - 16 edges
4. `check_sql_queries()` - 15 edges
5. `agent/CLAUDE.md` - 15 edges
6. `PcmRuntimeClientSync` - 14 edges
7. `run_prephase()` - 13 edges
8. `_call_llm()` - 12 edges
9. `HarnessServiceClientSync` - 12 edges
10. `RulesLoader` - 11 edges

## Surprising Connections (you probably didn't know these)
- `_run_single_task()` --calls--> `run_agent()`  [INFERRED]
  main.py → agent/orchestrator.py
- `SqlPlanOutput` --calls--> `test_sql_plan_output_valid()`  [INFERRED]
  agent/models.py → tests/test_pipeline_models.py
- `SqlPlanOutput` --calls--> `test_sql_plan_output_requires_reasoning()`  [INFERRED]
  agent/models.py → tests/test_pipeline_models.py
- `SqlPlanOutput` --calls--> `test_sql_plan_output_requires_queries()`  [INFERRED]
  agent/models.py → tests/test_pipeline_models.py
- `RulesLoader` --calls--> `test_empty_directory_returns_empty()`  [INFERRED]
  agent/rules_loader.py → tests/test_rules_loader.py

## Communities (19 total, 0 thin omitted)

### Community 0 - "LLM Dispatch & Routing"
Cohesion: 0.05
Nodes (51): call_llm_raw(), _call_raw_single_model(), dispatch(), get_anthropic_model_id(), get_provider(), get_response_format(), _get_static_hint(), is_claude_code_model() (+43 more)

### Community 1 - "Connect-RPC / BitGN Harness"
Cohesion: 0.07
Nodes (34): agent/CLAUDE.md, bitgn/ (generated stubs), BitGN benchmark harness, HarnessServiceClientSync, Connect-RPC, dispatch.py, DSPy optimization, main() (+26 more)

### Community 2 - "Agent Orchestration"
Cohesion: 0.08
Nodes (35): Minimal orchestrator for ecom benchmark., Execute a single benchmark task., No-op: wiki subsystem removed., run_agent(), _write_dry_run(), write_wiki_fragment(), PrephaseResult, run_prephase() (+27 more)

### Community 3 - "Pydantic Models & Contracts"
Cohesion: 0.09
Nodes (32): Contract, ContractRound, EvaluatorResponse, ExecutorProposal, AnswerOutput, EmailOutbox, LearnOutput, NextStep (+24 more)

### Community 4 - "Architecture & Config"
Cohesion: 0.06
Nodes (4): ConnectClient, Minimal Connect RPC client using JSON protocol over httpx., EcomRuntimeClientSync, PcmRuntimeClientSync

### Community 5 - "Pipeline & SQL Execution"
Cohesion: 0.15
Nodes (25): _build_system(), _call_llm_phase(), _csv_has_data(), _exec_result_text(), _gates_summary(), Phase-based SQL pipeline for lookup tasks — replaces run_loop() for task_type='l, Phase-based SQL pipeline. Returns stats dict compatible with run_loop()., Extract stdout/output text from an ExecResponse or test mock. (+17 more)

### Community 6 - "Prompt Builder"
Cohesion: 0.13
Nodes (23): check_path_access(), check_sql_queries(), _has_where_clause(), _is_select(), load_security_gates(), Security gate evaluation — gates loaded from data/security/*.yaml., Load all gate definitions from *.yaml files in directory, sorted by filename., Apply security gates to SQL queries. Returns error message or None if all pass. (+15 more)

### Community 7 - "SQL Security Gates"
Cohesion: 0.13
Nodes (21): build_system_prompt(), load_prompt(), System prompt builder — loads blocks from data/prompts/*.md., Return prompt block by file stem name. Returns '' if not found., Assemble system prompt from file-based blocks for the given task type., test_build_system_prompt_fallback_to_default_for_unknown(), test_build_system_prompt_lookup_contains_core_and_catalogue(), test_core_has_ecom_role() (+13 more)

### Community 8 - "Evaluator"
Cohesion: 0.2
Nodes (15): _append_log(), _build_eval_system(), EvalInput, Post-execution pipeline evaluator. Fail-open: any exception returns None., Evaluate pipeline trace. Returns PipelineEvalOutput or None on any failure., _run(), run_evaluator(), _make_eval_input() (+7 more)

### Community 9 - "Rules Loader"
Cohesion: 0.22
Nodes (9): Load and append SQL planning rules from data/rules/ (one YAML file per rule)., RulesLoader, _make_rules_dir(), Create a rules directory with two individual rule files., test_append_rule_creates_new_file(), test_append_rule_unique_id(), test_empty_directory_returns_empty(), test_load_all_rules() (+1 more)

### Community 10 - "CC Client"
Cohesion: 0.27
Nodes (8): _build_env(), cc_complete(), _parse_envelope(), Claude Code tier — spawn iclaude CLI as stateless LLM.  Bypasses applied (all re, Spawn iclaude once. Returns (stdout_lines, exit_code, fail_reason).     fail_rea, Stateless LLM call via iclaude subprocess.      Returns assistant text (JSON str, Extract result text and token usage from iclaude --output-format json.     Envel, _spawn_once()

### Community 11 - "BitGN Init Stubs"
Cohesion: 0.67
Nodes (3): _make_vm_mock(), run_agent with task_type=lookup calls run_pipeline, not run_loop., test_lookup_routes_to_pipeline()

## Knowledge Gaps
- **78 isolated node(s):** `Tee stdout to logs/{ts}_{model}.log. ANSI codes are stripped in file.`, `Execute one benchmark trial.`, `Claude Code tier — spawn iclaude CLI as stateless LLM.  Bypasses applied (all re`, `Extract result text and token usage from iclaude --output-format json.     Envel`, `Spawn iclaude once. Returns (stdout_lines, exit_code, fail_reason).     fail_rea` (+73 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_agent()` connect `Agent Orchestration` to `LLM Dispatch & Routing`, `Connect-RPC / BitGN Harness`, `Architecture & Config`, `Pipeline & SQL Execution`, `SQL Security Gates`, `BitGN Init Stubs`?**
  _High betweenness centrality (0.397) - this node is a cross-community bridge._
- **Why does `run_pipeline()` connect `Pipeline & SQL Execution` to `Rules Loader`, `Agent Orchestration`, `Prompt Builder`?**
  _High betweenness centrality (0.288) - this node is a cross-community bridge._
- **Why does `_run_single_task()` connect `Connect-RPC / BitGN Harness` to `Agent Orchestration`?**
  _High betweenness centrality (0.201) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `load_prompt()` (e.g. with `test_load_prompt_core()` and `test_load_prompt_lookup()`) actually correct?**
  _`load_prompt()` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `run_pipeline()` (e.g. with `run_agent()` and `test_happy_path()`) actually correct?**
  _`run_pipeline()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `EcomRuntimeClientSync` (e.g. with `PrephaseResult` and `run_agent()`) actually correct?**
  _`EcomRuntimeClientSync` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `check_sql_queries()` (e.g. with `test_ddl_drop_blocked()` and `test_ddl_insert_blocked()`) actually correct?**
  _`check_sql_queries()` has 10 INFERRED edges - model-reasoned connections that need verification._