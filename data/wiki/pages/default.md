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
