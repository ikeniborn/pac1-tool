# Graph Report - .  (2026-05-15)

## Corpus Check
- 5 files · ~4,660 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 873 nodes · 1415 edges · 43 communities (38 shown, 5 thin omitted)
- Extraction: 79% EXTRACTED · 21% INFERRED · 0% AMBIGUOUS · INFERRED: 292 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Optimization Tests|Optimization Tests]]
- [[_COMMUNITY_Prephase & Schema|Prephase & Schema]]
- [[_COMMUNITY_TDD Trace Logging|TDD Trace Logging]]
- [[_COMMUNITY_Evaluator & Models|Evaluator & Models]]
- [[_COMMUNITY_Optimization Pipeline|Optimization Pipeline]]
- [[_COMMUNITY_LLM Routing|LLM Routing]]
- [[_COMMUNITY_SQL Security Gates|SQL Security Gates]]
- [[_COMMUNITY_Pipeline Answer Build|Pipeline Answer Build]]
- [[_COMMUNITY_Orchestrator & Harness|Orchestrator & Harness]]
- [[_COMMUNITY_JSON Extraction|JSON Extraction]]
- [[_COMMUNITY_Prompt Assembly|Prompt Assembly]]
- [[_COMMUNITY_Connect RPC Client|Connect RPC Client]]
- [[_COMMUNITY_Schema Gate|Schema Gate]]
- [[_COMMUNITY_Resolve Phase|Resolve Phase]]
- [[_COMMUNITY_CLAUDE Context|CLAUDE Context]]
- [[_COMMUNITY_Module Group 15|Module Group 15]]
- [[_COMMUNITY_Module Group 16|Module Group 16]]
- [[_COMMUNITY_Module Group 17|Module Group 17]]
- [[_COMMUNITY_Module Group 18|Module Group 18]]
- [[_COMMUNITY_Module Group 19|Module Group 19]]
- [[_COMMUNITY_Module Group 20|Module Group 20]]
- [[_COMMUNITY_Module Group 21|Module Group 21]]
- [[_COMMUNITY_Module Group 22|Module Group 22]]
- [[_COMMUNITY_Module Group 23|Module Group 23]]
- [[_COMMUNITY_Module Group 24|Module Group 24]]
- [[_COMMUNITY_Module Group 25|Module Group 25]]
- [[_COMMUNITY_Module Group 28|Module Group 28]]
- [[_COMMUNITY_Module Group 29|Module Group 29]]
- [[_COMMUNITY_Module Group 30|Module Group 30]]
- [[_COMMUNITY_Module Group 31|Module Group 31]]
- [[_COMMUNITY_Module Group 32|Module Group 32]]
- [[_COMMUNITY_Module Group 42|Module Group 42]]

## God Nodes (most connected - your core abstractions)
1. `run_pipeline()` - 45 edges
2. `main` - 36 edges
3. `TraceLogger` - 32 edges
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

## Communities (43 total, 5 thin omitted)

### Community 0 - "Optimization Tests"
Cohesion: 0.08
Nodes (51): _base_patches(), _eval_entry(), _make_harness_mocks(), Ensure propose_optimizations imports rules text from knowledge_loader, not its o, Ensure propose_optimizations imports rules text from knowledge_loader, not its o, _cluster_recs returns fewer items when LLM merges duplicates., _cluster_recs returns fewer items when LLM merges duplicates., _cluster_recs returns items as-is when LLM call fails. (+43 more)

### Community 1 - "Prephase & Schema"
Cohesion: 0.06
Nodes (52): parse_agents_md(), Parse AGENTS.MD into {section_name: [lines]} for each ## section., _build_schema_digest(), _exec_sql_text(), _parse_csv_rows(), PrephaseResult, run_prephase(), test_empty_section_has_empty_lines() (+44 more)

### Community 2 - "TDD Trace Logging"
Cohesion: 0.08
Nodes (31): set_trace(), TraceLogger, _collect_trace_records(), _exec_ok(), _make_pre(), Verify pipeline instruments TraceLogger at all required points., sql_validate + sql_execute records written on successful cycle., Happy path: sql_plan + answer llm_call records written. (+23 more)

### Community 3 - "Evaluator & Models"
Cohesion: 0.07
Nodes (44): Contract, ContractRound, EvaluatorResponse, ExecutorProposal, _compute_eval_metrics(), Compute agents_md_coverage and schema_grounding. Returns dict with both floats., AnswerOutput, LearnOutput (+36 more)

### Community 4 - "Optimization Pipeline"
Cohesion: 0.05
Nodes (48): Optimization Pipeline Design, call_llm_raw_cluster, _check_contradiction, _cluster_recs, _dedup_by_content_per_task, _entry_hash, _load_model_cfg, _load_processed (+40 more)

### Community 5 - "LLM Routing"
Cohesion: 0.05
Nodes (40): _call_raw_single_model(), get_anthropic_model_id(), get_provider(), get_response_format(), _get_static_hint(), is_claude_code_model(), is_claude_model(), is_ollama_model() (+32 more)

