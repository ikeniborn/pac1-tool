<!-- wiki:meta
category: errors/temporal
quality: nascent
fragment_count: 3
fragment_ids: [t41_20260430T140645Z, t41_20260430T170111Z, t43_20260430T170316Z]
last_synthesized: 2026-04-30
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
When resolving date-relative queries (e.g., "what day is yesterday?"), the system derives the current date from vault artifacts rather than relying on wall-clock time. The proven sequence involves:

1. **List candidate directories** (e.g., `/reminders`) to identify time-anchored files
2. **Select the newest future-anchored artifact** — an artifact with a date in the future relative to estimated today (e.g., `rem_009.json` with `due_on=<date>`)
3. **Verify anchor validity** — confirm the artifact date is >= `VAULT_DATE_LOWER_BOUND` to ensure reliable calibration
4. **Derive ESTIMATED_TODAY** — compute the gap between the anchor date and the expected date, then apply that offset: `ESTIMATED_TODAY = anchor_date + gap`
5. **Resolve the relative date** — apply the calculated offset (e.g., `yesterday = ESTIMATED_TODAY - 1`)

**Key insight — Candidate file inversion:** When past-anchored artifacts are unavailable or insufficient, invert the search to identify the newest future-anchored artifact. This provides a reliable upper-bound anchor that can be adjusted by its known temporal offset to recover the estimated current date. The gap calculation (`gap = expected_date - anchor_date`) determines the calibration offset to apply across all relative computations.

**Consistent gap calibration:** Empirical evaluation shows the vault's temporal offset remains stable across operations. When ESTIMATED_TODAY is derived from VAULT_DATE with a +5 day gap, this offset holds for subsequent computations in the same session. Verify gap consistency before applying across multiple relative date calculations.

**Cross-directory artifact validation:** When resolving date-relative queries about specific content (e.g., "which article did I capture 6 days ago?"), list multiple artifact directories (e.g., `/00_inbox`, `/01_capture/influential`) to cross-validate the target date. Discrepancies between directories may indicate incomplete coverage requiring fallback behavior.

**Absent target handling:** If no artifact exists on the computed TARGET_DATE, document the nearest alternatives in both directions. The system should report the closest prior capture and note the absence on the exact date rather than failing silently.

**Support file prerequisites:** Certain queries may require reading support files (e.g., `/90_memory/soul.md`) before artifact processing. Treat these as required steps in the resolution sequence, not optional enrichment.

**Validation gate:** Always verify the anchor artifact's date meets the `VAULT_DATE_LOWER_BOUND` threshold before using it for derivation. Artifacts below this bound may not reflect the current vault state.

## Key pitfalls
- **System-clock vs vault-time confusion risk**: When temporal tasks do not provide an explicit `VAULT_DATE` or current date context, the agent must derive temporal state from artifacts. In t41, the task simply asked "what day is yesterday?" with no date provided. The agent explored artifacts (read `/reminders/rem_010.json`, read `/reminders/rem_009.json`) without establishing a temporal anchor first. The evaluator resolved this by identifying the newest future-anchored artifact (rem_009.json, `due_on=<date>`) and computing `ESTIMATED_TODAY=<date>` (gap=-3). Agents should not assume system clock availability or proceed without confirming temporal context. Additional instances (t41, t43) show gap values of +5 days are also used depending on artifact signatures—the agent must compute ESTIMATED_TODAY by comparing the latest artifact date against VAULT_DATE, not assume a fixed offset.

- **Wrong temporal anchor risk**: The agent in t41 listed `/reminders` and read multiple files before attempting temporal reasoning, suggesting it anchored to the wrong context (possibly the most recently read file's due date rather than the logical system date). This led to exploratory behavior that did not contribute to the answer. Temporal anchoring must be resolved immediately upon encountering a date-dependent task, ideally before any file operations. In t43, the agent appropriately anchored to `/00_inbox` for VAULT_DATE when the task referenced captures—demonstrating that the correct temporal anchor depends on which artifact collection the task references; wrong collection choice leads to dead ends.

- **Premature NONE_CLARIFICATION risk**: The agent in t41 issued multiple sequential list and read operations without producing the requested output ("Respond with DD-MM-YYYY only"). It received two stall warnings indicating it had taken 6+ steps without writing, deleting, moving, or creating anything. The agent performed `list: /my-invoices`, `read: /reminders/rem_010.json`, `list: /reminders`, `read: /reminders/rem_009.json` before stalling—listing files rather than first clarifying or resolving the temporal question. This demonstrates that premature list/find/tree operations before resolving temporal anchoring leads to dead ends; the agent should resolve "what is today/yesterday/tomorrow" before iterating over artifact collections. In t43, the agent successfully followed this sequence: list `/00_inbox` to establish VAULT_DATE, read supporting artifacts (soul.md as required), then list capture directories to locate the target—avoiding the deadlock pattern seen in t41.

## Shortcuts
Temporal patterns: VAULT_DATE as lower bound, ESTIMATED_TODAY derivation, candidate inversion (implied_today = file_date + N)

### VAULT_DATE as Lower Bound

The VAULT_DATE (specifically VAULT_DATE_LOWER_BOUND) establishes a temporal floor for artifact selection. When deriving ESTIMATED_TODAY, any candidate artifact must have a date >= VAULT_DATE_LOWER_BOUND. This prevents temporal inversion where an artifact's date falls before the known minimum vault date.

Example: rem_009.json with due_on=<date> satisfies the constraint when VAULT_DATE_LOWER_BOUND=<date>.

**Anchor Discovery:** VAULT_DATE can be derived by scanning directory listings and identifying the newest dated artifact. For example, listing /00_inbox revealed VAULT_DATE=<date> from the most recent inbox entries (t43).

### ESTIMATED_TODAY Derivation

ESTIMATED_TODAY is derived by analyzing temporal artifacts (files with date fields) and calculating the implied current date. The derivation works by identifying anchor artifacts and computing the gap between their date and the true current date.

**Method for future-anchored artifacts:**
1. Identify the newest artifact with a future-relative date (e.g., reminders with due_on dates)
2. Compute gap = artifact_date - ESTIMATED_TODAY (negative gap indicates future-anchored)
3. Verify artifact_date >= VAULT_DATE_LOWER_BOUND
4. Derive ESTIMATED_TODAY = artifact_date - gap

Example from t41: rem_009.json due_on=<date> → ESTIMATED_TODAY=<date> with gap=-3

**Consistent Gap Pattern:** Empirical observation from multiple tasks reveals a consistent +5 day gap between VAULT_DATE and ESTIMATED_TODAY. Both t41 and t43 derived ESTIMATED_TODAY=VAULT_DATE+5days independently, suggesting this gap is stable across operations.

**Temporal Arithmetic:**
- Forward calculation: FUTURE_DATE = ESTIMATED_TODAY + N (e.g., adding 16 days for "what day is in 16 days?" from t41)
- Backward calculation: TARGET_DATE = ESTIMATED_TODAY - N (e.g., subtracting 6 days for "6 days ago" from t43)

### Candidate Inversion (implied_today = file_date + N)

The candidate inversion formula computes the implied current date from file metadata:

**implied_today = file_date + N**

Where:
- file_date: The date extracted from an artifact (e.g., issued_on, due_on)
- N: The temporal offset gap derived from context
- implied_today: The computed current date

This inversion is applied when the artifact is future-anchored (N is negative) or past-anchored (N is positive). The system validates that implied_today remains consistent with VAULT_DATE constraints before accepting it as ESTIMATED_TODAY.
