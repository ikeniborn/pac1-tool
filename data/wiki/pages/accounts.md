## Do NOT Mutate Fields the Task Didn't Name

## Proven Step Sequences (OUTCOME_OK)

### Account Follow-up Date Update

1. **READ** target account JSON file
2. **WRITE** only the named field(s) requiring update
3. **READ** again to verify write success

```
Example: t32 updated next_follow_up_on from <date> → <date>
```

### Bulk Account Reading (Reference Tasks)

- When tasked with "read multiple accounts," each file is independent
- No writes expected; outcome is informational (OUTCOME_OK if all reads succeed)
- Example: t38 read <account> through <account> without modifications

### Single-Account Field Updates

- Narrow scope tasks (e.g., "update follow-up date") succeed by limiting writes to one field
- Reading before writing is mandatory to preserve unchanged fields
- Verification read after write confirms integrity

### Reschedule Task Behavior

- Rescheduled tasks may encounter updated account data (new dates, different manager assignments)
- Do not interpret a changed `account_manager` as evidence of a task to "fix" the value
- Trust the task's named fields only

## Key Risks and Pitfalls

### Pitfall: Reschedule Tasks Should Not Rewrite account_manager

- When a task reads an account file and finds a different `account_manager` value than expected, the agent must not assume the task is to "correct" it
- Reschedule tasks may legitimately land on different data snapshots; the field-diff check only compares named fields
- **Action:** Only write fields explicitly named in the task. Leave all other fields unchanged.

### Pitfall: Stale vs. Current Data Reads

- Multiple reads of the same account (e.g., <account> in t14) can return identical or different JSON depending on whether another agent wrote in between
- **Action:** If reads differ, check timestamps. If no recent write occurred, prefer the later-dated read.

### Pitfall: Compliance Flags Are Informational Only

- Flags like `security_review_open`, `dpa_required`, `external_send_guard`, and `privacy_sensitive` indicate external review states
- Agents must not promise or imply these reviews are "approved" in outbound communications
- **Action:** Treat compliance-flagged accounts as having pending external dependencies. Keep outbound language conservative.

### Pitfall: Duplicate Reads Waste Cycles

- t14 read <account> twice consecutively with identical results
- t35 read <account> twice consecutively with identical results
- t32 performed a redundant third read after verification confirmed success
- **Action:** After a successful write + verification read, do not re-read unless the task explicitly requires it

## Task-Type Specific Insights

### Bulk Account Reading (Reference Tasks)

- When tasked with "read multiple accounts," each file is independent
- No writes expected; outcome is informational (OUTCOME_OK if all reads succeed)
- Example: t34 read <account> and <account> in sequence; t38 read multiple accounts without modifications

### Single-Account Field Updates

- Narrow scope tasks (e.g., "update follow-up date") succeed by limiting writes to one field
- Reading before writing is mandatory to preserve unchanged fields
- Verification read after write confirms integrity

### Reschedule Task Behavior

- Rescheduled tasks may encounter updated account data (new dates, different manager assignments)
- Do not interpret a changed `account_manager` as evidence of a task to "fix" the value
- Trust the task's named fields only

### Same Account Reads Across Tasks Reveal Data Evolution

- <account> read in t14 showed account_manager "Martin Herzog" and next_follow_up_on "<date>"
- Same account read in t26 showed account_manager "Kim Bender" and next_follow_up_on "<date>"
- <account> read in t19 showed account_manager "Maximilian Becker"; read in t38 showed "Johannes Krüger"
- **Insight:** When the same account is read across multiple tasks, expect that field values (especially account_manager, dates, and notes) may differ based on when the task ran and what data was current at that time.

### Compliance Flag Variety Across Accounts

- t36 (Nordlicht Health) showed `dpa_required`
- t35 and t39 (Blue Harbor Bank) showed `nda_signed`, `security_review_open`, `external_send_guard`
- t14 and t26 (Aperture AI Labs) showed `ai_insights_subscriber`, `security_review_open`
- **Insight:** Different compliance flags exist; each account may have unique combinations. Conservative outbound language applies regardless of which flags are present.

```json
{"graph_deltas": {
  "new_insights": [
    {"text": "Same account across tasks shows changed field values; trust named task fields only", "tags": ["data_consistency"], "confidence": 0.7},
    {"text": "Compliance flags vary by account: dpa_required, nda_signed, security_review_open, external_send_guard all require conservative language", "tags": ["compliance"], "confidence": 0.6}
  ],
  "new_rules": [],
  "antipatterns": [
    {"text": "Redundant read after successful verification write wastes cycles without adding value", "tags": ["efficiency"]}
  ]
}
```
