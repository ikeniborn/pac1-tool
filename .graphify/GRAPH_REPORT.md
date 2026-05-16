# Graph Report - .  (2026-05-16)

## Corpus Check
- 8 files · ~0 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 960 nodes · 1610 edges · 54 communities (49 shown, 5 thin omitted)
- Extraction: 81% EXTRACTED · 19% INFERRED · 0% AMBIGUOUS · INFERRED: 313 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
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
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 53|Community 53]]

## God Nodes (most connected - your core abstractions)
1. `run_pipeline()` - 51 edges
2. `main` - 36 edges
3. `TraceLogger` - 32 edges
4. `load_prompt()` - 21 edges
5. `check_schema_compliance()` - 21 edges
6. `_write_eval_log()` - 20 edges
7. `_eval_entry()` - 20 edges
8. `_setup()` - 20 edges
9. `check_sql_queries()` - 19 edges
10. `_base_patches()` - 19 edges

## Surprising Connections (you probably didn't know these)
- `_build_answer_user_msg()` --calls--> `test_build_answer_user_msg_with_refs()`  [INFERRED]
  .worktrees/mock-validation/agent/pipeline.py → tests/test_pipeline_sku_refs.py
- `_build_answer_user_msg()` --calls--> `test_build_answer_user_msg_no_refs()`  [INFERRED]
  .worktrees/mock-validation/agent/pipeline.py → tests/test_pipeline_sku_refs.py
- `_run_learn()` --calls--> `make_json_hash()`  [INFERRED]
  .worktrees/mock-validation/agent/pipeline.py → /home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/sql_security.py
- `get_trace()` --calls--> `test_get_trace_none_by_default()`  [INFERRED]
  agent/trace.py → tests/test_trace.py
- `_run_single_task()` --calls--> `TraceLogger`  [INFERRED]
  /home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/main.py → agent/trace.py

## Communities (54 total, 5 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (52): parse_agents_md(), Parse AGENTS.MD into {section_name: [lines]} for each ## section., _build_schema_digest(), _exec_sql_text(), _parse_csv_rows(), PrephaseResult, run_prephase(), test_empty_section_has_empty_lines() (+44 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (31): set_trace(), TraceLogger, _collect_trace_records(), _exec_ok(), _make_pre(), Verify pipeline instruments TraceLogger at all required points., sql_validate + sql_execute records written on successful cycle., Happy path: sql_plan + answer llm_call records written. (+23 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (48): Optimization Pipeline Design, call_llm_raw_cluster, _check_contradiction, _cluster_recs, _dedup_by_content_per_task, _entry_hash, _load_model_cfg, _load_processed (+40 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (40): _call_raw_single_model(), get_anthropic_model_id(), get_provider(), get_response_format(), _get_static_hint(), is_claude_code_model(), is_claude_model(), is_ollama_model() (+32 more)

