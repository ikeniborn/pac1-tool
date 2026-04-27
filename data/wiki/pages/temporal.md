## Temporal Task — File-System Agent Workflow Wiki

---

## Baseline Anchor — Derivation, Not Lookup

**Today is never a known input. Derive it from vault signals.**

Priority order (highest wins):

1. **Artifact-anchored** — a dated artifact in the current task context (e.g. a file you just created, a log entry) gives `ARTIFACT_DATE = today`.
2. **Vault-content-lookup (INVERT)** — iterate candidate filenames; for each file dated `D` and a relative offset `N`, compute `implied_today = D + N`; pick the candidate where `implied_today ∈ [VAULT_DATE, VAULT_DATE + 10]`. That implied_today is your `ESTIMATED_TODAY`.
3. **Pure arithmetic** — when no inversion candidate resolves cleanly, derive:
   - Past-anchored sources: `ESTIMATED_TODAY = VAULT_DATE + ~5 day gap`
   - Future-anchored sources: `ESTIMATED_TODAY = VAULT_DATE − 3 day gap`

**Never treat `VAULT_DATE` as today.** It is a lower bound. Always add a gap.

**Never use `currentDate` from an external system clock as the anchor** — benchmark today is randomized per run.

---

## Vault Content Lookup by Relative Date

**INVERSION approach** (FIX-357 canonical method):

```
FOR each file with date-prefix D in candidate directories:
    implied_today = D + N          # N = relative offset from task ("14 days ago" → N=14)
    IF implied_today ∈ [VAULT_DATE, VAULT_DATE + 10]:
        ESTIMATED_TODAY = implied_today
        TARGET_FILE = file with prefix D
        RETURN TARGET_FILE
```

- `VAULT_DATE` = the latest date prefix observed across all listed files.
- The window `[VAULT_DATE, VAULT_DATE + 10]` filters out implausible candidates.
- Do **not** compute `TARGET_DATE = currentDate − N` and search for a file — this assumes today is known, which it is not.

**Example (symbolic):**

> Task: "article from 14 days ago"
> Files observed: `…`, `BASE__slug.md`
> Inversion: `implied_today = BASE + 14` → within `[VAULT_DATE, VAULT_DATE + 10]` ✓
> → `ESTIMATED_TODAY = BASE + 14`, answer = `BASE__slug.md`

---

## Proven Step Sequences

### Relative-date article lookup (OUTCOME_OK)

**Task type:** "which article is from N days ago?"

```
1. list /01_capture/influential            → observe all date-prefixed filenames
2. Set VAULT_DATE = max date prefix seen
3. FOR each file D: compute implied_today = D + N
4. Select file where implied_today ∈ [VAULT_DATE, VAULT_DATE+10]
5. If multiple candidates satisfy window, prefer smallest residual |implied_today − (VAULT_DATE + 5)|
6. Return that file as the target
   verify: implied_today is plausible; file prefix matches D
```

**Worked instance (N=14, OUTCOME_OK):**
- Listed `/01_capture/influential` → 5 files, `VAULT_DATE = BASE`
- Candidate `BASE−14__slug.md` → `implied_today = BASE−14 + 14 = BASE` ✓ (within window)
- Returned correct article.

**Worked instance (N=20, boundary case, OUTCOME_OK):**
- Listed `/01_capture/influential` → 5 files, `VAULT_DATE = BASE`
- Candidate `BASE−20__slug.md` → `implied_today = BASE−20 + 20 = BASE` ✓ (within window)
- Window filtering eliminated 4 older/newer candidates from single list operation.
- Returned correct article.
- **Key insight:** N=20 (exact boundary) resolves with single inversion pass; no special handling required.

**Worked instance (N=20, non-zero residual, OUTCOME_OK):**
- Listed `/01_capture/influential` → 5 files, `VAULT_DATE = BASE`
- Candidate `BASE−17__slug.md` → `implied_today = BASE−17 + 20 = BASE+3` ✓ (within window [BASE, BASE+10])
- Window filtering eliminated 4 other candidates from single list operation.
- Returned correct article.
- **Key insight:** Inversion succeeds with non-zero residual when `implied_today` remains within the window. Residual of +3 is valid and reliable.

**Worked instance (N=11, OUTCOME_OK):**
- Listed `/01_capture/influential` → 5 files, `VAULT_DATE = BASE`
- Candidate `BASE−6__intercom-claude-code-platform.md` → `implied_today = BASE−6 + 11 = BASE+5` ✓ (within window, residual = 0)
- Returned correct article.
- **Key insight:** Small N (11 days) resolves cleanly with single inversion pass and perfect residual.

