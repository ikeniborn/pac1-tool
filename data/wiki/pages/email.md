<!-- wiki:meta
category: email
quality: developing
fragment_count: 6
fragment_ids: [t04_20260430T133605Z, t12_20260430T133948Z, t14_20260430T133947Z, t35_20260430T140056Z, t04_20260430T163800Z, t12_20260430T164151Z]
last_synthesized: 2026-04-30
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
- **Contact lookup before compose:** When a task requires email, verify the contact exists in `/contacts/<file> before attempting to compose. Searching vault-wide (or in the root) misses contact JSON files; look inside `/contacts/<file> specifically.
- **Name matching**: Search both full name and individual tokens (`Alex Meyer`, `Alex`, `Meyer`) but expect possible mismatch due to formatting (e.g., `"Alex Meyer"` may not appear literally in any JSON `full_name` field).
- **Known structure:** `/contacts/<file> contains numbered JSON files (`<contact>.json` … `<contact>.json`) plus `mgr_*.json` files and a `README.MD`. Each file has `full_name`, `email`, and `preferred_tone` fields.
- **Efficient search within directory:** Rather than reading every contact file sequentially, search by filename pattern or use directory metadata. Sequential reads across all contacts caused 12+ stall steps in t12 without result.
- **OUTCOME_NONE_CLARIFICATION handling:** If no matching contact is found after thorough search, the task cannot proceed; signal clarification needed rather than continuing to explore unrelated directories.
- **No /outbox/ in this vault:** Verified absence of `/outbox/<file> or `/contacts/<file> structures in the root; contact data lives under `/contacts/<file> and outbox operations may require additional directory creation or different path conventions.

## Key pitfalls
- Ambiguous or missing recipient identifiers cause task abortion. When a task refers to a recipient by an informal or partial name (e.g., "Sam") and no contact file for that person exists, the agent stalls and produces no output. The stall-hint warning shows repeated listing operations without any write, indicating the agent could not resolve the reference.

- Name mismatch between task language and stored contact data. When a task names "Alex Meyer" but contacts store the person under "Alexander Richter," search operations for the exact task name return no matches, even though a partial name search finds the actual record. The agent failed to recognize the alias and gave up after listing the contacts directory rather than bridging the name gap.