### Community 6 - "SQL Security Gates"
Cohesion: 0.06
Nodes (44): check_grounding_refs(), check_learn_output(), check_path_access(), check_retry_loop(), check_sql_queries(), check_where_literals(), _has_where_clause(), _is_select() (+36 more)

### Community 7 - "Pipeline Answer Build"
Cohesion: 0.07
Nodes (38): _obj_mutation_tool(), Return the mutation tool name if obj is a write/delete/exec action, else None., _build_answer_user_msg(), _extract_sku_refs(), Extract catalogue paths from SQL results. Uses 'path' column when present,     f, Raw hierarchical paths stored verbatim in sku_refs., AUTO_REFS block must show full paths — LLM copies them verbatim to grounding_ref, test_build_answer_user_msg_no_refs() (+30 more)

### Community 8 - "Orchestrator & Harness"
Cohesion: 0.07
Nodes (22): Minimal orchestrator for ecom benchmark., Execute a single benchmark task., run_agent(), HarnessServiceClientSync, _log_stats(), main(), _print_table_header(), _print_table_row() (+14 more)

### Community 9 - "JSON Extraction"
Cohesion: 0.09
Nodes (34): _extract_json_from_text(), JSON extraction from free-form LLM text output.  Public API:   _obj_mutation_too, Try json5 parse; raises on failure (ImportError or parse error)., Lower tuple = preferred. Used by min() to break ties among same-tier candidates., Extract the most actionable valid JSON object from free-form model output., _richness_key(), _try_json5(), call_llm_raw() (+26 more)

### Community 10 - "Prompt Assembly"
Cohesion: 0.08
Nodes (30): _build_static_system(), _format_schema_digest(), _gates_summary(), _relevant_agents_sections(), Load SQL planning rules from data/rules/ (one YAML file per rule)., RulesLoader, _build_static_system('sql_plan') includes security gates; 'learn' does not., _build_static_system does not include IN-SESSION RULE (those go to user_msg). (+22 more)

### Community 11 - "Connect RPC Client"
Cohesion: 0.06
Nodes (4): ConnectClient, Minimal Connect RPC client using JSON protocol over httpx., EcomRuntimeClientSync, PcmRuntimeClientSync

### Community 12 - "Schema Gate"
Cohesion: 0.1
Nodes (31): _build_alias_map(), _check_query(), check_schema_compliance(), _known_cols_by_table(), Schema-aware SQL validator: unknown columns, unverified literals, double-key JOI, Check queries against schema. Returns first error string or None if all pass., Return {table_name_lower: {col_name_lower, ...}}., Return {alias_lower: table_name_lower} from FROM and JOIN clauses. (+23 more)

### Community 13 - "Resolve Phase"
Cohesion: 0.12
Nodes (29): _all_values(), _build_resolve_system(), _exec_sql(), _first_value(), Resolve phase: confirm task identifiers against DB before pipeline cycles., Deprecated shim — kept for test backward compat. Use _all_values., Resolve identifiers in task_text against DB. Returns confirmed_values or {} on f, _run() (+21 more)

