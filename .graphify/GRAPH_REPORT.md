# Graph Report - logs/20260511_134122_qwen3.5-cloud + ecom-py  (2026-05-11)

## Corpus Check
- 15 files · ~400,000 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 84 nodes · 117 edges · 9 communities (7 shown, 2 thin omitted)
- Extraction: 68% EXTRACTED · 32% INFERRED · 0% AMBIGUOUS · INFERRED: 37 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Agent Pipeline (Our)|Agent Pipeline (Our)]]
- [[_COMMUNITY_Prephase & Task Load|Prephase & Task Load]]
- [[_COMMUNITY_Wiki Knowledge System|Wiki Knowledge System]]
- [[_COMMUNITY_Context Overflow Failures|Context Overflow Failures]]
- [[_COMMUNITY_LLM Models & Dispatch|LLM Models & Dispatch]]
- [[_COMMUNITY_Contract & Consensus|Contract & Consensus]]
- [[_COMMUNITY_Sample Agent (ecom-py)|Sample Agent (ecom-py)]]
- [[_COMMUNITY_Architecture Diff & Fixes|Architecture Diff & Fixes]]
- [[_COMMUNITY_PCM Tools|PCM Tools]]

## God Nodes (most connected - your core abstractions)
1. `Agent Loop (≤30 steps)` - 20 edges
2. `Prephase: Vault Explorer` - 17 edges
3. `Sample: run_agent() — main loop` - 17 edges
4. `LLM Dispatcher` - 7 edges
5. `Prephase Load: Medium (100-2000 reads)` - 7 edges
6. `Error: Context Window Overflow (>262K tokens)` - 6 edges
7. `Prephase Load: Large (>9000 reads) → OVERFLOW` - 6 edges
8. `Model Router` - 5 edges
9. `Contract Phase: Executor+Evaluator Consensus` - 5 edges
10. `Wiki Lint` - 5 edges

## Surprising Connections (you probably didn't know these)
- `Agent Loop (≤30 steps)` --calls--> `FIX-345: report_completion blocked — no vault discovery`  [INFERRED]
  agent/__init__.py → main.log
- `Sample: NextStep (Pydantic union schema)` --semantically_similar_to--> `Agent Loop (≤30 steps)`  [INFERRED] [semantically similar]
  ecom-py/agent.py → agent/__init__.py
- `Prephase: Vault Explorer` --rationale_for--> `Root Cause: Prephase reads 9000+ catalog files → context overflow`  [INFERRED]
  agent/__init__.py → main.log
- `Prephase: Vault Explorer` --calls--> `Prephase Load: Large (>9000 reads) → OVERFLOW`  [INFERRED]
  agent/__init__.py → main.log
- `Prephase: Vault Explorer` --precedes--> `t02 | score=1.0 | OK | reads=102`  [EXTRACTED]
  agent/__init__.py → t02.log

## Hyperedges (group relationships)
- **Context Overflow Failure Group (t04, t08, t12)** — task_t04, task_t08, task_t12, prephase_large, error_ctx_overflow, root_cause_prephase_bloat [EXTRACTED 1.00]
- **Medium-load successful tasks (t02, t03, t10, t11)** — task_t02, task_t03, task_t10, task_t11, prephase_medium [EXTRACTED 1.00]
- **Agent Pipeline Modules** — module_prephase, module_classifier, module_model_router, module_prompt_builder, module_contract, module_loop, module_evaluator [EXTRACTED 1.00]
- **Sample Agent vs Our Agent: Architecture Comparison** — sa_must_phase, module_prephase, diff_no_prephase_bloat, fix_overflow_solution, root_cause_prephase_bloat [EXTRACTED 1.00]
- **Sample Agent: Missing subsystems vs Our Agent** — diff_no_dspy, diff_no_contract, diff_no_wiki, diff_no_stall, diff_no_parallel [EXTRACTED 1.00]

## Communities (9 total, 2 thin omitted)

### Community 0 - "Agent Pipeline (Our)"
Cohesion: 0.11
Nodes (18): KEY DIFF: No stall detection, no security gates, Agent Loop (≤30 steps), Security Gates, Stall Detector, Our Agent: complex system prompt (task-type blocks, wiki, graph), Sample: minimal 3-line system prompt (no task-type blocks), Sample Tool: exec, Sample Tool: report_completion (+10 more)