- Insufficient contact lookup strategy. The agent in task t12 re-read an already-seen contact file (`/contacts/<file>) to verify structure rather than continuing to search for the target recipient. This indicates a pattern of low-value re-reads when the search query itself should be refined. After failing exact-match searches for "Alex Meyer," "Alex," and "Meyer" across the contacts directory, the agent in t12 switched to exhaustive linear scanning—reading contacts <contact> through <contact> sequentially—without finding the target recipient and without refining its search query or recognizing that the name might exist under a different full name.

- Skipped contact file reads are implicit when the agent stalls or aborts rather than attempting to load a likely contact file. In t04 the agent never listed `/contacts` before stalling, so it never discovered whether a Sam entry existed. The root-level search failed, but a contacts-folder search was never attempted.

- Verification behavior on missing directories. In t04, after failing to find "Maya" with vault-wide search, the agent explicitly verified that `/contacts/<file> and `/outbox/<file> directories do not exist. This shows the agent confirming absence rather than pivoting to alternative resolution paths such as checking inbox entries, project directories for contact references, or other sources where a recipient identifier might appear.

- Exhaustive linear scanning as fallback when searches fail. This behavior produces extended stalls with repeated sequential reads across contact files (<contact> through <contact> in t12) rather than improving the search strategy or triggering clarification.

- Recovery gap

None of the stalled tasks triggered a clarification request or a "recipient unknown" abort message. The agent continued to stall until the step limit, resulting in no outcome instead of an explicit OUTCOME_NONE_CLARIFICATION flag being written to the task record. Tasks t04 and t12 both confirm this pattern—after failing to locate Maya and Alex Meyer respectively, the agent stalled without writing any resolution flag or requesting clarification.

## Shortcuts
- **Standard email send pattern**: Search accounts for company → read account → extract `primary_contact_id` → read contacts/{id}.json → get `email` → read `/outbox/<file> for next ID → write `/outbox/<file>

- **When name lookup fails (t12)**: Searching for "Alex Meyer" found no matches, but searching for just "Alex" surfaced `<manager>.json` (Alexander Richter). The evaluator flagged the person wasn't Alex Meyer, but the contact existed under a different full name. This suggests that when an exact name search fails, try searching by first name, role, or partial string before concluding the contact doesn't exist.

- **Compliance flags inform caution (t14)**: Blue Harbor Bank has `external_send_guard` flag. The account notes explicitly warn: "Security review keeps slipping, so outbound promises should stay conservative and never imply approval is already done." Always check `compliance_flags` in the account file before composing.

- **Contact structure verification (t12)**: Reading `/contacts/<file> confirmed the structure: `{id, account_id, full_name, role, email, preferred_tone, last_seen_on, tags}`. Use `preferred_tone` to guide email style if needed.

- **Stall trigger**: Taking 6+ steps without write/delete/move/action while repeatedly browsing the same locations (/, /contacts, /contacts/<file>) signals the lookup isn't working. At that point: try a different search term, verify the contact file exists, or acknowledge the contact may not be in the system.

- **Contacts folder may not exist**: t04 search for "/" found no `/contacts` folder initially. Fall back to checking account files directly for any contact references.

- **Check manager files for additional contacts (t12)**: The `/contacts/<file> folder may contain `mgr_*.json` files separate from `cont_*.json` sequence. When standard contacts don't yield a match, search manager files by first name or partial string. Even partial matches like "Alex" → "Alexander" may surface relevant contacts, though verify the matched person is actually the intended recipient.

- **Name mismatch doesn't always mean contact missing (t12)**: When searching for a name like "Alex Meyer" returns no direct match, the person may exist under a different full name. Exhausting standard contacts without finding a name variant is grounds for acknowledging the contact cannot be located within the vault.

## Proven Step Sequences → OUTCOME_OK
### Pattern: Contact Lookup via Account → Outbox Write

**Workflow:**
1. `search` for account name → locate `accounts/<id>.json`
2. `read /accounts/<file> → extract `primary_contact_id` and/or `email`
3. `read /contacts/<file> → verify contact details
4. `read /outbox/<file> → get next sequence ID
5. `write /outbox/<file> → deliver email

**t14** (Blue Harbor Bank):
```
search "Blue Harbor Bank" → accounts/<account>.json:3,4
read /accounts/<file> → primary_contact_id: <contact>, email: <email>
read /contacts/<file> → full_name: Sem Bakker, role: Product Manager, preferred_tone: brief
read /outbox/<file> → id: 84851
write /outbox/<file> → SUCCESS
```

**t35** (Aperture AI Labs):
```
search "Aperture AI Labs" → accounts/<account>.json:3,4
read /accounts/<file> → primary_contact_id: <contact>, email: <email>
read /contacts/<file> → full_name: Finn Visser, role: Finance Director, preferred_tone: direct
read /outbox/<file> → id: 84625
write /outbox/<file> → SUCCESS
```

**Key insight:** Contact identity is reliably resolved through account lookup. Reading the contact file verifies tone preferences and confirms current status before composing.

---

## Failed Patterns → OUTCOME_NONE_CLARIFICATION
### t04: Contact Not Found

**Workflow:**
1. `search` for "Sam" → `ERROR NOT_FOUND`
2. `list /contacts` → `ERROR NOT_FOUND`
3. `read /90_memory/soul.md` (checking for guidance)
4. `stall` (6 steps without productive action)

**Evaluator notes:** "Cannot send email without recipient identity"

**Key insight:** When contact lookup fails, agent lacks mechanism to ask clarifying question—stalls indefinitely.

---

### t12: Ambiguous Contact Lookup

**Workflow:**
1. `search "Alex Meyer"` → no matches
2. `search "Meyer"` → no matches
3. `search "Alex"` → found `<manager>` (Alexander Richter—not target)
4. `search` root for "Meyer" → no matches
5. `search` root for "A. Meyer" → no matches
6. `list /contacts` → enumerated <contact>–010, <manager>–003
7. `read /contacts/<file> → verified structure (Leonie Arnold)
8. `stall` (8 steps without productive action)

**Evaluator notes:** "Verified Alex Meyer not in any contact file"

**Key insight:** Partial matches (e.g., "Alex" → Alexander Richter) do not satisfy precise contact requests. Agent exhausts search options before recognizing need for clarification.

## Verified refusal: t04 (2026-04-30)
<!-- refusal: t04:OUTCOME_NONE_CLARIFICATION -->

**Goal shape:** Email Sam a brief update on whichever initiative matters most.

**Outcome:** OUTCOME_NONE_CLARIFICATION

**Why refuse:** OUTCOME_NONE_CLARIFICATION: Sam's contact file does not exist in this vault. Searched the entire vault for any file containing 'Sam' — zero results. The /contacts/ folder was not found (listed twice,

**Probes before refusal:**
1. read(/90_memory/soul.md)
2. search(?)
3. search
4. list(/)
5. search
6. list(/contacts)

**Applies when:** email

## Successful pattern: t14 (2026-04-30)
<!-- researcher: t14:bf79fde996c8 -->

**Goal shape:** Send email to Blue Harbor Bank with subject "Security review follow-up" and body "Checking in on the

**Final answer:** Email sent to Blue Harbor Bank at <email> with subject 'Security review follow-up' and body 'Checking in on the open security review. Happy to answer questions and alig

**Trajectory:**
1. search
2. read(/accounts/<file>)
3. read(/contacts/<file>)
4. read(/outbox/<file>)
5. write(/outbox/<file>)

**Key insights:**
- (none)

**Applies when:** email

## Verified refusal: t12 (2026-04-30)
<!-- refusal: t12:OUTCOME_NONE_CLARIFICATION -->

**Goal shape:** Send short follow-up email to Alex Meyer about next steps on the expansion. Keep the diff focused.

**Outcome:** OUTCOME_NONE_CLARIFICATION

**Why refuse:** Recipient 'Alex Meyer' not found after comprehensive vault search. Searched full name, surname, given name, and initial combinations — zero matches. The contacts directory contains only <contact>-cont_

**Probes before refusal:**
1. search
2. search
3. search
4. read(/contacts/<file>)
5. search
6. search

**Applies when:** email

## Successful pattern: t35 (2026-04-30)
<!-- researcher: t35:4801eba17ad0 -->

**Goal shape:** Send email to the account German AI-insights add-on subscriber Aperture with subject "Security revie

**Final answer:** Email sent to Aperture AI Labs (Finn Visser, <email>) with subject 'Security review follow-up' and body 'Checking in on the open security review. Happy to answer quest

**Trajectory:**
1. search
2. read(/accounts/<file>)
3. read(/contacts/<file>)
4. read(/outbox/<file>)
5. write(/outbox/<file>)

**Key insights:**
- (none)

**Applies when:** email
