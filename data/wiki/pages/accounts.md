<!-- wiki:meta
category: accounts
quality: developing
fragment_count: 12
fragment_ids: [t14_20260430T133947Z, t32_20260430T140120Z, t34_20260430T140103Z, t35_20260430T140056Z, t36_20260430T140441Z, t37_20260430T140728Z, t38_20260430T140152Z, t39_20260430T140342Z, t34_20260430T165555Z, t37_20260430T170449Z, t38_20260430T165841Z, t39_20260430T165835Z]
last_synthesized: 2026-04-30
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
- read account file before initiating any write operation (t14, t32, t37, t38 confirm read-first pattern)
- write account file only after confirming current state via read (t32 demonstrates this sequence)
- perform read again after write to verify write succeeded and content matches intended update (t32 shows read→write→read verification cycle)
- for multi-account tasks, read each account file in sequence before proceeding to writes (t38 reads <account>, <account>, <account>, <account> in order)
- account_manager field may differ between reads for same account due to team assignment changes; do not assume stale read reflects current state (<account> shows Jonas Schneider → Daniel Koch → Holger Arnold across reads)
- next_follow_up_on may shift during updates; do not carry forward old date after successful write (t32 shows next_follow_up_on changed from <date> to <date> after write)

## Key pitfalls
- **Security review stalls blocking expansion**: Blue Harbor Bank (<account>) and Aperture AI Labs (<account>) both have open security reviews that delay scope expansion and feature rollouts. Avoid implying approval is imminent.
- **DPA review gating healthcare procurement**: Nordlicht Health (<account>) has legal-enforced DPA review as a prerequisite for any scope expansion. Do not commit to expansion timelines before DPA is cleared.
- **False urgency signals in logistics accounts**: CanalPort Shipping (<account>) has real operational pain but absorbs delays with overtime, masking urgency. The follow-up date slipped by one day (<date> → <date>) in a single write cycle, indicating the account manager is already struggling to maintain cadence.
- **Intentional name ambiguity across Acme accounts**: Acme Robotics (<account>) and Acme Logistics (<account>) are separate accounts with separate buying committees despite similar naming. This ambiguity is intentional and must remain visible to prevent cross-account promise contamination.
- **External send guard on financial accounts**: Blue Harbor Bank (<account>) carries an external_send_guard flag that restricts outbound communications. All external promises require conservative framing.
- **Account manager churn creating knowledge gaps**: Multiple accounts show account_manager changes within short time windows across the task log (<account>: three different managers across t34, t38; <account>: three different managers across t36, t38, t39; <account> and <account> similarly shifted). Rapid handoffs risk context loss on strategic and compliance-flagged accounts.
- **Sponsor departure risk on logo wins**: Silverline Retail (<account>) illustrates a pattern where initial buyer enthusiasm converts to a signed deal but the sponsoring champion moves roles before broader rollout sponsorship is secured. The resulting weak internal sponsorship surfaces in follow-up conversations as hesitation and blocked escalation paths.

## Shortcuts
- **Compliance-driven accounts (healthcare/finance) require longer procurement timelines** — DPA reviews, security reviews, and architecture reviews are common gatekeepers. Budget approval does not imply immediate execution capacity.
- **Blue Harbor Bank specifically**: Security review is a chronic bottleneck. Any outbound communication should explicitly state that approvals are pending and avoid implying certainty about timelines or expanded capabilities.
- **Logistics accounts (CanalPort Shipping, Acme Logistics)** tend to absorb delays with internal resources, resulting in medium urgency despite clear operational pain. Engagement cadence can be longer without risk of churn.
- **Acme naming ambiguity**: Two separate Acme accounts (Acme Robotics, Acme Logistics) exist in different industries and regions with different buying committees. The name similarity is intentional and must remain visible to avoid cross-contamination of account context.
- **Write operations on tracked files**: When updating JSON files like <account>.json, verify the written state matches intent — subtle field changes (e.g., date offsets) can affect follow-up scheduling.
- **AI insights add-on accounts** (e.g., Aperture AI Labs) often trigger secondary security reviews when new data flows are introduced, even after the core platform relationship is established.
- **Demo-based logo wins require rapid sponsorship consolidation** — Accounts like Silverline Retail show that procurement closed through event demos can result in weak internal sponsorship when the original champion moves roles before broader rollout sponsorship is established. Follow-up conversations often surface fragile advocacy. Post-close prioritization should include rapid documentation of value metrics and identification of secondary sponsors.
- **Account manager assignments may be stale across reads** — When the same account is read across different tasks, assignment of account managers can differ (e.g., <account> showing alternating assignments in separate reads), indicating active transitions. Cross-reference against the most recent read before treating AM context as current.
- **Loss analysis accelerates manufacturing segment deals** — Accounts like Acme Robotics have closed after warm intros through systems integrators familiar with operational handoff pain points (e.g., robotics QA to plant operations), with a workflow audit plus concrete loss analysis proving sufficient for initial budget approval in this segment.
