## Proven Step Sequences

### Account Lookup by Name
1. List `/accounts` to get candidate filenames
2. Read candidate files sequentially until account name matches or industry matches
3. Use `id` field (e.g., `acct_009`) to cross-reference contacts and invoices

### Account via Contact
1. Resolve contact by name or email (see contacts.md)
2. Read `account_id` field from contact record
3. Read `/accounts/acct_{id}.json` for business context

## Key Risks and Pitfalls

- **Account ID does not predict company**: Account IDs (acct_001, acct_009, etc.) are vault-specific and change per randomization. Never assume a specific ID maps to a specific company — always look up by reading the file
- **Industry mismatch**: When searching by description (e.g., "AI insights"), compare the account's `industry` field to narrow candidates
- **Notes/reminders may use different status values**: Account JSON files may have `status: "active"`, `status: "churned"`, etc. — verify actual field content before reporting

## Task-Type Specific Insights

- **Email outreach**: Always read the account (`accounts/acct_{id}.json`) after resolving the contact — it provides the business context (company name, industry) needed for accurate outreach emails and must be included in grounding_refs
- **Invoice lookup**: Use `account_id` from the account file to filter `/my-invoices/` — do not rely on filenames alone
- **CRM reschedule**: Both the account's `next_follow_up_on` field and the reminder's date field must be updated when rescheduling follow-ups

