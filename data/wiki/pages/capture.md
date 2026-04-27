## Capture Tasks — Workflow Wiki

### Proven Step Sequence

Applies to `task_type: capture` with `OUTCOME_OK`.

1. **Read changelog** (`/90_memory/agent_changelog.md`) → confirm format before writing
2. **Write capture file** to the exact path specified in the task (under `01_capture/`) → verify `WRITTEN` confirmation
3. **Write distill card** (`/02_distill/cards/<slug>.md`) → link back to the capture file
4. **Update relevant distill thread** (`/02_distill/threads/`) → append a new bullet referencing the capture
5. **Append changelog entry** (`/90_memory/agent_changelog.md`) → one line only, for new artifacts outside `/90_memory/`

> All five steps required for full evaluator approval when a matching distill thread exists.

---

### File Structure Requirements

Every capture file **must** include:

| Frontmatter field | Notes |
|---|---|
| `source_url` | Full URL of the source (e.g. `https://news.ycombinator.com/…`) |
| `captured_date` | ISO-8601 date of capture |
| `tags` | Relevant topic tags |

Body: verbatim snippet, no paraphrasing.

---

### Naming Convention

```
01_capture/<category>/YYYY-MM-DD__<slug>.md
```

- Date prefix matches the **content date** (not necessarily today's date)
- Slug is kebab-case, descriptive of the snippet topic
- Mirror the same slug for the corresponding distill card: `02_distill/cards/YYYY-MM-DD__<slug>.md`

---

### Distill Integration

When a capture relates to an existing distill thread, the full approved sequence expands to include distill writes:

- **Distill card** at `02_distill/cards/<slug>.md` — one card per capture, links to the source capture file
- **Thread update** at `02_distill/threads/<thread-slug>.md` — append one bullet; do not rewrite the thread body
- Read the target thread before writing it to understand current state and append correctly

---

### Key Risks & Pitfalls

- **Missing frontmatter fields** — evaluators explicitly check for `source_url`, `captured_date`, and `tags`; omitting any causes rejection
- **Paraphrasing the snippet** — evaluators require verbatim content; summarising fails validation
- **Skipping the changelog** — writing the capture file alone is insufficient; the changelog append is a required step
- **Wrong target path** — use the path given in the task literally; do not normalise or relocate
- **Omitting distill writes** — if a matching distill thread exists, skipping the card and thread update results in a partial approval at best; evaluators check for both
- **Security-blocked sources** — tasks targeting restricted domains (e.g. `medium.com`, `docs.anthropic.com`, `news.ycombinator.com`) are denied before any file ops; no partial state is left; the pattern signals a domain allowlist constraint; retry with an allowlisted source is safe
- **Incomplete task specifications** — truncated or malformed task input (cut-off snippet text, unfinished task descriptions) triggers `OUTCOME_NONE_CLARIFICATION` before file operations begin; always validate task clarity before execution
- **Query tasks out of scope** — tasks asking 'which capture from N days ago?' with relative date references trigger `OUTCOME_NONE_CLARIFICATION`; this workflow is for write operations only; reformulate with exact ISO dates or reframe as a write task

---

### Shortcuts & Insights

- The changelog format is minimal: one line per meaningful outcome; read it first to match the existing style
- Structured outputs (narrow schemas) pair well with deterministic, small-scope capture workflows — the capture task itself is an example of this pattern in practice
- `01_capture/influential/` is the standard subfolder for externally sourced, high-signal clips
- Reading the target distill thread before writing prevents duplicate bullets and preserves the thread's existing structure
- A single `OUTCOME_DENIED_SECURITY` leaves zero file-system state — safe to retry with an allowlisted source without cleanup

---
