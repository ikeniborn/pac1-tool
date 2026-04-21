## Proven Step Sequences

### Capture to Influential Directory
1. **Read process definition**: Check `/99_process/document_capture.md` to confirm item qualifies for "capture" (worth keeping) vs. inbox
2. **List destination**: `list /01_capture/influential` to verify existing files and naming patterns
3. **Write with frontmatter**: Create file using pattern `YYYY-MM-DD__kebab-case-description.md` with YAML frontmatter containing `origin`, `status`, and `handling` fields
4. **Verify persistence**: Re-list destination directory to confirm file appears in index

### Capture-to-Distill Flow
1. **Write capture file** with proper frontmatter at `/01_capture/influential/`
2. **Read existing thread** at `/02_distill/threads/` to identify relevant context
3. **Create distill card** at `/02_distill/cards/` extracting key concepts from capture
4. **Link card into thread** to establish capture→distill lineage

## Key Risks and Pitfalls

- **Frontmatter omission**: Missing required frontmatter fields breaks document provenance and searchability
- **Frontmatter field inconsistency**: Using non-standard field names (e.g., `source_url` instead of `origin`) causes metadata mismatches with expected tooling patterns
- **Path confusion**: Writing high-value captures to `/00_inbox/` instead of `/01_capture/influential/` prevents proper archiving per process criteria
- **Naming collisions**: Using inconsistent date formats (e.g., missing leading zeros) risks filename collisions; strict `YYYY-MM-DD__` prefix required
- **Process drift**: Skipping read of `/99_process/document_capture.md` leads to misclassification of capture vs. transient items
- **URL mismatches**: `origin` or `source_url` in frontmatter must match the actual captured source; breaks traceability when copy-pasted incorrectly

## Task-Type Specific Insights (Capture)

- **Canonical reference**: `/99_process/document_capture.md` is the source of truth for capture criteria—reference when unclear if content belongs in inbox or influential
- **Directory semantics**: `/01_capture/influential/` is for high-signal reference material; use `/00_inbox/` only for unprocessed transient items
- **Filename as metadata**: The `date__slug` pattern serves as primary organization; contents should be in kebab-case to match existing index (e.g., `2026-02-15__openai-harness-engineering.md`)
- **Atomic verification**: Directory listing before and after write operations is the lightweight confirmation pattern for filesystem state transitions
- **Source date vs. task date**: Filename date reflects content source date (e.g., `2026-04-04__agent-evals-notes` for article published that day), not execution date (`2026-04-21`)—prioritize source chronology over action timestamp
- **Standardized frontmatter**: Observed pattern uses `origin` (source identifier), `status` (processing state), and `handling` (routing action) fields—maintain exact field names for tooling compatibility
- **Capture triggers distill**: A successful capture often spawns follow-up distill work; expect to create `/02_distill/cards/` and link into `/02_distill/threads/` as part of complete capture workflow
- **Thread linkage**: After capturing, read existing threads before writing distill artifacts; linking cards into threads maintains the thread's value as a conceptual anchor
- **Frontmatter read-back verification**: After writing, read the file back to confirm frontmatter renders correctly and content is intact—catches encoding or truncation issues early
- **Snippet captures from documentation**: Use blockquote formatting for captured quotes; include source attribution in content body; date in filename reflects source date not execution date (e.g., `2026-04-04__prompting-review-snippet.md` for docs.anthropic.com content)
- **Clip captures**: Use `-clip.md` suffix when capturing partial content rather than full documents (e.g., `structured-outputs-clip.md`)