### Community 1 - "Prephase & Task Load"
Cohesion: 0.14
Nodes (17): DIFF: context tool present (absent in our agent), DIFF: stat tool present (absent in our agent), Sample: HarnessServiceClientSync, Sample: main.py — harness runner, Sample: must-phase — 3 fixed calls (tree + AGENTS.MD + context), Sample: NextStep (Pydantic union schema), Sample: run_agent() — main loop, Sample Tool: context (+9 more)

### Community 2 - "Wiki Knowledge System"
Cohesion: 0.23
Nodes (15): Error: Missing /proc/catalog reference in answer, Error: No answer provided (model silent), FIX-345: report_completion blocked — no vault discovery, Prephase: Vault Explorer, Prephase Load: Medium (100-2000 reads), Prephase Load: Small (<100 catalog reads), t01 | score=0.0 | GRADING_FAIL | reads=12, t02 | score=1.0 | OK | reads=102 (+7 more)

### Community 3 - "Context Overflow Failures"
Cohesion: 0.24
Nodes (10): KEY DIFF: Native OpenAI structured outputs (not JSON text gen), Ollama (local fallback), qwen3.5:397b-cloud (classifier/evaluator/builder/wiki), qwen3.5:cloud (executor, 10 tasks), Task Classifier (DSPy/LLM), LLM Dispatcher, Model Router, Sample: dispatch() — tool routing (+2 more)

### Community 4 - "LLM Models & Dispatch"
Cohesion: 0.43
Nodes (8): KEY DIFF: must-phase = 3 fixed reads (no catalog bulk-load), Error: Context Window Overflow (>262K tokens), FIX CANDIDATE: Replace bulk prephase with on-demand tool calls (sample pattern), Prephase Load: Large (>9000 reads) → OVERFLOW, Root Cause: Prephase reads 9000+ catalog files → context overflow, t04 | score=0.0 | OUTCOME_ERR_INTERNAL | reads=9207, t08 | score=0.0 | OUTCOME_ERR_INTERNAL | reads=9686, t12 | score=0.0 | OUTCOME_ERR_INTERNAL | reads=9896

### Community 5 - "Contract & Consensus"
Cohesion: 0.33
Nodes (7): Contract: Multi-round consensus (≤3 rounds), Contract: Evaluator role, Contract: Executor role, KEY DIFF: No contract/consensus phase, KEY DIFF: No DSPy (no prompt_builder, evaluator, classifier), Contract Phase: Executor+Evaluator Consensus, Prompt Builder (DSPy)

### Community 6 - "Sample Agent (ecom-py)"
Cohesion: 0.33
Nodes (7): KEY DIFF: No wiki/knowledge graph system, Evaluator (DSPy), Wiki Graph, Wiki Lint, Wiki: errors/lookup fragments (4 tasks failed), Wiki Graph: 19 delta items, 19 node touches, Wiki page: lookup.md (quality=developing)

## Knowledge Gaps
- **19 isolated node(s):** `Security Gates`, `Error: Missing /proc/catalog reference in answer`, `Grading failure`, `Ollama (local fallback)`, `Wiki Graph: 19 delta items, 19 node touches` (+14 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Agent Loop (≤30 steps)` connect `Agent Pipeline (Our)` to `Prephase & Task Load`, `Wiki Knowledge System`, `Context Overflow Failures`, `Contract & Consensus`, `Sample Agent (ecom-py)`?**
  _High betweenness centrality (0.532) - this node is a cross-community bridge._
- **Why does `Prephase: Vault Explorer` connect `Wiki Knowledge System` to `Context Overflow Failures`, `LLM Models & Dispatch`?**
  _High betweenness centrality (0.304) - this node is a cross-community bridge._
- **Why does `Sample: run_agent() — main loop` connect `Prephase & Task Load` to `Agent Pipeline (Our)`, `Context Overflow Failures`?**
  _High betweenness centrality (0.300) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `Agent Loop (≤30 steps)` (e.g. with `PCM Tool: tree` and `PCM Tool: find`) actually correct?**
  _`Agent Loop (≤30 steps)` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `Prephase: Vault Explorer` (e.g. with `Root Cause: Prephase reads 9000+ catalog files → context overflow` and `Prephase Load: Small (<100 catalog reads)`) actually correct?**
  _`Prephase: Vault Explorer` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `Sample: run_agent() — main loop` (e.g. with `Sample Tool: tree` and `Sample Tool: find`) actually correct?**
  _`Sample: run_agent() — main loop` has 11 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Security Gates`, `Error: Missing /proc/catalog reference in answer`, `Grading failure` to the rest of the system?**
  _19 weakly-connected nodes found - possible documentation gaps or missing edges._