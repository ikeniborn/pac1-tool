## Proven Step Sequences

### Create JSON Invoice (OUTCOME_OK)
1. `read /my-invoices/README.MD` → obtain required JSON schema (number, account_id, line items array with amount values)
2. `write /my-invoices/{NUMBER}.json` → create with extracted schema, ensuring filename matches invoice number field (e.g., `SR-13`); total computed from line item sum (e.g., $20 + $20 = $40)

### Discard Single Thread (OUTCOME_OK)
1. `list /02_distill/threads` → capture current state, verify target exists, note sibling files
2. `delete /02_distill/threads/{YYYY-MM-DD__thread-name}.md` → execute precise removal using full filename including descriptor
3. `list /02_distill/threads` → verify target absent, confirm siblings untouched; optionally read a sibling to confirm it wasn't modified

### Fix Purchase ID Prefix Regression (OUTCOME_OK)
1. `read /purchases/audit.json` → obtain workflow guidance and `drift_started_after` timestamp
2. `read /purchases/{sample-ID}.json` → establish expected prefix baseline from production data (e.g., `purchase_id: "prc-100277"`)
3. `read /processing/lane_a.json` → identify active emitter prefix drift (e.g., `"prefix": "purchase-"`)
4. `read /processing/lane_b.json` → confirm it is shadow only, not affecting downstream
5. `read /processing/cleanup-plan.json` → verify `rewrite_historical_ids: false` before proceeding
6. `read /processing/README.MD` → confirm lane roles (active vs shadow)
7. `write /processing/lane_a.json` → correct `prefix` field to match baseline (`"prc-"`)
8. `read /processing/lane_a.json` → post-fix verification of corrected configuration

**Optional**: `read /docs/purchase-id-workflow.md` → supplementary workflow reference for prefix investigation

### Bulk Removal of Cards and Threads (OUTCOME_OK)
1. `list /02_distill/cards` → inventory all files, identify captured content vs scaffold (`_card-template.md`)
2. `list /02_distill/threads` → inventory all files, identify captured content vs scaffold (`_thread-template.md`)
3. `delete /02_distill/cards/{file-1}`, `{file-2}`... → sequential targeted deletion of captured files
4. `list /02_distill/cards` → verify cards cleared; immediately `list /02_distill/threads` to discover remaining work in threads
5. `delete /02_distill/threads/{remaining-file}` → clear any threads discovered during interleaved verification
6. `list /02_distill/threads` → verify only scaffold remains (`_thread-template.md`)
7. `list /02_distill/cards` → final verification only scaffold remains (`_card-template.md`)

## Key Risks and Pitfalls

- **Similar filename collision**: Directory may contain files with identical date prefixes; full filename including descriptor is mandatory
- **Scope violation**: "Don't touch anything else" prohibits wildcard patterns or cleanup of derived assets
- **Silent deletion failures**: Filesystems may return success for non-existent paths; post-deletion verification via `list` is mandatory
- **Scaffold contamination**: Explicit per-file targeting required; underscore-prefixed files (`_card-template.md`, `_thread-template.md`) are directory infrastructure
- **Schema unread dependency**: Creating JSON invoices without reading README.MD produces malformed documents; total field is computed from line item sums
- **Incremental file discovery during interleaved ops**: After deleting from one directory, list the OTHER directory to discover remaining work before assuming completion
- **Historical rewrite policy**: Emitter fixes must verify `rewrite_historical_ids: false` in cleanup-plan.json before proceeding
- **Prefix format drift**: Active emitter configuration must match observed ID patterns in production records; mismatches propagate downstream
- **Shadow lane non-intervention**: lane_b with `"traffic": "shadow"` does not affect downstream; only fix active lane when problem is in downstream emitter
- **Stall warning threshold**: Taking 6+ read-only steps without writing triggers stall warning; minimize read steps by planning ahead

## Task-Type Specific Insights and Shortcuts

- **Thread path convention**: `/02_distill/threads/YYYY-MM-DD__{kebab-case-descriptor}.md`
- **Cards path convention**: `/02_distill/cards/YYYY-MM-DD__{kebab-case-descriptor}.md` (parallel structure to threads)
- **Invoice path convention**: `/my-invoices/{NUMBER}.json` where NUMBER matches internal "number" field; content schema governed by README.MD
- **Invoice line item structure**: Each item includes descriptive text and numeric amount; total derived from sum
- **Verification discipline**: Second `list` serves as diff against initial state; absence of target + presence of siblings = proof of correct execution
- **Explicit targeting rule**: Always use full filename including date prefix and descriptor when scope constraint applies
- **Scaffold preservation rule**: Files prefixed with underscore (`_card-template.md`, `_thread-template.md`) are infrastructure; exclude from deletion when removing "captured" content only
- **Cross-directory atomicity**: Treat each directory as separate scope requiring independent inventory and verification
- **Interleaved verification pattern**: After completing operations in one directory, immediately list the OTHER directory to discover any files missed in initial inventory; then return to complete final verification of first directory
- **Multi-pass bulk deletion**: Bulk cleanup operations may require multiple passes; perform follow-up `list` after initial batch to catch missed files
- **Emitter configuration path**: `/processing/lane_{a,b}.json` controls purchase ID generation; lane_a is active (`"traffic": "downstream"`), lane_b is shadow (`"traffic": "shadow"`)
- **Expected purchase ID prefix**: `prc-` (observed in valid production records like `prc-100277`)
- **Cleanup policy gate**: `/processing/cleanup-plan.json` contains `enabled` and `rewrite_historical_ids` flags; proceed only when `rewrite_historical_ids: false`
- **Audit guidance source**: `/purchases/audit.json` provides `candidate_actions` array and `drift_started_after` timestamp to scope investigation
- **Lane role confirmation**: Read `/processing/README.MD` to verify which lane is active vs shadow before making fixes
- **Post-fix validation**: After writing corrected lane configuration, re-read to verify `prefix` field matches expected value before considering fix complete
- **Purchase workflow reference**: `/docs/purchase-id-workflow.md` exists as supplementary documentation for prefix investigation tasks
- **Minimal fix approach**: When fix scope is clearly established, direct write without reading all supporting docs is viable after core verification steps
- **Inventory asymmetry**: Bulk deletion initial lists may reveal different file counts between directories; interleave verification to catch work remaining in the other directory after completing first directory's operations
- **Deletion batch composition**: Captured content files are eligible for deletion; templates (underscore-prefixed) are always excluded from deletion scope