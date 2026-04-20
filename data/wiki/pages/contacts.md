## Contact Lookup and Disambiguation

### Proven Step Sequences
1. **Direct File Access**: Retrieve contact object from `/contacts/{contact_id}.json`
2. **Account Link Verification**: Extract `account_id` field and immediately fetch corresponding account record
3. **Metadata Sync Check**: Compare file system values (role, name) against any cached index entries to identify drift
4. **Identity Confirmation**: When names overlap, use email domain and `account_id` correlation to distinguish candidates

### Key Risks

**Multiple Candidate Resolution**
Same display names may map to different individuals across accounts. Disambiguate using email domain validation and account ownership chains rather than relying solely on `full_name` matches.

**Stale Cache Divergence**
Index summaries (role, last_seen timestamps) frequently lag behind source file updates. Treat cached metadata as hints, not ground truth.

**Email Domain Mismatches**
Contact email addresses may use personal domains or alias domains that differ from primary account domains. Flag mismatches for verification before proceeding.

### Workflow Insights

**Always Read Account After Contact**
Contact records contain foreign key references (`account_id`) that must be validated against the parent account file. This confirms organizational context, active status, and prevents operations on orphaned or transferred contacts.

**Name Variation Handling**
Expect `full_name` fields in JSON files to contain complete legal names, while indexes and task references may use nicknames or shortened forms. Validate through ID linkage rather than string matching.

**File Path Convention**
Contact records reside at `/contacts/cont_{NNN}.json` using zero-padded numeric identifiers.