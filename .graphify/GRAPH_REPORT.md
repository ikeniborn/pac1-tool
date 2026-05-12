# Graph Report - .  (2026-05-12)

## Corpus Check
- 492 files · ~0 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 492 nodes · 802 edges · 34 communities (30 shown, 4 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 108 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_SQL Pipeline|SQL Pipeline]]
- [[_COMMUNITY_LLM Dispatch|LLM Dispatch]]
- [[_COMMUNITY_Protobuf Bindings|Protobuf Bindings]]
- [[_COMMUNITY_Test Suite|Test Suite]]
- [[_COMMUNITY_Security Gates|Security Gates]]
- [[_COMMUNITY_Prompt System|Prompt System]]
- [[_COMMUNITY_Eval & Optimization|Eval & Optimization]]
- [[_COMMUNITY_Prephase & Bootstrap|Prephase & Bootstrap]]
- [[_COMMUNITY_Orchestrator|Orchestrator]]
- [[_COMMUNITY_Contract Models|Contract Models]]
- [[_COMMUNITY_JSON Extraction|JSON Extraction]]
- [[_COMMUNITY_Rules Loader|Rules Loader]]
- [[_COMMUNITY_Harness Connect|Harness Connect]]
- [[_COMMUNITY_PCM Service|PCM Service]]
- [[_COMMUNITY_DSPy Training|DSPy Training]]
- [[_COMMUNITY_Task Registry|Task Registry]]
- [[_COMMUNITY_Model Registry|Model Registry]]
- [[_COMMUNITY_Pipeline Tests|Pipeline Tests]]
- [[_COMMUNITY_Script Utilities|Script Utilities]]
- [[_COMMUNITY_Loop Logic|Loop Logic]]
- [[_COMMUNITY_SQL Security Tests|SQL Security Tests]]
- [[_COMMUNITY_Prompt Loader Tests|Prompt Loader Tests]]
- [[_COMMUNITY_LLM Module Tests|LLM Module Tests]]

## God Nodes (most connected - your core abstractions)
1. `load_prompt()` - 19 edges
2. `run_pipeline()` - 17 edges
3. `check_sql_queries()` - 16 edges
4. `agent/CLAUDE.md` - 15 edges
5. `run_prephase()` - 14 edges
6. `EcomRuntimeClientSync` - 14 edges
7. `main()` - 14 edges
8. `_extract_json_from_text()` - 13 edges
9. `PcmRuntimeClientSync` - 13 edges
10. `run_agent()` - 12 edges

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
  agent/json_extract.py → /home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/.worktrees/eval-driven-rules/scripts/propose_optimizations.py

## Communities (34 total, 4 thin omitted)

### Community 0 - "SQL Pipeline"
Cohesion: 0.06
Nodes (48): _call_raw_single_model(), dispatch(), get_anthropic_model_id(), get_provider(), get_response_format(), _get_static_hint(), is_claude_code_model(), is_claude_model() (+40 more)

### Community 1 - "LLM Dispatch"
Cohesion: 0.08
Nodes (39): PrephaseResult, run_prephase(), _make_vm(), PrephaseResult now has db_schema field., prephase log must not contain the NextStep few-shot pair., Normal mode (not dry_run) still calls vm.exec for schema., vm.exec exception → db_schema is empty string, no crash., db_schema content must NOT appear in LLM log messages. (+31 more)

### Community 2 - "Protobuf Bindings"
Cohesion: 0.09
Nodes (32): Contract, ContractRound, EvaluatorResponse, ExecutorProposal, AnswerOutput, EmailOutbox, LearnOutput, NextStep (+24 more)

### Community 3 - "Test Suite"
Cohesion: 0.12
Nodes (32): _build_system(), _call_llm_phase(), _csv_has_data(), _exec_result_text(), _gates_summary(), Phase-based SQL pipeline for lookup tasks — replaces run_loop() for task_type='l, Phase-based SQL pipeline. Returns stats dict compatible with run_loop()., Extract stdout/output text from an ExecResponse or test mock. (+24 more)

### Community 4 - "Security Gates"
Cohesion: 0.07
Nodes (15): Minimal orchestrator for ecom benchmark., Execute a single benchmark task., Execute a single benchmark task., No-op: wiki subsystem removed., No-op: wiki subsystem removed., run_agent(), _write_dry_run(), write_wiki_fragment() (+7 more)