**Worked instance (N=41, OUTCOME_OK):**
- Listed `/01_capture/influential` → 5 files, `VAULT_DATE = BASE`
- Candidate `BASE−41__slug.md` → `implied_today = BASE−41 + 41 = BASE` ✓ (within window, residual = 0 — best fit)
- `ESTIMATED_TODAY = BASE−41+41`; returned correct article.
- **Key insight:** large N (41 days) resolved cleanly via inversion when a matching file existed; no fallback needed.

---

### No-match fallback — gap too large (OUTCOME_NONE_CLARIFICATION)

**Task type:** "article from N days ago" where N is large and no file inverts cleanly.

```
1. list /01_capture/influential            → observe all date-prefixed filenames
2. list /00_inbox (if applicable)          → widen the candidate pool
3. Set VAULT_DATE = max date prefix seen
4. ESTIMATED_TODAY = VAULT_DATE + ~5d gap
5. FOR each file D: compute implied_today = D + N
6. IF no implied_today ∈ [VAULT_DATE, VAULT_DATE+10]:
       Report: no file matches N-day offset; list closest candidates
   DO NOT return NONE_CLARIFICATION without completing steps 1–5
```

**Worked instance (N=30):**
- `VAULT_DATE = BASE`, `ESTIMATED_TODAY = BASE + 5`
- No file `D` satisfies `D + 30 ∈ [BASE, BASE+10]` → honest no-match report with candidate list.

---

## Key Risks and Pitfalls

| Pitfall | Why it fails | Fix |
|---|---|---|
| Using `currentDate` directly as today | Benchmark today is randomized; external clock is wrong anchor | Derive `ESTIMATED_TODAY` from vault signals |
| Computing `TARGET_DATE = currentDate − N` then searching | Assumes today is known | Use INVERSION: iterate files, compute `implied_today = D + N` |
| Treating `VAULT_DATE` as today | It is a lower bound, not today | Always add a gap: `ESTIMATED_TODAY = VAULT_DATE + ~5d` |
| Returning `NONE_CLARIFICATION` before any list/find/tree | Skips derivation entirely | Run at least one directory listing before giving up |
| Baking concrete dates into examples | Wrong anchor for next run | Always use symbolic placeholders: `BASE`, `VAULT_DATE`, `ESTIMATED_TODAY` |
| Applying `VAULT_DATE ≥ 7 days behind currentDate` threshold | Superseded by FIX-357 | Discard; use gap-based derivation unconditionally |
| Skipping `/00_inbox` when influential has no match | Misses captures in other dirs | Always widen candidate pool before reporting no-match |
| Assuming large N will not resolve via inversion | N=41 resolved cleanly with residual=0 | Always run full inversion scan regardless of N magnitude |

---

## Task-Type Specific Insights

### Temporal — Relative Date Lookup

- **Small N (≤ ~20 days):** Inversion reliably resolves to exactly one file in `/01_capture/influential` via window filtering. Single `list` op is sufficient. Tested range: N ∈ {11, 14, 20} all resolve cleanly.
- **Large N (> ~20 days):** Gap between `ESTIMATED_TODAY` and target date may predate the oldest vault file. After exhausting inversion, report closest candidates rather than silently failing. However, large N can still resolve cleanly (e.g. N=41, residual=0) if a matching file exists — always attempt full inversion before declaring no-match.
- **Tiebreaking multiple plausible inversions:** If two files both satisfy the window, prefer the one with the smaller residual `|implied_today − VAULT_DATE − 5|`. A residual of 0 is a perfect fit.
- **Residuals within window are acceptable:** Non-zero residuals (e.g., +3 days) yield valid matches when `implied_today ∈ [VAULT_DATE, VAULT_DATE+10]`. Window selectivity filters effectively even with offsets. Perfect residuals (0) signal ideal fits but are not required.
- **Inbox vs. influential:** Captures in `/00_inbox` use the same date-prefix convention; include in candidate pool when influential yields no match.
- **Never report `NONE_CLARIFICATION` on temporal tasks** without first running at least one `list`/`find`/`tree` — the vault always contains derivable signals.
- **Window selectivity:** The filter `[VAULT_DATE, VAULT_DATE+10]` consistently narrows 5+ candidate files to 0–1 matches, demonstrating high selectivity. This robustness holds across the tested N range (11, 14, 20, 41).

---
