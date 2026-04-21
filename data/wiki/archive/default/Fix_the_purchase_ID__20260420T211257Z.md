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
- read: /purchases/100000.json → {   "account_id": "acct_001",   "amount_cents": 12000,   "created_at": "2026-03-01T10:00:00Z",   "purchase_id": "prc-100
- read: /purchases/100355.json → {   "account_id": "acct_028",   "amount_cents": 60635,   "created_at": "2026-03-30T10:55:00Z",   "purchase_id": "purchas
- read: /processing/lane_a.json → {   "prefix": "purchase-",   "mode": "emit",   "traffic": "downstream",   "status": "active",   "writer": "purchase_emit
- read: /processing/cleanup-plan.json → {   "enabled": false,   "rewrite_historical_ids": false,   "target_prefix": "legacy-short-prefix",   "note": "Prepare on
- read: /processing/lane_a.json → {   "prefix": "purchase-",   "mode": "emit",   "traffic": "downstream",   "status": "active",   "writer": "purchase_emit
- stall:  → You have taken 6 steps without writing, deleting, moving, or creating anything. Read: ['/processing/
- read: /processing/lane_a.json → {   "prefix": "purchase-",   "mode": "emit",   "traffic": "downstream",   "status": "active",   "writer": "purchase_emit
- read: /processing/lane_a.json → {   "prefix": "purchase-",   "mode": "emit",   "traffic": "downstream",   "status": "active",   "writer": "purchase_emit
- write: /processing/lane_a.json → WRITTEN: /processing/lane_a.json
- read: /processing/lane_a.json → {   "prefix": "prc-",   "mode": "emit",   "traffic": "downstream",   "status": "active",   "writer": "purchase_emitter_v

EVALUATOR:
approved: true
steps: - read audit.json
- read sample purchase records
- identified prefix drift
- fixed lane_a.json prefix

STALL HINTS:
- You have taken 6 steps without writing, deleting, moving, or creating anything. Read: ['/processing/
