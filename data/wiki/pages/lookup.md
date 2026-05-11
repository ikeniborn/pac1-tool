<!-- wiki:meta
category: lookup
quality: developing
fragment_count: 6
fragment_ids: [t02_20260511T112721Z, t03_20260511T112348Z, t05_20260511T113240Z, t09_20260511T113028Z, t10_20260511T112443Z, t11_20260511T113733Z]
last_synthesized: 2026-05-11
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
*   **Specific Product Lookup**
    *   Combine Brand, Product Line, and technical attributes (e.g., wattage, fitting, color, storage type) for precise queries.
    *   Verify catalogue existence using read-only filters; do not modify records.
    *   Supported attributes include luminous flux, adhesive type, control method, and color family.
*   **Category Counting**
    *   Query catalogue by product category (e.g., Wall Paint, Lawn Mower, Cordless Drill Driver).
    *   Return integer results strictly in the format `<COUNT:n>`.
    *   Ensure query type is `lookup` to maintain read-only status.
*   **General Data Retrieval**
    *   Chain multiple attribute filters to narrow result sets before counting.
    *   Confirm `OUTCOME_OK` on lookup tasks to validate successful read access.
    *   Avoid any write operations during finding, counting, or querying processes.

## Key pitfalls
*   **Lookup Without Operations:** Tasks may return `OUTCOME_OK` while `DONE OPS` remains `(none)`, indicating the agent skipped file-system commands.
*   **False Matches:** Product existence (e.g., Milwaukee Tool Box, Loctite Adhesive, Philips LED Bulb) may be asserted without verifying via `list`, `find`, or `tree`.
*   **Wrong Filters:** Specific attributes (storage type, adhesive type, wattage, luminous flux, fitting, color family) may be assumed incorrectly without catalogue inspection.
*   **Premature NONE_CLARIFICATION:** Agents risk finalizing clarification status before running discovery commands, particularly evident in category count queries (Wall Paint, Lawn Mower, Cordless Drill Driver).
*   **Verification Skip:** Success confirmation should not occur prior to executing search operations to prevent hallucination of catalogue data and statistics.

## Shortcuts
**Hierarchical Search Strategy**
- Prioritize Brand and Product Line identifiers to narrow scope before filtering attributes.
- Recommended flow: Brand → Product Line → Category → Specific Attributes.
- Example: Milwaukee → Compact HD Q68-SJX → Tool Box → Storage Type.

**Multi-Attribute Filtering**
- Combine technical specifications (wattage, fitting, luminous flux) for precise item matching.
- Apply non-technical filters (color family, adhesive type) concurrently with technical specs.
- Validate attribute values against catalogue schema to ensure exact matches.

**Category Counting Operations**
- Identify queries requesting product counts within a category (e.g., Wall Paint, Lawn Mower).
- Execute aggregate count logic rather than item retrieval for "How many" questions.
- Enforce strict output formatting for count responses (e.g., `<COUNT:n>`).

**Constraint Extraction**
- Parse natural language for explicit constraints (brand, model, specs).
- Differentiate between product line names and general category names during parsing.
- Handle complex multi-attribute queries requiring all conditions to be met.

## Successful pattern: t03 (2026-05-11)
<!-- researcher: t03:e3b0c44298fc -->

**Goal shape:** Do you have the Adhesive and Glue from Loctite in the Loctite Super Glue HY 1BI-ADH Adhesive and Glu

**Final answer:** (unspecified)

**Trajectory:**
1. ?
2. ?
3. ?

**Key insights:**
- (none)

**Applies when:** lookup

## Successful pattern: t10 (2026-05-11)
<!-- researcher: t10:e3b0c44298fc -->

**Goal shape:** How many catalogue products are Lawn Mower? Answer with '<COUNT:n>' exactly.

**Final answer:** (unspecified)

**Trajectory:**
1. ?
2. ?
3. ?

**Key insights:**
- (none)

**Applies when:** lookup

## Successful pattern: t02 (2026-05-11)
<!-- researcher: t02:e3b0c44298fc -->

**Goal shape:** Do you have the Tool Box and Bag from Milwaukee in the Milwaukee Compact HD Q68-SJX Tool Box and Bag

**Final answer:** (unspecified)

**Trajectory:**
1. ?
2. ?
3. ?
4. ?

**Key insights:**
- (none)

**Applies when:** lookup

## Successful pattern: t09 (2026-05-11)
<!-- researcher: t09:e3b0c44298fc -->

**Goal shape:** How many catalogue products are Wall Paint? Answer with '<COUNT:n>' exactly.

**Final answer:** (unspecified)

**Trajectory:**
1. ?
2. ?
3. ?

**Key insights:**
- (none)

**Applies when:** lookup

## Successful pattern: t05 (2026-05-11)
<!-- researcher: t05:e3b0c44298fc -->

**Goal shape:** Do you have the LED Bulb from Philips in the Philips CorePro Ultra 1BQ-MPB LED Bulb line that has wa

**Final answer:** (unspecified)

**Trajectory:**
1. ?
2. ?
3. ?
4. ?
5. ?
6. ?
7. ?
8. ?
9. ?

**Key insights:**
- (none)

**Applies when:** lookup

## Successful pattern: t11 (2026-05-11)
<!-- researcher: t11:e3b0c44298fc -->

**Goal shape:** How many catalogue products are Cordless Drill Driver? Answer with '<COUNT:n>' exactly.

**Final answer:** (unspecified)

**Trajectory:**
1. ?
2. ?
3. ?
4. ?
5. ?
6. ?
7. ?
8. ?

**Key insights:**
- (none)

**Applies when:** lookup
