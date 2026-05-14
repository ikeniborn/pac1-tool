# Graph Report - .  (2026-05-14)

## Corpus Check
- 0 files · ~0 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 864 nodes · 1399 edges · 42 communities (37 shown, 5 thin omitted)
- Extraction: 79% EXTRACTED · 21% INFERRED · 0% AMBIGUOUS · INFERRED: 287 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Optimization Proposal Tests|Optimization Proposal Tests]]
- [[_COMMUNITY_Task Evaluator|Task Evaluator]]
- [[_COMMUNITY_Pre-Phase & Agents Config|Pre-Phase & Agents Config]]
- [[_COMMUNITY_Trace Logger|Trace Logger]]
- [[_COMMUNITY_Contract Models|Contract Models]]
- [[_COMMUNITY_Optimization Pipeline|Optimization Pipeline]]
- [[_COMMUNITY_LLM Routing Layer|LLM Routing Layer]]
- [[_COMMUNITY_SQL Security Gates|SQL Security Gates]]
- [[_COMMUNITY_JSON Extraction & Answer|JSON Extraction & Answer]]
- [[_COMMUNITY_Agent Orchestrator|Agent Orchestrator]]
- [[_COMMUNITY_System Prompt Assembly|System Prompt Assembly]]
- [[_COMMUNITY_BitGN Connect Client|BitGN Connect Client]]
- [[_COMMUNITY_Schema Gate|Schema Gate]]
- [[_COMMUNITY_Value Resolver|Value Resolver]]
- [[_COMMUNITY_Claude Prompt Builder|Claude Prompt Builder]]
- [[_COMMUNITY_Pipeline Tests|Pipeline Tests]]
- [[_COMMUNITY_Agent Configuration|Agent Configuration]]
- [[_COMMUNITY_Prompt Loader|Prompt Loader]]
- [[_COMMUNITY_Discovery Pipeline|Discovery Pipeline]]
- [[_COMMUNITY_Pipeline Message Builder|Pipeline Message Builder]]
- [[_COMMUNITY_TDD Pipeline Tests|TDD Pipeline Tests]]
- [[_COMMUNITY_Claude Code Client|Claude Code Client]]
- [[_COMMUNITY_Test Runner|Test Runner]]
- [[_COMMUNITY_Eval Optimization Docs|Eval Optimization Docs]]
- [[_COMMUNITY_Trace Tests|Trace Tests]]
- [[_COMMUNITY_Knowledge Loader|Knowledge Loader]]
- [[_COMMUNITY_Task Definitions|Task Definitions]]
- [[_COMMUNITY_Test Fixtures|Test Fixtures]]
- [[_COMMUNITY_BitGN Proto Docs|BitGN Proto Docs]]
- [[_COMMUNITY_Claude Docs|Claude Docs]]
- [[_COMMUNITY_Models Config|Models Config]]

## God Nodes (most connected - your core abstractions)
1. `run_pipeline()` - 45 edges
2. `main` - 36 edges
3. `TraceLogger` - 31 edges
4. `load_prompt()` - 21 edges
5. `check_schema_compliance()` - 21 edges
6. `check_sql_queries()` - 19 edges
7. `_write_eval_log()` - 19 edges
8. `_eval_entry()` - 19 edges
9. `_setup()` - 19 edges
10. `run_prephase()` - 18 edges

## Surprising Connections (you probably didn't know these)
- `_run_learn()` --calls--> `make_json_hash()`  [INFERRED]
  agent/pipeline.py → /home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/sql_security.py
- `get_trace()` --calls--> `test_get_trace_none_by_default()`  [INFERRED]
  agent/trace.py → tests/test_trace.py
- `_run_single_task()` --calls--> `TraceLogger`  [INFERRED]
  /home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/main.py → agent/trace.py
- `_run_single_task()` --calls--> `set_trace()`  [INFERRED]
  /home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/main.py → agent/trace.py
- `_run_single_task()` --calls--> `get_trace()`  [INFERRED]
  /home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/main.py → agent/trace.py

