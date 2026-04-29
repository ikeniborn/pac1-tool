## Verified Patterns: File-System Agent Workflow

---

### Successful pattern: Capture–Distill–Delete Inbox Item

**Goal shape:** Capture an inbox item to `/01_capture/`, distill to `/02_distill/cards/`, link into threads, and delete the original.

**Final answer:** Source captured, distill card created, linked into 2 threads, inbox file deleted.

**Trajectory (minimal):**
1. `list(/00_inbox)` → locate source file
2. `read(/00_inbox/{file})` → ingest content
3. `list(/02_distill/threads)` → find threads to link into
4. `write(/01_capture/{...})` → store raw capture
5. `write(/02_distill/cards/{...})` → create distill card
6. `read(/02_distill/threads/{thread})` → load thread
7. `write(/02_distill/threads/{thread})` → append card link
8. `delete(/00_inbox/{file})` → remove from inbox

**Stop condition:** The `delete` call marks task completion. Do not re-read or re-list afterward.

**Key insight:** Stalling after deletion is a known trap. The agent continues reading the now-nonexistent file and listing directories, apparently expecting more work. After deleting, stop immediately.

**Applies when:** default / inbox processing

---

### Successful pattern: Create Structured JSON Record

**Goal shape:** Create a typed record (e.g., invoice) with specific fields.

**Trajectory:**
1. `list(dir)` → locate directory
2. `read(dir/README.MD)` → get schema and invariants
3. `write(dir/NAME.json)` → create record per schema
4. `read(dir/NAME.json)` → verify write success
5. `list(dir)` → confirm file appears

**Key insight:** Always read the README/schema first. JSON schemas encode required fields, field types, and invariants (e.g., total must equal sum of line amounts). Verify by reading back.

**Applies when:** creating JSON records with schema

---

### Successful pattern: Fix Prefix Regression in Downstream Emitter

**Goal shape:** Correct a drifted ID prefix so downstream processing aligns with historical data.

**Trajectory:**
1. `read(audit.json)` → impact context only (do not use for fix direction)
2. `read(processing/README.MD)` → determine which lane is downstream
3. `read(lane_a.json)` → identify `traffic: "downstream"` emitter
4. `read(lane_b.json)` → confirm `traffic: "shadow"` lane (irrelevant to fix)
5. `read(purchases/{historical}.json)` → establish correct established prefix
6. `write(lane_a.json)` → correct prefix in downstream emitter only
7. `read(lane_a.json)` → verify fix

**Key insight:** Use historical purchase records—not planning files or audit logs—to determine the established prefix. Historical records are stable once written; never rewrite them.

**Applies when:** fixing configuration regressions

---

### Refusal pattern: Ambiguous Task Language

**Goal shape:** Any task with truncated or ambiguous terms.

**Outcome:** OUTCOME_NONE_CLARIFICATION

**Why refuse:** Clarification needed on ambiguous term(s). Do not guess at truncated words like "upd."

**Applies when:** default

---

## Key Risks and Pitfalls

- **Post-deletion stalling:** After completing deletions, the agent re-reads the deleted file (which no longer exists) and re-lists directories. This causes stall escalation. Stop immediately after `delete`.
- **Using audit/planning files for fix direction:** `audit.json` provides context for impact scope, not fix direction. For regressions, establish ground truth from historical records.
- **Fixing shadow lanes:** The shadow lane (lane_b) is irrelevant to the regression; fix only the downstream emitter.
- **Listing sibling directories after work completion:** After completing an operation on a scoped set, do not list adjacent directories to check for more work.

---

## Task-Type Specific Shortcuts

| Task type | Shortcut |
|-----------|----------|
| Inbox capture | `delete` = completion signal; stop after |
| Structured record creation | Schema in README; read first, verify by reading back |
| Prefix regression fix | Historical records = ground truth; README identifies owner lane |

---

## Successful pattern: t10 (2026-04-29)
<!-- researcher: t10:668ca6ee301b -->

**Goal shape:** Create invoice SR-13 with 2 lines: 'OpenAI Subscription' - 20, 'Claude Subscription' - 20

**Final answer:** Invoice SR-13 created successfully with 2 line items (OpenAI Subscription: 20, Claude Subscription: 20) totaling 40.

