## Successful pattern: t03 (<date>)
<!-- researcher: t03:fcc53cd1b3b0 -->

**Goal shape:** Take inbox file → capture to category folder → create distill card → link to relevant threads → delete inbox. Keep the diff focused.

**Final answer:** Captured the Walmart ChatGPT checkout inbox item:
- **Capture:** [/01_capture/influential/2026-03-23__hn-walmart-chatgpt-checkout.md](/01_capture/influential/2026-03-23__hn-walmart-chatgpt-checkout.md)
- **Card:** [/02_distill/cards/2026-03-23__hn-walmart-chatgpt-checkout.md](/02_distill/cards/2026-03-23__hn-walmart-chatgpt-checkout.md)
- **Threads updated:** agent-platforms-and-runtime, ai-engineering-foundations

**Trajectory:**
1. read(/00_inbox/...) ← read inbox source first
2. read(/02_distill/threads/...) ← read existing threads to understand structure before writing
3. write(/01_capture/...) ← capture to target category folder
4. write(/02_distill/cards/...) ← create distill card linked to capture source
5. write(/02_distill/threads/...) ← update thread with new card link (AIOS-NOTE preserved)
6. read(/02_distill/threads/...) ← check other relevant threads
7. delete(/00_inbox/...) ← delete inbox file only after all writes confirmed
8. write(/02_distill/threads/...) ← update second thread if relevant

**Key insights:**
- Read threads before writing to avoid conflicts with existing AIOS-NOTE blocks
- Update relevant threads after card creation; skip threads unrelated to the content
- Focus diff on essential changes: one card, two threads, one deletion
- Deleting inbox file is the final step only after all writes are confirmed

**Applies when:** distill

---
