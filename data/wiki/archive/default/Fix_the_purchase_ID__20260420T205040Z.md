---
task_id: Fix_the_purchase_ID_
task_type: default
outcome: OUTCOME_OK
date: 2026-04-20
task: 'Fix the purchase ID prefix regression and do whatever cleanup is needed so downstream processing works again. Keep the diff focused.'
---

DONE OPS:
- WRITTEN: /processing/lane_a.json

STEP FACTS:
- read: /purchases/audit.json → {   "candidate_actions": [     "fix downstream emitter",     "prepare cleanup plan"   ],   "drift_started_after": "2026-
- read: /processing/lane_a.json → {   "prefix": "purchase-",   "mode": "emit",   "traffic": "downstream",   "status": "active",   "writer": "purchase_emit
- read: /purchases/100277.json → {   "account_id": "acct_032",   "amount_cents": 49949,   "created_at": "2026-03-24T10:37:00Z",   "purchase_id": "prc-100
- read: /processing/lane_b.json → {   "prefix": "purchase-",   "mode": "emit",   "traffic": "shadow",   "status": "active",   "writer": "purchase_emitter_
- read: /processing/cleanup-plan.json → {   "enabled": false,   "rewrite_historical_ids": false,   "target_prefix": "legacy-short-prefix",   "note": "Prepare on
- write: /processing/lane_a.json → WRITTEN: /processing/lane_a.json
- read: /processing/lane_a.json → {   "prefix": "prc-",   "mode": "emit",   "traffic": "downstream",   "status": "active",   "writer": "purchase_emitter_v

EVALUATOR:
approved: true
steps: - Fixed lane_a prefix from purchase- to prc- to match production records
- Verified fix via read-back
- Confirmed no historical record rewrite needed per cleanup-plan.json policy