**Trajectory:**
1. read(/my-invoices/README.MD)
2. list(/my-invoices)
3. write(/my-invoices/SR-13.json)
4. read(/my-invoices/SR-13.json)

**Key insights:**
- (none)

**Applies when:** default

## Successful pattern: t01 (2026-04-29)
<!-- researcher: t01:56410e0ac633 -->

**Goal shape:** Let's start over. Remove all captured cards and threads. Do not touch anything else

**Final answer:** All captured cards and threads removed from /02_distill/. Templates left untouched. Nothing else touched.

**Trajectory:**
1. list(/02_distill/cards)
2. list(/02_distill/threads)
3. delete(/02_distill/cards/2026-02-10__how-i-use-claude-code.md)
4. delete(/02_distill/cards/2026-02-15__openai-harness-engineering.md)
5. delete(/02_distill/cards/2026-03-06__anthropic-biology-of-llms.md)
6. delete(/02_distill/cards/2026-03-17__intercom-claude-code-platform.md)
7. delete(/02_distill/cards/2026-03-23__hn-structured-outputs-practical-notes.md)
8. delete(/02_distill/threads/2026-03-23__agent-platforms-and-runtime.md)
9. delete(/02_distill/threads/2026-03-23__ai-engineering-foundations.md)

**Key insights:**
- (none)

**Applies when:** default

## Successful pattern: t03 (2026-04-29)
<!-- researcher: t03:40b00e529e52 -->

**Goal shape:** Take 00_inbox/2026-03-23__hn-reports-of-codes-death.md from inbox, capture it into into 'influental'

**Final answer:** Inbox item processed successfully: source captured verbatim to /01_capture/influential/2026-03-23__hn-reports-of-codes-death.md, distill card created at /02_distill/cards/2026-03-23__hn-reports-of-cod

**Trajectory:**
1. read(/00_inbox/2026-03-23__hn-reports-of-codes-death.md)
2. list(/02_distill/threads)
3. write(/01_capture/influential/2026-03-23__hn-reports-of-codes-death.md)
4. write(/02_distill/cards/2026-03-23__hn-reports-of-codes-death.md)
5. read(/02_distill/threads/2026-03-23__agent-platforms-and-runtime.md)
6. write(/02_distill/threads/2026-03-23__agent-platforms-and-runtime.md)
7. read(/02_distill/threads/2026-03-23__ai-engineering-foundations.md)
8. write(/02_distill/threads/2026-03-23__ai-engineering-foundations.md)
9. delete(/00_inbox/2026-03-23__hn-reports-of-codes-death.md)
10. list(/01_capture/influential)
11. read(/02_distill/cards/2026-03-23__hn-reports-of-codes-death.md)
12. read(/02_distill/threads/2026-03-23__agent-platforms-and-runtime.md)
13. read(/02_distill/threads/2026-03-23__ai-engineering-foundations.md)
14. list(/01_capture/influential)
15. list(/02_distill/cards)
16. stall
17. stall
18. read(/01_capture/influential/2026-03-23__hn-reports-of-codes-death.md)
19. stall
20. stall
21. read(/02_distill/threads/2026-03-23__agent-platforms-and-runtime.md)
22. stall
23. stall
24. read(/01_capture/influential/2026-03-23__hn-reports-of-codes-death.md)
25. stall

**Key insights:**
- (none)

**Applies when:** default

## Successful pattern: t31 (2026-04-29)
<!-- researcher: t31:923860fb4450 -->

**Goal shape:** Fix the purchase ID prefix regression and do whatever cleanup is needed so downstream processing wor

**Final answer:** Fixed purchase ID prefix regression. Downstream emitter lane_a.json corrected to use 'prc-' prefix matching historical records. lane_b.json unchanged. cleanup-plan.json has no active cleanup tasks.

**Trajectory:**
1. read(/docs/purchase-id-workflow.md)
2. read(/purchases/audit.json)
3. read(/processing/README.MD)
4. read(/processing/lane_a.json)
5. read(/processing/lane_b.json)
6. read(/purchases/100000.json)
7. stall
8. read(/purchases/100001.json)
9. stall
10. read(/processing/cleanup-plan.json)
11. stall
12. write(/processing/lane_a.json)
13. read(/processing/lane_a.json)
14. read(/processing/lane_a.json)
15. read(/purchases/100000.json)
16. read(/processing/lane_a.json)

**Key insights:**
- (none)

**Applies when:** default
