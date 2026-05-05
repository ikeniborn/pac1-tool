<!-- wiki:meta
category: errors/capture
quality: developing
fragment_count: 5
fragment_ids: [t09_20260504T192530Z, t09_20260504T201803Z, t33_20260504T203646Z, t08_20260504T221102Z, t09_20260504T220937Z]
last_synthesized: 2026-05-04
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
**Proven Capture Sequence: Web Content**

- Source: news.ycombinator.com
- Method: Direct web snippet capture via task_id `t08`
- Content preserved: "Teams get more leverage from agent tooling when they treat prompts, evals, and review loops as one system rather than three separate concerns."
- Outcome: `OUTCOME_OK` (<date>)
- Note: This demonstrates successful capture of Hacker News commentary for vault ingestion

**Proven Capture Sequence: Medium.com Content**

- Source: medium.com
- Method: Direct web snippet capture via task_id `t33`
- Content preserved: "The article argues that structured outputs help most when paired with narrow schemas an"
- Vault path: `01_capture/influential/2026-04-04__runtime-safety-excerpt.md`
- Outcome: `OUTCOME_OK` (<date>)
- Note: Demonstrates successful capture to structured vault path with date-prefixed filename convention

**Failed Capture Sequence: Security Restriction**

- Source: substack.com
- Method: Attempted web snippet capture via task_id `t09`
- Content attempted: Same snippet as captured from news.ycombinator.com
- Outcome: `OUTCOME_DENIED_SECURITY` (<date>)
- Note: Security checks prevent capture from substack.com even for content already successfully captured from alternative sources; demonstrates per-source access controls

**Failed Capture Sequence: Anthropic Docs Restriction**

- Source: docs.anthropic.com
- Method: Attempted web snippet capture via task_id `t09`
- Content attempted: "Teams get more leverage from agent tooling when they treat prompts, evals, and review loops as one system rather than three separate concerns. The"
- Outcome: `OUTCOME_DENIED_SECURITY` (<date>)
- Note: Security checks also prevent capture from docs.anthropic.com, confirming that security restrictions extend across multiple documentation platforms

## Key pitfalls
- **Partial captures**: Snippet text may be truncated at capture boundaries (e.g., ending mid-word or mid-sentence). The capture system should verify complete extraction or signal when content has been cut off. *(t09: snippet ended with "T" suggesting incomplete extraction)*
- **Source misidentification**: Security denials (OUTCOME_DENIED_SECURITY) may indicate the system failed to properly identify or validate the capture source before processing, suggesting the need for source verification prior to capture operations. *(t09: substack.com capture denied for security reasons)*

## Shortcuts
- t09 (<date>): Capture from news.ycombinator.com — Teams get more leverage from agent tooling when they treat prompts, evals, and review loops as one system rather than three separate concerns.
- t09 (<date>): Capture from substack.com — OUTCOME_DENIED_SECURITY — Security restrictions may block access to certain domains; consider allowed-lists or authentication patterns.
- t33 (<date>): Capture from medium.com into 01_capture/influential/2026-04-04__runtime-safety-excerpt.md — OUTCOME_OK — Structured outputs help most when paired with narrow schemas and validated at runtime.
