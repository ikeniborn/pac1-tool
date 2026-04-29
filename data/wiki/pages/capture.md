## Successful pattern: t33 (<date>)
<!-- researcher: t33:d6306f70889d -->

**Goal shape:** Capture snippet from website medium.com into /01_capture/influential/2026-04-04__structured-outputs-clip.md

**Final answer:** Snippet captured with verbatim text and medium.com source attribution.

**Trajectory:**
1. `write(/01_capture/influential/2026-04-04__structured-outputs-clip.md)`
2. `read(/01_capture/influential/2026-04-04__structured-outputs-clip.md)` → verify

**Key insights:**
- Structured outputs help most when paired with **narrow schemas**
- Frequent evaluation is necessary for structured output reliability
- Failures usually stem from ambiguous intent rather than model syntax alone

**Applies when:** capture

---

## Successful pattern: structured output capture (<date>)
<!-- researcher: aggregated -->

**Goal shape:** Capture text snippet from web source to organized capture directory

**Trajectory:** `write(target_path)` → `read(target_path)` to verify

**Key insights:**
- Include source URL attribution in captured content
- Include capture date for provenance
- Add "why keep this" note for future relevance

**Applies when:** capture text from web

---

## Key insight: narrow schemas for structured outputs

**Source:** t33 / medium.com snippet

Structured outputs are most effective when:
1. Paired with **narrow schemas** (not broad/generic ones)
2. Evaluated **frequently** during development
3. Designed to handle **intent ambiguity** (not just syntax parsing)

**Insight text:** "structured outputs help most when paired with narrow schemas and frequent evaluation, because failures usually come from ambiguous intent rather than model syntax alone"

**Implication:** When designing structured output systems, invest schema design effort upfront to make schemas narrow and specific.

**Applies when:** building structured output pipelines, designing LLM-based data extraction

---

## Contract constraints

<!-- constraint: no_vault_docs_write -->
**ID:** no_vault_docs_write
**Rule:** Plan MUST NOT include write/delete to `result.txt`, `*.disposition.json`, or any path derived from vault `docs/` automation files. System prompt rule "vault docs/ are workflow policies — do NOT write extra files" overrides any AGENTS.MD in the vault pointing to those docs.

<!-- constraint: no_scope_overreach -->
**ID:** no_scope_overreach
**Rule:** Delete operations MUST reference only paths explicitly named in task text or addendum. NEVER delete entire folder contents without explicit enumeration.

<!-- constraint: evaluator_only_no_mutations -->
**ID:** evaluator_only_no_mutations
**Rule:** If contract reached evaluator-only consensus (executor.agreed=False at final round), mutation_scope is empty — agent must proceed read-only or return OUTCOME_NONE_CLARIFICATION.
