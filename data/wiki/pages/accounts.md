## Account Data Retrieval

### Step Sequence — Bulk Account Read

```
1. read: /accounts/acct_NNN.json          → capture: name, account_manager, status, industry
2. repeat for each target acct_NNN        → accumulate records
3. validate expected fields present       → verify schema completeness
```

> No `OUTCOME_OK` marker present in recorded fragments; sequence is *observed, not yet confirmed successful end-to-end.*

---

## Schema Reference

### `/accounts/acct_NNN.json` — Confirmed Fields

| Field | Type | Notes |
|---|---|---|
| `name` | string | Company display name |
| `account_manager` | string | Full name of assigned AM |
| `status` | enum | e.g. `"active"` |
| `industry` | string | e.g. `"healthcare"`, `"manufacturing"`, `"software"`, `"energy"`, `"retail"`, `"finance"`, `"logistics"`, `"professional_services"` |

### Known Account Index (as of 2026-04-22)

| File | Name | Industry |
|---|---|---|
| `acct_001.json` | Nordlicht Health | healthcare |
| `acct_002.json` | Acme Robotics | manufacturing |
| `acct_003.json` | Acme Logistics | logistics |
| `acct_004.json` | Blue Harbor Bank | finance |
| `acct_005.json` | GreenGrid Energy | energy |
| `acct_006.json` | Silverline Retail | retail |
| `acct_007.json` | CanalPort Shipping | logistics |
| `acct_008.json` | Helios Tax Group | professional_services |
| `acct_009.json` | Aperture AI Labs | software |
| `acct_010.json` | Northstar Forecasting | professional_services |

---

## Risks & Pitfalls

- **Non-contiguous IDs**: Do not assume sequential numbering is exhaustive; missing IDs may be deleted or reserved, not absent data.
- **Highly mutable account data**: `acct_001.json` has been observed with three distinct `account_manager` values across tasks on the same date (`"Tanja Frank"` in t34, `"Franziska Busch"` in t13, `"Kai Möller"` in t39). `acct_007.json` was similarly written multiple times in t13 and t24. Always read immediately before use; never cache `account_manager` or any field across tasks.
- **Redundant writes/reads**: t13 wrote `acct_007.json` five times; t34 read `acct_006.json` twice. Implement deduplication guards before issuing file operations.
- **No `OUTCOME_OK` signal yet**: Treat all step sequences as *candidate patterns* until a successful end-to-end run is recorded.
- **Schema drift**: Core four fields confirmed across all sampled records, but additional fields may appear in records not yet sampled.

---

## Insights & Shortcuts

- Accounts directory path is `/accounts/` — no subdirectories observed.
- File naming convention is zero-padded three-digit suffix: `acct_NNN.json`.
- IDs confirmed present: `001`–`010`.
- `status: "active"` seen across all sampled records; filter on this field to exclude inactive accounts before downstream processing.
- `industry` enum values observed: `healthcare`, `manufacturing`, `logistics`, `finance`, `energy`, `retail`, `software`, `professional_services`.
- Multiple accounts may share the same `account_manager`; do not assume AM-to-account is a 1:1 mapping. The `account_manager` field is also subject to frequent mutation — treat it as a point-in-time value only.