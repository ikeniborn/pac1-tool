## Contact Record Access

### File Path Patterns

```
/contacts/cont_<NNN>.json
/contacts/mgr_<NNN>.json
```

### Observed JSON Schema

| Field | Type | Notes |
|---|---|---|
| `id` | string | Matches filename stem (e.g. `cont_007`, `mgr_002`) |
| `account_id` | string | Cross-reference key to accounts store; mirrors numeric suffix (e.g. `mgr_002` → `acct_002`) |
| `full_name` | string | Display name |
| `role` | string | Job title / functional role |
| `email` | string | Primary contact address |

### Known Prefixes

| Prefix | Example | Observed Roles |
|---|---|---|
| `cont_` | `cont_003`, `cont_004`, `cont_005`, `cont_009` | Head of Engineering, Operations Director, Product Manager |
| `mgr_` | `mgr_001`, `mgr_002`, `mgr_003` | Account Manager |

---

## Pitfalls & Risks

- **Truncated reads (persistent, systemic)** — Every observed fragment across all tasks (t14, t16, t17, t21, t26, t35, t39) is cut off mid-value at or within the `email` field. This is not an occasional edge case — treat truncation as the default until proven otherwise. Always verify the closing `}` is present before consuming any field value.
- **Re-read on truncation** — If the closing `}` is absent, re-issue the read before proceeding downstream. Do not interpolate or guess missing field values.
- **NOT_FOUND errors are repeatable** — `cont_006` returned `ERROR NOT_FOUND` on two consecutive reads within t21 (both `NOT_FOUND` and `Code.NOT_FOUND` variants observed). A missing file does not self-heal; do not retry more than once. Log the gap and continue.
- **Stale / conflicting data** — `cont_004` appears in both t14 (`full_name: Lois Maas`, `role: Head of Engineering`) and t17 (`full_name: Roel Boer`, `role: Operations Director`). The same path returned different records on the same date. Always use the most recently read value and treat older cached reads as unreliable.
- **No OUTCOME_OK recorded** — No task fragment across any logged task has confirmed success. All data remains unverified. Do not treat any contact field as authoritative until a complete, successful read is logged with `OUTCOME_OK`.
- **account_id suffix mirrors file suffix** — Observed consistently across `mgr_` prefix records (mgr_001 → acct_001, mgr_002 → acct_002, mgr_003 → acct_003) and `cont_` prefix (cont_003 → acct_003, cont_005 → acct_005, cont_009 → acct_009). Pattern is consistent across all observed records but remains unconfirmed at `OUTCOME_OK` level; do not rely on this shortcut without a verified read.

---

## Pending: Insufficient Data

No proven multi-step sequences or task-type shortcuts can be extracted yet — all fragments contain only single or paired read operations with no outcome markers. Update this page when complete workflow traces (read → verify closure → process → write → `OUTCOME_OK`) are available.