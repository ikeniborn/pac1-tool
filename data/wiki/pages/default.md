## Proven Step Sequences

### Discard Single Thread (OUTCOME_OK)
1. `list /02_distill/threads` → capture current state, verify target exists, note sibling files (watch for identical date prefixes like `2026-03-23__agent-platforms-and-runtime.md` vs `2026-03-23__ai-engineering-foundations.md`)
2. `delete /02_distill/threads/{YYYY-MM-DD__thread-name}.md` → execute precise removal using full filename including descriptor
3. `list /02_distill/threads` → verify target absent, confirm siblings untouched (e.g., parallel date-prefixed files remain)

### Create JSON Invoice (OUTCOME_OK)
1. `list /my-invoices` → verify directory access, confirm README.MD presence
2. `read /my-invoices/README.MD` → obtain required JSON schema (number, account_id, line items array with amount values)
3. `write /my-invoices/{NUMBER}.json` → create with extracted schema, ensuring filename matches invoice number field (alphanumeric like `SR-13` or `2026-001`); total is computed from line item sum

### Bulk Removal of Cards and Threads (OUTCOME_OK)
1. `list /02_distill/cards` → inventory all files, identify captured content vs scaffold (underscore-prefixed templates)
2. `list /02_distill/threads` → inventory all files, identify captured content vs scaffold
3. `delete /02_distill/cards/{file-1}`, `{file-2}`... → sequential targeted deletion of specific captured files
4. `delete /02_distill/threads/{file-1}`, `{file-2}`... → sequential targeted deletion of specific captured files  
5. `list /02_distill/cards` → verify only scaffold files remain (e.g., `_card-template.md`)
6. `list /02_distill/threads` → verify only scaffold files remain (e.g., `_thread-template.md`)

## Key Risks and Pitfalls

- **Similar filename collision**: Directory may contain files with identical date prefixes; concrete example: `2026-03-23__agent-platforms-and-runtime.md` vs `2026-03-23__ai-engineering-foundations.md` — substring matching risks wrong-file deletion; full filename including descriptor is mandatory
- **Scope violation**: Instruction "don't touch anything else" prohibits wildcard patterns or cleanup of derived assets; collateral damage constitutes failure
- **Silent deletion failures**: Filesystems may return success for non-existent paths; post-deletion verification via `list` is mandatory, not optional
- **Scaffold contamination**: Bulk removal of "all captured files" risks destruction of infrastructure templates (e.g., `_card-template.md`, `_thread-template.md`) or failure to delete actual content if templates are mistaken for content boundaries; explicit per-file targeting is required
- **Schema unread dependency**: Creating JSON invoices without reading README.MD produces malformed documents incompatible with downstream processors; total field is computed from line item sums, not manually specified

## Task-Type Specific Insights and Shortcuts

- **Thread path convention**: `/02_distill/threads/YYYY-MM-DD__{kebab-case-descriptor}.md`
- **Cards path convention**: `/02_distill/cards/YYYY-MM-DD__{kebab-case-descriptor}.md` (parallel structure to threads)
- **Invoice path convention**: `/my-invoices/{NUMBER}.json` where NUMBER is alphanumeric (e.g., `SR-13`, `2026-001`) and matches the internal "number" field; content schema governed by `/my-invoices/README.MD`
- **Invoice line item structure**: Each line item includes descriptive text and numeric amount; total is derived from sum of line items (e.g., 20 + 20 = 40)
- **Verification discipline**: Second `list` operation serves as diff against initial state; absence of target + presence of all previously seen siblings = proof of correct execution; applies per directory in multi-directory operations
- **Explicit targeting rule**: Always use full filename including date prefix and descriptor; never rely on partial matching when "don't touch anything else" constraint applies
- **Scaffold preservation rule**: Files prefixed with underscore (e.g., `_template.md`) are directory infrastructure; exclude from deletion when instructed to remove "captured" content only
- **Cross-directory atomicity**: When clearing both cards and threads simultaneously, treat each directory as a separate scope requiring independent inventory and verification; do not assume symmetry