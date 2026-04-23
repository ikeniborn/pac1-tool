## Temporal Calculations

### Proven Step Sequences

#### Date Arithmetic (OUTCOME_OK)
1. Identify the anchor date from system context (`currentDate`).
2. Apply the offset using calendar arithmetic (no library required for simple day offsets).
3. Return result in the requested format (e.g., `YYYY-MM-DD`).

**Example:** `2026-04-22 + 5 days = 2026-04-27`

---

### Key Risks & Pitfalls

- **Month/year boundary overflow:** Adding days near end-of-month or end-of-year requires carrying over correctly (e.g., April 28 + 5 = May 3, not April 33).
- **Ambiguous "today":** Always source the anchor date from the authoritative `currentDate` context value — never infer from model training data.
- **Format drift:** Confirm output format before responding; `YYYY-MM-DD` ≠ `MM/DD/YYYY` ≠ natural language.

---

### Task-Type Insights & Shortcuts

- For offsets ≤ 28 days within the same month, simple addition suffices; verify only against month length.
- For cross-month or cross-year offsets, enumerate month lengths or use modular day-of-year arithmetic.
- When the task says "Answer only YYYY-MM-DD," omit all prose — return the bare date string.