## Communities (42 total, 5 thin omitted)

### Community 0 - "Optimization Proposal Tests"
Cohesion: 0.08
Nodes (51): _base_patches(), _eval_entry(), _make_harness_mocks(), Ensure propose_optimizations imports rules text from knowledge_loader, not its o, Ensure propose_optimizations imports rules text from knowledge_loader, not its o, _cluster_recs returns fewer items when LLM merges duplicates., _cluster_recs returns fewer items when LLM merges duplicates., _cluster_recs returns items as-is when LLM call fails. (+43 more)

### Community 1 - "Task Evaluator"
Cohesion: 0.06
Nodes (53): _append_log(), _build_eval_system(), EvalInput, Post-execution pipeline evaluator. Fail-open: any exception returns None., Evaluate pipeline trace. Returns PipelineEvalOutput or None on any failure., _run(), run_evaluator(), _extract_json_from_text() (+45 more)

### Community 2 - "Pre-Phase & Agents Config"
Cohesion: 0.06
Nodes (52): parse_agents_md(), Parse AGENTS.MD into {section_name: [lines]} for each ## section., _build_schema_digest(), _exec_sql_text(), _parse_csv_rows(), PrephaseResult, run_prephase(), test_empty_section_has_empty_lines() (+44 more)

### Community 3 - "Trace Logger"
Cohesion: 0.08
Nodes (31): set_trace(), TraceLogger, _collect_trace_records(), _exec_ok(), _make_pre(), Verify pipeline instruments TraceLogger at all required points., sql_validate + sql_execute records written on successful cycle., Happy path: sql_plan + answer llm_call records written. (+23 more)

### Community 4 - "Contract Models"
Cohesion: 0.07
Nodes (44): Contract, ContractRound, EvaluatorResponse, ExecutorProposal, _compute_eval_metrics(), Compute agents_md_coverage and schema_grounding. Returns dict with both floats., AnswerOutput, LearnOutput (+36 more)

### Community 5 - "Optimization Pipeline"
Cohesion: 0.05
Nodes (48): Optimization Pipeline Design, call_llm_raw_cluster, _check_contradiction, _cluster_recs, _dedup_by_content_per_task, _entry_hash, _load_model_cfg, _load_processed (+40 more)

### Community 6 - "LLM Routing Layer"
Cohesion: 0.05
Nodes (40): _call_raw_single_model(), get_anthropic_model_id(), get_provider(), get_response_format(), _get_static_hint(), is_claude_code_model(), is_claude_model(), is_ollama_model() (+32 more)

### Community 7 - "SQL Security Gates"
Cohesion: 0.06
Nodes (44): check_grounding_refs(), check_learn_output(), check_path_access(), check_retry_loop(), check_sql_queries(), check_where_literals(), _has_where_clause(), _is_select() (+36 more)

### Community 8 - "JSON Extraction & Answer"
Cohesion: 0.07
Nodes (38): _obj_mutation_tool(), Return the mutation tool name if obj is a write/delete/exec action, else None., _build_answer_user_msg(), _extract_sku_refs(), Extract catalogue paths from SQL results. Uses 'path' column when present,     f, Raw hierarchical paths stored verbatim in sku_refs., AUTO_REFS block must show full paths — LLM copies them verbatim to grounding_ref, test_build_answer_user_msg_no_refs() (+30 more)

### Community 9 - "Agent Orchestrator"
Cohesion: 0.07
Nodes (22): Minimal orchestrator for ecom benchmark., Execute a single benchmark task., run_agent(), HarnessServiceClientSync, _log_stats(), main(), _print_table_header(), _print_table_row() (+14 more)

### Community 10 - "System Prompt Assembly"
Cohesion: 0.08
Nodes (30): _build_static_system(), _format_schema_digest(), _gates_summary(), _relevant_agents_sections(), Load SQL planning rules from data/rules/ (one YAML file per rule)., RulesLoader, _build_static_system('sql_plan') includes security gates; 'learn' does not., _build_static_system does not include IN-SESSION RULE (those go to user_msg). (+22 more)