### Community 14 - "CLAUDE Context"
Cohesion: 0.09
Nodes (30): AGENTS.MD, build_system_prompt, call_llm_raw, data/prompts/*.md, data/prompts/optimized/, data/rules/*.yaml, data/security/*.yaml, data/eval_log.jsonl (+22 more)

### Community 15 - "Module Group 15"
Cohesion: 0.13
Nodes (28): _answer_json(), _make_exec_result(), _make_pre(), 3 cycles all fail → OUTCOME_NONE_CLARIFICATION without ANSWER LLM call., DDL query → security gate blocks → LEARN → retry → success., LEARN updates session_rules but does not write rule files (append_rule removed)., total_in_tok and total_out_tok are non-zero after successful pipeline run., SQL_PLAN → VALIDATE ok → EXECUTE ok → ANSWER ok. (+20 more)

### Community 16 - "Module Group 16"
Cohesion: 0.08
Nodes (27): /AGENTS.MD (vault rules), AnswerOutput, cc_client.py, data/prompts/{phase}.md, data/rules/*.yaml, data/security/*.yaml, JSON extraction mutation-first priority, json_extract.py (+19 more)

### Community 17 - "Module Group 17"
Cohesion: 0.13
Nodes (21): build_system_prompt(), load_prompt(), System prompt builder — loads blocks from data/prompts/*.md., Return prompt block by file stem name. Returns '' if not found., Assemble system prompt from file-based blocks for the given task type., test_build_system_prompt_fallback_to_default_for_unknown(), test_build_system_prompt_lookup_contains_core_and_catalogue(), test_core_has_ecom_role() (+13 more)

### Community 18 - "Module Group 18"
Cohesion: 0.1
Nodes (21): _extract_discovery_results(), _format_confirmed_values(), Update confirmed_values in-place from DISTINCT query results., _call_llm_phase returns (obj, sgr, tok) — tok has input/output keys., _run_learn with error_type='llm_fail' must not add to session_rules., LEARN sgr_trace entry must contain 'error_type' field., session_rules accumulates all LEARN rules — no truncation cap., run_pipeline signature includes all injection params. (+13 more)

### Community 19 - "Module Group 19"
Cohesion: 0.16
Nodes (19): _append_log(), _build_eval_system(), EvalInput, Post-execution pipeline evaluator. Fail-open: any exception returns None., Evaluate pipeline trace. Returns PipelineEvalOutput or None on any failure., _run(), run_evaluator(), _run_evaluator_safe() (+11 more)

### Community 20 - "Module Group 20"
Cohesion: 0.18
Nodes (16): _check_tdd_antipatterns(), Subprocess test runner for TDD pipeline., Run test_code in isolated subprocess. Returns (passed, error_message)., Run test_code in isolated subprocess. Returns (passed, error_message, warnings)., run_tests(), False-negative: regex does not match unescaped opposite-quote inside literal. Ac, test_answer_tests_signature(), test_antipattern_header_literal_always_warns() (+8 more)

### Community 21 - "Module Group 21"
Cohesion: 0.23
Nodes (15): _build_learn_user_msg(), _build_sql_user_msg(), _call_llm_phase(), _csv_has_data(), _exec_result_text(), _get_rules_loader(), _get_security_gates(), Phase-based SQL pipeline for lookup tasks — replaces run_loop() for task_type='l (+7 more)

### Community 22 - "Module Group 22"
Cohesion: 0.29
Nodes (15): _answer_json(), _make_exec_result(), _make_pre(), sql_tests fail → LEARN + SQL_PLAN retry (_skip_sql=False) → sql_tests pass → ANS, answer_tests fail → LEARN + _skip_sql=True → next cycle skips SQL, retries ANSWE, TEST_GEN returns garbage → vm.answer(OUTCOME_NONE_CLARIFICATION), SQL never runs, TDD_ENABLED=0 → pipeline identical to current; run_tests never called., TDD_ENABLED=1 + all tests pass → OUTCOME_OK, vm.answer called once. (+7 more)

### Community 23 - "Module Group 23"
Cohesion: 0.27
Nodes (8): _build_env(), cc_complete(), _parse_envelope(), Claude Code tier — spawn iclaude CLI as stateless LLM.  Bypasses applied (all re, Spawn iclaude once. Returns (stdout_lines, exit_code, fail_reason).     fail_rea, Stateless LLM call via iclaude subprocess.      Returns assistant text (JSON str, Extract result text and token usage from iclaude --output-format json.     Envel, _spawn_once()

### Community 24 - "Module Group 24"
Cohesion: 0.25
Nodes (8): data/eval_log.jsonl, data/.eval_optimizations_processed (processed hashes), MODEL_EVALUATOR env var, prompt_optimization channel → data/prompts/optimized/, scripts/propose_optimizations.py, rule_optimization channel → data/rules/sql-NNN.yaml, security_optimization channel → data/security/sec-NNN.yaml, Three optimization channels (rule, security, prompt)

### Community 25 - "Module Group 25"
Cohesion: 0.33
Nodes (5): Verify main.py creates/closes TraceLogger and calls log_header + log_task_result, main.log must contain stats rows but NOT pipeline cycle lines., After _run_single_task: .jsonl created, no .log file, log_header + log_task_resu, test_main_log_contains_only_stats(), test_run_single_task_creates_jsonl_and_removes_log()

### Community 29 - "Module Group 29"
Cohesion: 0.6
Nodes (5): check_grounding_refs, clean_refs, p.path SQL column, sku_refs, t16 grounding refs bug

## Knowledge Gaps
- **274 isolated node(s):** `Create run dir, open main.log for stats, wrap stdout for [task_id] terminal pref`, `Execute one benchmark trial.`, `System prompt builder — loads blocks from data/prompts/*.md.`, `Return prompt block by file stem name. Returns '' if not found.`, `Assemble system prompt from file-based blocks for the given task type.` (+269 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_pipeline()` connect `Module Group 21` to `TDD Trace Logging`, `SQL Security Gates`, `Pipeline Answer Build`, `Orchestrator & Harness`, `Prompt Assembly`, `Schema Gate`, `Resolve Phase`, `Module Group 15`, `Module Group 18`, `Module Group 20`, `Module Group 22`?**
  _High betweenness centrality (0.266) - this node is a cross-community bridge._
- **Why does `run_agent()` connect `Orchestrator & Harness` to `Prephase & Schema`, `Connect RPC Client`, `Module Group 21`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Why does `run_prephase()` connect `Prephase & Schema` to `Orchestrator & Harness`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Are the 29 inferred relationships involving `run_pipeline()` (e.g. with `run_resolve()` and `check_sql_queries()`) actually correct?**
  _`run_pipeline()` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `main` (e.g. with `test_existing_security_text_returns_id_message` and `test_existing_prompts_text_returns_full_content`) actually correct?**
  _`main` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `TraceLogger` (e.g. with `_run_single_task()` and `_collect_trace_records()`) actually correct?**
  _`TraceLogger` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `load_prompt()` (e.g. with `_build_static_system()` and `_run_test_gen()`) actually correct?**
  _`load_prompt()` has 18 INFERRED edges - model-reasoned connections that need verification._