### Community 5 - "Prompt System"
Cohesion: 0.16
Nodes (25): check_path_access(), check_sql_queries(), _has_where_clause(), _is_select(), load_security_gates(), Security gate evaluation — gates loaded from data/security/*.yaml., Load all gate definitions from *.yaml files in directory, sorted by filename., Apply security gates to SQL queries. Returns error message or None if all pass. (+17 more)

### Community 6 - "Eval & Optimization"
Cohesion: 0.14
Nodes (26): agent/CLAUDE.md, bitgn/ (generated stubs), BitGN benchmark harness, bitgn/harness_connect.py, Connect-RPC, dispatch.py, DSPy optimization, bitgn/vm/ecom/ecom.proto (+18 more)

### Community 7 - "Prephase & Bootstrap"
Cohesion: 0.13
Nodes (21): build_system_prompt(), load_prompt(), System prompt builder — loads blocks from data/prompts/*.md., Return prompt block by file stem name. Returns '' if not found., Assemble system prompt from file-based blocks for the given task type., test_build_system_prompt_fallback_to_default_for_unknown(), test_build_system_prompt_lookup_contains_core_and_catalogue(), test_core_has_ecom_role() (+13 more)

### Community 8 - "Orchestrator"
Cohesion: 0.09
Nodes (22): bitgn/harness_connect.py:EndTrialRequest, .cache/capability_cache.json, dispatch.py:dispatch(), data/dspy_examples.jsonl, json_extract.py, JSON extraction priority order (7-level), LLM routing with provider prefix and capability probing, loop.py:run_loop() (+14 more)

### Community 9 - "Contract Models"
Cohesion: 0.13
Nodes (20): _call_raw_single_model(), get_anthropic_model_id(), get_provider(), get_response_format(), _get_static_hint(), is_claude_code_model(), is_claude_model(), is_ollama_model() (+12 more)

### Community 10 - "JSON Extraction"
Cohesion: 0.14
Nodes (11): HarnessServiceClientSync, main(), _print_table_header(), _print_table_row(), Execute one benchmark trial., Execute one benchmark trial., Tee stdout to logs/{ts}_{model}.log. ANSI codes are stripped in file., _require_env() (+3 more)

### Community 11 - "Rules Loader"
Cohesion: 0.1
Nodes (3): ConnectClient, Minimal Connect RPC client using JSON protocol over httpx., PcmRuntimeClientSync

### Community 12 - "Harness Connect"
Cohesion: 0.12
Nodes (14): close_tracer(), get_task_tracer(), init_tracer(), Replay tracer for the agent loop (П3).  Writes JSONL event stream to logs/{ts}_{, Store task_id in thread-local so loop.py can access it without signature changes, Return a TaskTracer bound to task_id (falls back to thread-local if not given)., Flush and close the run-level tracer. Call at process exit., Append-only JSONL writer. Fail-open: errors in emit() never propagate. (+6 more)

### Community 13 - "PCM Service"
Cohesion: 0.27
Nodes (17): call_llm_raw(), Call LLM with MODEL_FALLBACK retry (FIX-417). Primary model through all tiers fi, call_llm_raw(), Call LLM with MODEL_FALLBACK retry (FIX-417). Primary model through all tiers fi, _entry_hash(), _existing_rules_text(), _load_model_cfg(), _load_processed() (+9 more)

### Community 14 - "DSPy Training"
Cohesion: 0.21
Nodes (15): _append_log(), _build_eval_system(), EvalInput, Post-execution pipeline evaluator. Fail-open: any exception returns None., Evaluate pipeline trace. Returns PipelineEvalOutput or None on any failure., _run(), run_evaluator(), _make_eval_input() (+7 more)

### Community 15 - "Task Registry"
Cohesion: 0.24
Nodes (7): Load SQL planning rules from data/rules/ (one YAML file per rule)., RulesLoader, _make_rules_dir(), Create a rules directory with two individual rule files., test_empty_directory_returns_empty(), test_load_all_rules(), test_load_verified_rules_only()

### Community 16 - "Model Registry"
Cohesion: 0.65
Nodes (10): _base_patches(), _eval_entry(), _setup(), test_dedup_skips_processed(), test_dry_run_writes_nothing(), test_missing_model_evaluator_exits(), test_writes_prompt_md(), test_writes_rule_yaml() (+2 more)

### Community 17 - "Pipeline Tests"
Cohesion: 0.27
Nodes (8): _build_env(), cc_complete(), _parse_envelope(), Claude Code tier — spawn iclaude CLI as stateless LLM.  Bypasses applied (all re, Spawn iclaude once. Returns (stdout_lines, exit_code, fail_reason).     fail_rea, Stateless LLM call via iclaude subprocess.      Returns assistant text (JSON str, Extract result text and token usage from iclaude --output-format json.     Envel, _spawn_once()

### Community 18 - "Script Utilities"
Cohesion: 0.29
Nodes (6): Test that all vault classes have been removed from models.py, Test that models.py contains exactly 4 BaseModel classes, Test that the 4 pipeline models are present in models.py, test_models_has_exactly_four_classes(), test_pipeline_models_present(), test_vault_models_removed()

## Knowledge Gaps
- **130 isolated node(s):** `Tee stdout to logs/{ts}_{model}.log. ANSI codes are stripped in file.`, `Execute one benchmark trial.`, `Claude Code tier — spawn iclaude CLI as stateless LLM.  Bypasses applied (all re`, `Extract result text and token usage from iclaude --output-format json.     Envel`, `Spawn iclaude once. Returns (stdout_lines, exit_code, fail_reason).     fail_rea` (+125 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_agent()` connect `Security Gates` to `SQL Pipeline`, `LLM Dispatch`, `Test Suite`, `Prephase & Bootstrap`, `JSON Extraction`?**
  _High betweenness centrality (0.240) - this node is a cross-community bridge._
- **Why does `run_pipeline()` connect `Test Suite` to `Security Gates`, `Prompt System`, `Task Registry`?**
  _High betweenness centrality (0.194) - this node is a cross-community bridge._
- **Why does `run_prephase()` connect `LLM Dispatch` to `Security Gates`?**
  _High betweenness centrality (0.125) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `load_prompt()` (e.g. with `_build_eval_system()` and `_build_system()`) actually correct?**
  _`load_prompt()` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `run_pipeline()` (e.g. with `run_agent()` and `RulesLoader`) actually correct?**
  _`run_pipeline()` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `check_sql_queries()` (e.g. with `run_pipeline()` and `test_ddl_drop_blocked()`) actually correct?**
  _`check_sql_queries()` has 11 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Tee stdout to logs/{ts}_{model}.log. ANSI codes are stripped in file.`, `Execute one benchmark trial.`, `Claude Code tier — spawn iclaude CLI as stateless LLM.  Bypasses applied (all re` to the rest of the system?**
  _130 weakly-connected nodes found - possible documentation gaps or missing edges._