### Community 11 - "BitGN Connect Client"
Cohesion: 0.06
Nodes (4): ConnectClient, Minimal Connect RPC client using JSON protocol over httpx., EcomRuntimeClientSync, PcmRuntimeClientSync

### Community 12 - "Schema Gate"
Cohesion: 0.1
Nodes (31): _build_alias_map(), _check_query(), check_schema_compliance(), _known_cols_by_table(), Schema-aware SQL validator: unknown columns, unverified literals, double-key JOI, Check queries against schema. Returns first error string or None if all pass., Return {table_name_lower: {col_name_lower, ...}}., Return {alias_lower: table_name_lower} from FROM and JOIN clauses. (+23 more)

### Community 13 - "Value Resolver"
Cohesion: 0.12
Nodes (29): _all_values(), _build_resolve_system(), _exec_sql(), _first_value(), Resolve phase: confirm task identifiers against DB before pipeline cycles., Deprecated shim — kept for test backward compat. Use _all_values., Resolve identifiers in task_text against DB. Returns confirmed_values or {} on f, _run() (+21 more)

### Community 14 - "Claude Prompt Builder"
Cohesion: 0.09
Nodes (30): AGENTS.MD, build_system_prompt, call_llm_raw, data/prompts/*.md, data/prompts/optimized/, data/rules/*.yaml, data/security/*.yaml, data/eval_log.jsonl (+22 more)

### Community 15 - "Pipeline Tests"
Cohesion: 0.13
Nodes (28): _answer_json(), _make_exec_result(), _make_pre(), 3 cycles all fail → OUTCOME_NONE_CLARIFICATION without ANSWER LLM call., DDL query → security gate blocks → LEARN → retry → success., LEARN updates session_rules but does not write rule files (append_rule removed)., total_in_tok and total_out_tok are non-zero after successful pipeline run., SQL_PLAN → VALIDATE ok → EXECUTE ok → ANSWER ok. (+20 more)

### Community 16 - "Agent Configuration"
Cohesion: 0.08
Nodes (27): /AGENTS.MD (vault rules), AnswerOutput, cc_client.py, data/prompts/{phase}.md, data/rules/*.yaml, data/security/*.yaml, JSON extraction mutation-first priority, json_extract.py (+19 more)

### Community 17 - "Prompt Loader"
Cohesion: 0.13
Nodes (21): build_system_prompt(), load_prompt(), System prompt builder — loads blocks from data/prompts/*.md., Return prompt block by file stem name. Returns '' if not found., Assemble system prompt from file-based blocks for the given task type., test_build_system_prompt_fallback_to_default_for_unknown(), test_build_system_prompt_lookup_contains_core_and_catalogue(), test_core_has_ecom_role() (+13 more)

### Community 18 - "Discovery Pipeline"
Cohesion: 0.1
Nodes (21): _extract_discovery_results(), _format_confirmed_values(), Update confirmed_values in-place from DISTINCT query results., _call_llm_phase returns (obj, sgr, tok) — tok has input/output keys., _run_learn with error_type='llm_fail' must not add to session_rules., LEARN sgr_trace entry must contain 'error_type' field., session_rules accumulates all LEARN rules — no truncation cap., run_pipeline signature includes all injection params. (+13 more)

### Community 19 - "Pipeline Message Builder"
Cohesion: 0.23
Nodes (15): _build_learn_user_msg(), _build_sql_user_msg(), _call_llm_phase(), _csv_has_data(), _exec_result_text(), _get_rules_loader(), _get_security_gates(), Phase-based SQL pipeline for lookup tasks — replaces run_loop() for task_type='l (+7 more)

### Community 20 - "TDD Pipeline Tests"
Cohesion: 0.29
Nodes (15): _answer_json(), _make_exec_result(), _make_pre(), sql_tests fail → LEARN + SQL_PLAN retry (_skip_sql=False) → sql_tests pass → ANS, answer_tests fail → LEARN + _skip_sql=True → next cycle skips SQL, retries ANSWE, TEST_GEN returns garbage → vm.answer(OUTCOME_NONE_CLARIFICATION), SQL never runs, TDD_ENABLED=0 → pipeline identical to current; run_tests never called., TDD_ENABLED=1 + all tests pass → OUTCOME_OK, vm.answer called once. (+7 more)

### Community 21 - "Claude Code Client"
Cohesion: 0.27
Nodes (8): _build_env(), cc_complete(), _parse_envelope(), Claude Code tier — spawn iclaude CLI as stateless LLM.  Bypasses applied (all re, Spawn iclaude once. Returns (stdout_lines, exit_code, fail_reason).     fail_rea, Stateless LLM call via iclaude subprocess.      Returns assistant text (JSON str, Extract result text and token usage from iclaude --output-format json.     Envel, _spawn_once()

### Community 22 - "Test Runner"
Cohesion: 0.29
Nodes (8): Subprocess test runner for TDD pipeline., Run test_code in isolated subprocess. Returns (passed, error_message)., run_tests(), test_answer_tests_signature(), test_failing_assert(), test_passing_assert(), test_syntax_error_in_test_code(), test_timeout()

### Community 23 - "Eval Optimization Docs"
Cohesion: 0.25
Nodes (8): data/eval_log.jsonl, data/.eval_optimizations_processed (processed hashes), MODEL_EVALUATOR env var, prompt_optimization channel → data/prompts/optimized/, scripts/propose_optimizations.py, rule_optimization channel → data/rules/sql-NNN.yaml, security_optimization channel → data/security/sec-NNN.yaml, Three optimization channels (rule, security, prompt)

### Community 24 - "Trace Tests"
Cohesion: 0.33
Nodes (5): Verify main.py creates/closes TraceLogger and calls log_header + log_task_result, main.log must contain stats rows but NOT pipeline cycle lines., After _run_single_task: .jsonl created, no .log file, log_header + log_task_resu, test_main_log_contains_only_stats(), test_run_single_task_creates_jsonl_and_removes_log()

### Community 28 - "Task Definitions"
Cohesion: 0.6
Nodes (5): check_grounding_refs, clean_refs, p.path SQL column, sku_refs, t16 grounding refs bug

## Knowledge Gaps
- **272 isolated node(s):** `Create run dir, open main.log for stats, wrap stdout for [task_id] terminal pref`, `Execute one benchmark trial.`, `System prompt builder — loads blocks from data/prompts/*.md.`, `Return prompt block by file stem name. Returns '' if not found.`, `Assemble system prompt from file-based blocks for the given task type.` (+267 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_pipeline()` connect `Pipeline Message Builder` to `Trace Logger`, `SQL Security Gates`, `JSON Extraction & Answer`, `Agent Orchestrator`, `System Prompt Assembly`, `Schema Gate`, `Value Resolver`, `Pipeline Tests`, `Discovery Pipeline`, `TDD Pipeline Tests`, `Test Runner`?**
  _High betweenness centrality (0.263) - this node is a cross-community bridge._
- **Why does `run_agent()` connect `Agent Orchestrator` to `BitGN Connect Client`, `Pre-Phase & Agents Config`, `Pipeline Message Builder`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Why does `run_prephase()` connect `Pre-Phase & Agents Config` to `Agent Orchestrator`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **Are the 29 inferred relationships involving `run_pipeline()` (e.g. with `run_resolve()` and `check_sql_queries()`) actually correct?**
  _`run_pipeline()` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `main` (e.g. with `test_existing_security_text_returns_id_message` and `test_existing_prompts_text_returns_full_content`) actually correct?**
  _`main` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `TraceLogger` (e.g. with `_run_single_task()` and `_collect_trace_records()`) actually correct?**
  _`TraceLogger` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `load_prompt()` (e.g. with `_build_static_system()` and `_run_test_gen()`) actually correct?**
  _`load_prompt()` has 18 INFERRED edges - model-reasoned connections that need verification._