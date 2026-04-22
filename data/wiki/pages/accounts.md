## Account Data Retrieval

### Step Sequence — Bulk Account Read

```
1. read: /accounts/acct_NNN.json          → capture: name, account_manager, status, industry
2. repeat for each target acct_NNN        → accumulate records
3. validate expected fields present       → verify schema completeness
```

> No `OUTCOME_OK` marker present in current fragments; sequence is *observed, not yet confirmed successful end-to-end.*

---

## Schema Reference

### `/accounts/acct_NNN.json` — Confirmed Fields

| Field | Type | Notes |
|---|---|---|
| `name` | string | Company display name |
| `account_manager` | string | Full name of assigned AM |
| `status` | enum | e.g. `"active"` |
| `industry` | string | e.g. `"healthcare"`, `"manufacturing"`, `"software"` |

---

## Risks & Pitfalls

- **Non-contiguous IDs**: Files jump from `acct_002` to `acct_009` — do not assume sequential numbering is exhaustive; missing IDs may be deleted or reserved, not absent data.
- **No `OUTCOME_OK` signal yet**: Treat this step sequence as a *candidate pattern* until a successful end-to-end run is recorded.
- **Schema drift**: Fields confirmed only for three records; additional or renamed fields may appear in other account files.

---

## Insights & Shortcuts

- Accounts directory path is `/accounts/` — no subdirectories observed.
- File naming convention is zero-padded three-digit suffix: `acct_NNN.json`.
- `status: "active"` seen across all sampled records; filter on this field to exclude inactive accounts before downstream processing.