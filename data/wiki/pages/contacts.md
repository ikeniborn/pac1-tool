## Contact Record Access

### File Path Pattern

```
/contacts/cont_<NNN>.json
```

### Observed JSON Schema

| Field | Type | Notes |
|---|---|---|
| `id` | string | Matches filename stem (e.g. `cont_007`) |
| `account_id` | string | Cross-reference key to accounts store |
| `full_name` | string | Display name |
| `role` | string | Job title / functional role |
| `email` | string | Primary contact address |

---

## Pitfalls & Risks

- **Truncated reads** — Both observed fragments were cut off mid-value (email field incomplete). Always verify the full record was returned before using field values downstream; re-read if the closing `}` is absent.
- **No OUTCOME_OK recorded** — Neither task fragment confirmed task success. Treat data from these reads as unverified until a complete, successful read is logged.

---

## Pending: Insufficient Data

No proven multi-step sequences or task-type shortcuts can be extracted yet — fragments contain only single read operations with no outcome markers. Update this page when complete workflow traces (read → process → write → `OUTCOME_OK`) are available.