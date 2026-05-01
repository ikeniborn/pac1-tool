<!-- wiki:meta
category: temporal
quality: nascent
fragment_count: 2
fragment_ids: [t43_20260430T205349Z, t43_20260430T211805Z]
last_synthesized: 2026-04-30
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
### Vault Anchor Derivation
- **Primary rule**: When no explicit reference path is provided and a queried path returns `NOT_FOUND`, the agent must derive a "vault anchor" — the nearest populated capture directory containing timestamped files.
- **Derivation method**: Scan the root for known capture subdirectories (e.g., `/01_capture/influential/`), list their contents, and identify the most recent timestamped file to establish a temporal baseline.
- **Anchor source**: In `t43`, `/01_capture/influential/` served as the vault anchor, yielding files like `2026-02-10__how-i-use-claude-code.md` through `2026-03-23__hn-structured-outputs-practical-notes.md`.
- **VAULT_DATE as ESTIMATED_TODAY proxy**: When no explicit "today" reference exists, the most recent capture file date becomes `ESTIMATED_TODAY` for relative date calculations. In `t43`, this yielded `ESTIMATED_TODAY=<date>` derived from the vault anchor's most recent file date.

### Candidate File Inversion Approach
- **Pattern**: For date-relative queries (e.g., "28 days ago"), compute the target date by subtracting the offset from the vault anchor's most recent file date.
- **t43 example**: Anchor date `<date>` minus 28 days yielded target `<date>`.
- **Inversion behavior**: When zero exact matches exist for the computed date, the agent must invert strategy — collect all candidate files within ±threshold range and return nearest temporal neighbors ordered by proximity.
- **Fallback candidates**: In `t43`, exact match for `<date>` returned 0 results; nearest candidates identified were `<date>` and `<date>`.
- **Outcome signaling**: When using inversion, set `outcome: OUTCOME_NONE_CLARIFICATION` to indicate the user must clarify which of the nearest candidates matches their intent.
- **Small-offset inversion**: Even small offsets (e.g., 10 days) may require inversion when the vault lacks captures for the computed target date. In `t43`, 10 days prior to `ESTIMATED_TODAY=<date>` yielded `<date>`, which returned 0 exact matches; nearest neighbor `<date>` was identified and user clarification was requested.

## Key pitfalls
- **Wrong temporal anchor**: Agent may anchor to wrong date (e.g., newest file in folder) rather than computing the actual requested temporal anchor (e.g., 28 days ago from `date: <date>` → `<date>`). In t43, agent anchored to newest capture `<date>` instead of the actual target date `<date>`, causing wrong baseline for subtraction and producing `<date>` as "28 days ago"—when there are no captures near that date, only near `<date>` and `<date>`. Additionally, agent may invert the temporal relationship, computing the target correctly but then deriving a contradictory implied reference date from candidates (e.g., computing target as <date> but implying reference date as <date> based on proximity to <date>), creating circular reasoning that undermines the anchor's validity.

- **Premature NONE_CLARIFICATION**: When zero exact matches are found at computed anchor, agent reports failure without recognizing the anchor itself may be wrong. Should detect divergence (computed anchor falls between unrelated file dates) and clarify before concluding NONE.

- **System-clock vs vault-time confusion**: Agent uses system date for temporal math but vault may lack captures for that date range. Agent should verify vault coverage for the computed period before committing to the anchor.

## Shortcuts
VAULT_DATE as lower bound: When searching for historical content, files are filtered to those with dates ≥ VAULT_DATE. The vault date (earliest meaningful content date) constrains the search space and prevents impossible date calculations.

ESTIMATED_TODAY derivation: Tasks with `date: YYYY-MM-DD` provide the temporal anchor. This value serves as ESTIMATED_TODAY for all relative calculations (e.g., "28 days ago" means `ESTIMATED_TODAY - 28`). When no explicit date exists or the task date exceeds available file dates, ESTIMATED_TODAY may be derived from VAULT_DATE instead.

Candidate inversion (implied_today = file_date + N): When no exact date match exists, inference runs backwards:
1. Target date = ESTIMATED_TODAY - N days
2. List candidate files with dates ≤ target date
3. If multiple candidates exist, derive implied_today by adding N to each file date — the file whose implied_today most closely matches ESTIMATED_TODAY is the strongest candidate

Example from t43:
- ESTIMATED_TODAY derived from VAULT_DATE (task date <date> exceeds file date range)
- N = 10 days
- Target = <date>
- `/01_capture/influential/` contains files from <date>, <date>, <date>, <date>, <date> (all before target)
- 0 exact matches for target date
- Candidate inversion: nearest file <date> + 10 = implied <date> (diverges ~33 days from ESTIMATED_TODAY)
- Clarification required: which candidate is intended, since all candidates imply today significantly earlier than VAULT_DATE

## Verified refusal: t43 (2026-04-30)
<!-- refusal: t43:OUTCOME_NONE_CLARIFICATION -->

**Goal shape:** What article did I capture 28 days ago?

**Outcome:** OUTCOME_NONE_CLARIFICATION

**Why refuse:** No article was captured on <date> (28 days before VAULT_DATE <date>). The vault's /01_capture/influential/ folder contains 5 captured articles but none dated <date>. Nearest candidates: 20

**Probes before refusal:**
1. list(/notes)
2. list(/notes)
3. list(/)
4. list(/01_capture/influential/)
5. list(/)
6. list(/01_capture/influential/)

**Applies when:** temporal
