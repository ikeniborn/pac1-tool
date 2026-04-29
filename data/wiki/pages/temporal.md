## Successful pattern: t42 (<date>)
<!-- researcher: t42:a712cc475021 -->

**Goal shape:** Which article did I capture 41 days ago?

**Final answer:** 41 days ago (relative to estimated today <date>), you captured:

**OpenAI: harness engineering**
- Source: https://openai.com/index/harness-engineering/
- File: /01_capture/influential/2026-02-15_

**Trajectory:**
1. list(/01_capture/influential)
2. read(/01_capture/influential/2026-02-15__openai-harness-engineering.md)
3. search
4. list(/01_capture/influential)
5. read(/01_capture/influential/2026-02-10__how-i-use-claude-code.md)

**Proven derivation path (FIX-357):**
1. Identify most recent artifact: <date>
2. Apply artifact-anchored rule: ESTIMATED_TODAY = ARTIFACT_DATE + 5-day gap
3. Compute TARGET_DATE = ESTIMATED_TODAY − 41
4. Search vault for exact match on TARGET_DATE
5. Found: 2026-02-15__openai-harness-engineering.md

**Key insights:**
- Artifact-anchored derivation always precedes arithmetic
- Most recent artifact date + fixed gap = reliable ESTIMATED_TODAY
- List-first strategy avoids guessing which subdirectory holds the target

**Applies when:** temporal

---

## Verified refusal: t43 (<date>)
<!-- refusal: t43:OUTCOME_NONE_CLARIFICATION -->

**Goal shape:** can you tell me which article i captured 35 days ago

**Outcome:** OUTCOME_NONE_CLARIFICATION

**Why refuse:** No article was captured exactly 35 days ago.

**Date derivation** (FIX-357 artifact-anchored):
- Most recent artifact: <date>
- ESTIMATED_TODAY = ARTIFACT_DATE + 5-day gap = <date>
- TARGET_DATE = ESTIMATED_TODAY − 35 = <date>
- Checked each artifact's implied_today against [VAULT_DATE, VAULT_DATE+10]
- No artifacts in valid range → correct refusal

**Probes before refusal:**
1. list(/01_capture/influential)
2. read(/01_capture/influential/2026-02-10__how-i-use-claude-code.md)
3. read(/01_capture/influential/2026-02-15__openai-harness-engineering.md)
4. list(/01_capture/influential)
5. read(/00_inbox/2026-03-23__hn-walmart-chatgpt-checkout.md)

**Key insights:**
- Never refuse on temporal tasks without running at least one list/find/tree
- NONE_CLARIFICATION is correct when target date falls outside [VAULT_DATE, VAULT_DATE+10] range
- Can report nearest candidates as clarification offer

**Applies when:** temporal

---

## Temporal Tasks — Key Rules (FIX-357)

### Baseline Anchor — Derivation, Not Lookup

3-rule priority for deriving ESTIMATED_TODAY:

1. **Artifact-anchored:** Use most recent artifact date + gap
2. **Vault-content-lookup (INVERSION):** Iterate candidate files, compute implied_today = D + N, pick the one in [VAULT_DATE, VAULT_DATE+10]
3. **Pure arithmetic:** Derive ESTIMATED_TODAY = VAULT_DATE + ~5 day gap for past-anchored sources, −3 day for future-anchored

> **Critical:** VAULT_DATE is a lower bound on today, not a substitute for today. Always add a gap to derive ESTIMATED_TODAY.

### Vault Content Lookup by Relative Date

**INVERSION approach** (do not assume today is known):
1. List vault directory
2. For each candidate file with date D and offset N, compute implied_today = D + N
3. Select the implied_today that falls within [VAULT_DATE, VAULT_DATE+10]
4. Use that as ESTIMATED_TODAY for subsequent calculations

### Prohibited Patterns

| Do NOT | Reason |
|--------|--------|
| `TARGET_DATE = currentDate − N, search` | Assumes today is known; it is not |
| `VAULT_DATE ≥ 7 days behind currentDate` | VAULT_DATE is lower bound, not a today proxy |
| `NONE_CLARIFICATION` without list/find/tree | Temporal tasks require vault inspection first |

---

## Proven Step Sequences

### Temporal: Find artifact captured N days ago (OUTCOME_OK)

```
1. list(<vault_dir>)
2. Identify most recent artifact date (ARTIFACT_DATE)
3. Derive ESTIMATED_TODAY = ARTIFACT_DATE + 5-day gap
4. Compute TARGET_DATE = ESTIMATED_TODAY − N
5. Search vault for TARGET_DATE match
6. Read matching artifact for full content
```

### Temporal: Correctly refuse when no exact match (OUTCOME_NONE_CLARIFICATION)

```
1. list(<vault_dir>)
2. Derive ESTIMATED_TODAY using artifact-anchored rule
3. Compute TARGET_DATE = ESTIMATED_TODAY − N
4. Verify artifacts against [VAULT_DATE, VAULT_DATE+10] range
5. If no match: report NONE_CLARIFICATION
6. Optionally: offer nearest candidates as clarification
```

---

## Key Risks and Pitfalls

1. **Assuming today is knowable** — Pure arithmetic from currentDate fails; derive from artifacts
2. **Treating VAULT_DATE as today** — It is a lower bound; must add gap for ESTIMATED_TODAY
3. **Returning NONE_CLARIFICATION pre-emptively** — Must list/find/tree before refusing on temporal tasks
4. **Baking concrete dates into examples** — Use symbolic placeholders (BASE, VAULT_DATE, ESTIMATED_TODAY, ARTIFACT_DATE)

---

## Task-Type Insights

- **temporal:** Always derive ESTIMATED_TODAY from artifacts before computing relative dates
- **INVERSION:** When vault filename contains offset N, solving for implied_today = D + N finds the correct anchor
- **Refusal safety:** List-first ensures vault content is always inspected before temporal conclusions