### Community 4 - "Community 4"
Cohesion: 0.06
Nodes (44): check_grounding_refs(), check_learn_output(), check_path_access(), check_retry_loop(), check_sql_queries(), check_where_literals(), _has_where_clause(), _is_select() (+36 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (40): _extract_json_from_text(), JSON extraction from free-form LLM text output.  Public API:   _obj_mutation_too, Try json5 parse; raises on failure (ImportError or parse error)., Lower tuple = preferred. Used by min() to break ties among same-tier candidates., Extract the most actionable valid JSON object from free-form model output., _richness_key(), _try_json5(), call_llm_raw() (+32 more)

### Community 6 - "Community 6"
Cohesion: 0.09
Nodes (37): Contract, ContractRound, EvaluatorResponse, ExecutorProposal, _compute_eval_metrics(), Compute agents_md_coverage and schema_grounding. Returns dict with both floats., AnswerOutput, LearnOutput (+29 more)

### Community 7 - "Community 7"
Cohesion: 0.06
Nodes (38): _obj_mutation_tool(), Return the mutation tool name if obj is a write/delete/exec action, else None., _extract_sku_refs(), Extract catalogue paths from SQL results. Uses 'path' column when present,     f, Extract catalogue paths from SQL results. Uses 'path' column when present,     f, Raw hierarchical paths stored verbatim in sku_refs., AUTO_REFS block must show full paths — LLM copies them verbatim to grounding_ref, test_build_answer_user_msg_no_refs() (+30 more)

### Community 8 - "Community 8"
Cohesion: 0.07
Nodes (22): Minimal orchestrator for ecom benchmark., Execute a single benchmark task., run_agent(), HarnessServiceClientSync, _log_stats(), main(), _print_table_header(), _print_table_row() (+14 more)

### Community 9 - "Community 9"
Cohesion: 0.06
Nodes (4): ConnectClient, Minimal Connect RPC client using JSON protocol over httpx., EcomRuntimeClientSync, PcmRuntimeClientSync

### Community 10 - "Community 10"
Cohesion: 0.09
Nodes (28): _build_static_system(), _format_schema_digest(), Load SQL planning rules from data/rules/ (one YAML file per rule)., RulesLoader, _build_static_system('sql_plan') includes security gates; 'learn' does not., _build_static_system does not include IN-SESSION RULE (those go to user_msg)., _build_static_system returns list[dict], last block has cache_control., When injected_prompt_addendum is non-empty, appends to guide block. (+20 more)

### Community 11 - "Community 11"
Cohesion: 0.1
Nodes (31): _build_alias_map(), _check_query(), check_schema_compliance(), _known_cols_by_table(), Schema-aware SQL validator: unknown columns, unverified literals, double-key JOI, Check queries against schema. Returns first error string or None if all pass., Return {table_name_lower: {col_name_lower, ...}}., Return {alias_lower: table_name_lower} from FROM and JOIN clauses. (+23 more)

### Community 12 - "Community 12"
Cohesion: 0.12
Nodes (29): _all_values(), _build_resolve_system(), _exec_sql(), _first_value(), Resolve phase: confirm task identifiers against DB before pipeline cycles., Deprecated shim — kept for test backward compat. Use _all_values., Resolve identifiers in task_text against DB. Returns confirmed_values or {} on f, _run() (+21 more)

### Community 13 - "Community 13"
Cohesion: 0.08
Nodes (28): MockScenario, _mock_entry(), _mock_scenario(), Valid LLM response → MockScenario., LLM returns None → None., LLM returns non-JSON → None., LLM returns JSON missing required fields → None., _generate_mock_scenario returns None → score=1.0 (fail-open). (+20 more)

### Community 14 - "Community 14"
Cohesion: 0.09
Nodes (30): AGENTS.MD, build_system_prompt, call_llm_raw, data/prompts/*.md, data/prompts/optimized/, data/rules/*.yaml, data/security/*.yaml, data/eval_log.jsonl (+22 more)

### Community 15 - "Community 15"
Cohesion: 0.12
Nodes (22): _MockResult, MockVM, test_answer_captures_last_answer(), test_answer_does_not_raise(), test_exec_clamps_to_last_result(), test_exec_cycles_through_results(), test_exec_empty_mock_results_returns_empty_string(), test_exec_explain_case_insensitive() (+14 more)

### Community 16 - "Community 16"
Cohesion: 0.13
Nodes (28): _answer_json(), _make_exec_result(), _make_pre(), 3 cycles all fail → OUTCOME_NONE_CLARIFICATION without ANSWER LLM call., DDL query → security gate blocks → LEARN → retry → success., LEARN updates session_rules but does not write rule files (append_rule removed)., total_in_tok and total_out_tok are non-zero after successful pipeline run., SQL_PLAN → VALIDATE ok → EXECUTE ok → ANSWER ok. (+20 more)

### Community 17 - "Community 17"
Cohesion: 0.17
Nodes (28): _base_patches(), _eval_entry(), Second rule synthesis receives updated rules_md after first write., Second rule synthesis receives updated rules_md after first write., Second rule synthesis receives updated rules_md after first write., Accepted (mock_score >= 1.0) → file written., Rejected (mock_score < 1.0) → no file written., Same rec text for same task_id validated only once. (+20 more)

### Community 18 - "Community 18"
Cohesion: 0.08
Nodes (27): /AGENTS.MD (vault rules), AnswerOutput, cc_client.py, data/prompts/{phase}.md, data/rules/*.yaml, data/security/*.yaml, JSON extraction mutation-first priority, json_extract.py (+19 more)

### Community 19 - "Community 19"
Cohesion: 0.13
Nodes (21): build_system_prompt(), load_prompt(), System prompt builder — loads blocks from data/prompts/*.md., Return prompt block by file stem name. Returns '' if not found., Assemble system prompt from file-based blocks for the given task type., test_build_system_prompt_fallback_to_default_for_unknown(), test_build_system_prompt_lookup_contains_core_and_catalogue(), test_core_has_ecom_role() (+13 more)

### Community 20 - "Community 20"
Cohesion: 0.1
Nodes (22): _extract_discovery_results(), _format_confirmed_values(), Update confirmed_values in-place from DISTINCT query results., Update confirmed_values in-place from DISTINCT query results., _call_llm_phase returns (obj, sgr, tok) — tok has input/output keys., _run_learn with error_type='llm_fail' must not add to session_rules., LEARN sgr_trace entry must contain 'error_type' field., session_rules accumulates all LEARN rules — no truncation cap. (+14 more)

### Community 21 - "Community 21"
Cohesion: 0.2
Nodes (20): _build_answer_user_msg(), _build_learn_user_msg(), _build_sql_user_msg(), _call_llm_phase(), _csv_has_data(), _exec_result_text(), _gates_summary(), _get_rules_loader() (+12 more)

### Community 22 - "Community 22"
Cohesion: 0.16
Nodes (19): _append_log(), _build_eval_system(), EvalInput, Post-execution pipeline evaluator. Fail-open: any exception returns None., Evaluate pipeline trace. Returns PipelineEvalOutput or None on any failure., _run(), run_evaluator(), _run_evaluator_safe() (+11 more)

### Community 23 - "Community 23"
Cohesion: 0.18
Nodes (16): _check_tdd_antipatterns(), Subprocess test runner for TDD pipeline., Run test_code in isolated subprocess. Returns (passed, error_message)., Run test_code in isolated subprocess. Returns (passed, error_message, warnings)., run_tests(), False-negative: regex does not match unescaped opposite-quote inside literal. Ac, test_answer_tests_signature(), test_antipattern_header_literal_always_warns() (+8 more)

### Community 24 - "Community 24"
Cohesion: 0.29
Nodes (15): _answer_json(), _make_exec_result(), _make_pre(), sql_tests fail → LEARN + SQL_PLAN retry (_skip_sql=False) → sql_tests pass → ANS, answer_tests fail → LEARN + _skip_sql=True → next cycle skips SQL, retries ANSWE, TEST_GEN returns garbage → vm.answer(OUTCOME_NONE_CLARIFICATION), SQL never runs, TDD_ENABLED=0 → pipeline identical to current; run_tests never called., TDD_ENABLED=1 + all tests pass → OUTCOME_OK, vm.answer called once. (+7 more)

### Community 25 - "Community 25"
Cohesion: 0.19
Nodes (9): _make_harness_mocks(), test_existing_prompts_text_empty_dir(), test_existing_prompts_text_returns_full_content(), test_existing_security_text_returns_id_message(), test_existing_security_text_skips_invalid(), test_validate_recommendation_accepted(), test_validate_recommendation_no_baseline(), test_validate_recommendation_rejected() (+1 more)

### Community 26 - "Community 26"
Cohesion: 0.27
Nodes (8): _build_env(), cc_complete(), _parse_envelope(), Claude Code tier — spawn iclaude CLI as stateless LLM.  Bypasses applied (all re, Spawn iclaude once. Returns (stdout_lines, exit_code, fail_reason).     fail_rea, Stateless LLM call via iclaude subprocess.      Returns assistant text (JSON str, Extract result text and token usage from iclaude --output-format json.     Envel, _spawn_once()

### Community 27 - "Community 27"
Cohesion: 0.27
Nodes (8): Test that all vault classes have been removed from models.py, Test that models.py contains exactly 8 BaseModel classes (4 pipeline + 2 resolve, Test that the 4 pipeline models are present in models.py, test_mock_scenario_fields(), test_models_has_exactly_seven_classes(), test_pipeline_models_present(), test_test_gen_output_fields(), test_vault_models_removed()

### Community 28 - "Community 28"
Cohesion: 0.25
Nodes (8): data/eval_log.jsonl, data/.eval_optimizations_processed (processed hashes), MODEL_EVALUATOR env var, prompt_optimization channel → data/prompts/optimized/, scripts/propose_optimizations.py, rule_optimization channel → data/rules/sql-NNN.yaml, security_optimization channel → data/security/sec-NNN.yaml, Three optimization channels (rule, security, prompt)

### Community 29 - "Community 29"
Cohesion: 0.29
Nodes (7): _cluster_recs returns items as-is when LLM call fails., _cluster_recs returns items as-is when LLM call fails., All hashes in a cluster group are marked processed after writing the representat, _cluster_recs returns items as-is when LLM call fails., All hashes in a cluster group are marked processed after writing the representat, test_cluster_recs_all_hashes_marked_on_write(), test_cluster_recs_fallback_on_llm_failure()

### Community 30 - "Community 30"
Cohesion: 0.33
Nodes (5): Verify main.py creates/closes TraceLogger and calls log_header + log_task_result, main.log must contain stats rows but NOT pipeline cycle lines., After _run_single_task: .jsonl created, no .log file, log_header + log_task_resu, test_main_log_contains_only_stats(), test_run_single_task_creates_jsonl_and_removes_log()

### Community 34 - "Community 34"
Cohesion: 0.6
Nodes (5): check_grounding_refs, clean_refs, p.path SQL column, sku_refs, t16 grounding refs bug

### Community 35 - "Community 35"
Cohesion: 0.5
Nodes (4): Returns conflict string when LLM finds contradiction., Returns conflict string when LLM finds contradiction., Returns conflict string when LLM finds contradiction., test_check_contradiction_returns_string_on_conflict()

### Community 36 - "Community 36"
Cohesion: 0.5
Nodes (4): Ensure propose_optimizations imports rules text from knowledge_loader, not its o, Ensure propose_optimizations imports rules text from knowledge_loader, not its o, Ensure propose_optimizations imports rules text from knowledge_loader, not its o, test_main_uses_knowledge_loader_for_rules()

### Community 37 - "Community 37"
Cohesion: 0.5
Nodes (4): Rule with contradiction is not written and its hashes are not marked processed., Rule with contradiction is not written and its hashes are not marked processed., Rule with contradiction is not written and its hashes are not marked processed., test_contradiction_blocks_write()

### Community 38 - "Community 38"
Cohesion: 0.5
Nodes (4): _cluster_recs returns fewer items when LLM merges duplicates., _cluster_recs returns fewer items when LLM merges duplicates., _cluster_recs returns fewer items when LLM merges duplicates., test_cluster_recs_merges_duplicates()

### Community 39 - "Community 39"
Cohesion: 0.5
Nodes (4): Returns None when LLM says OK., Returns None when LLM says OK., Returns None when LLM says OK., test_check_contradiction_returns_none_on_ok()

### Community 41 - "Community 41"
Cohesion: 0.67
Nodes (3): --dry-run skips validate_mock entirely., candidate pipeline produces no answer → score=0.0., test_dry_run_skips_validation()

## Knowledge Gaps
- **306 isolated node(s):** `Create run dir, open main.log for stats, wrap stdout for [task_id] terminal pref`, `Execute one benchmark trial.`, `System prompt builder — loads blocks from data/prompts/*.md.`, `Return prompt block by file stem name. Returns '' if not found.`, `Assemble system prompt from file-based blocks for the given task type.` (+301 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_pipeline()` connect `Community 21` to `Community 1`, `Community 4`, `Community 5`, `Community 7`, `Community 8`, `Community 10`, `Community 11`, `Community 12`, `Community 15`, `Community 16`, `Community 20`, `Community 23`, `Community 24`?**
  _High betweenness centrality (0.353) - this node is a cross-community bridge._
- **Why does `MockScenario` connect `Community 13` to `Community 27`, `Community 6`?**
  _High betweenness centrality (0.155) - this node is a cross-community bridge._
- **Are the 33 inferred relationships involving `run_pipeline()` (e.g. with `run_resolve()` and `check_sql_queries()`) actually correct?**
  _`run_pipeline()` has 33 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `main` (e.g. with `test_existing_security_text_returns_id_message` and `test_existing_prompts_text_returns_full_content`) actually correct?**
  _`main` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `TraceLogger` (e.g. with `_run_single_task()` and `_collect_trace_records()`) actually correct?**
  _`TraceLogger` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `load_prompt()` (e.g. with `_build_static_system()` and `_run_test_gen()`) actually correct?**
  _`load_prompt()` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `check_schema_compliance()` (e.g. with `run_pipeline()` and `test_valid_query_passes()`) actually correct?**
  _`check_schema_compliance()` has 18 INFERRED edges - model-reasoned connections that need verification._