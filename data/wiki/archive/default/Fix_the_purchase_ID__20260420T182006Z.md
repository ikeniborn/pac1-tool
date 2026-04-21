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
- read: /processing/lane_a.json → {   "prefix": "purchase-",   "mode": "emit",   "traffic": "downstream",   "status": "active",   "writer": "purchase_emit
- read: /processing/lane_b.json → {   "prefix": "purchase-",   "mode": "emit",   "traffic": "shadow",   "status": "active",   "writer": "purchase_emitter_
- read: /purchases/100000.json → {   "account_id": "acct_001",   "amount_cents": 12000,   "created_at": "2026-03-01T10:00:00Z",   "purchase_id": "prc-100
- read: /processing/cleanup-plan.json → {   "enabled": false,   "rewrite_historical_ids": false,   "target_prefix": "legacy-short-prefix",   "note": "Prepare on
- write: /processing/lane_a.json → WRITTEN: /processing/lane_a.json
- read: /processing/lane_a.json → {   "prefix": "prc-",   "mode": "emit",   "traffic": "downstream",   "status": "active",   "writer": "purchase_emitter_v

EVALUATOR:
approved: true
steps: - Fixed lane_a.json prefix from 'purchase-' to 'prc-'
- Verified against historical purchase records (prc-100000)
- Confirmed cleanup-plan.json has rewrite_historical_ids: false — forward-only fix policy enforced
