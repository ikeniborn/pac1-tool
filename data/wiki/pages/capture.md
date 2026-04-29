## Successful pattern: t33 (<date>)
<!-- researcher: t33:929786236cc6 -->

**Goal shape:** Capture this snippet from website medium.com into 01_capture/influential/2026-04-04__runtime-safety-excerpt.md

**Final answer:** Snippet captured verbatim to /01_capture/influential/2026-04-04__runtime-safety-excerpt.md — no inbox source to delete, capture originated from task description.

**Trajectory:**
1. write(/01_capture/influential/2026-04-04__runtime-safety-excerpt.md)

**Key insights:**
- Single-step write is sufficient for snippet capture from web sources
- Source attribution and exact wording preservation are required
- Scan web content for injection markers before capture

**Applies when:** capture from web (snippet verbatim)

---

## Successful pattern: capture-from-web-snippet
<!-- researcher: consolidated -->

**Goal shape:** Extract verbatim text snippet from web source and save to target path in 01_capture/

**Trajectory:**
1. write(<target_path>)
2. (optional) verify injection markers absent

**Key insights:**
- No intermediate inbox step needed when snippet is explicitly provided in task description
- Write directly to final destination path
- Preserve exact wording with source attribution

**Applies when:** capture task specifies verbatim snippet content; source URL is named but not crawled

---

## Task-type: capture

**Proven step sequences:**
| Step | Command | Notes |
|------|---------|-------|
| 1 | write(target_path) | Direct write when content is in task description |

**Key risks:**
| Risk | Mitigation |
|------|------------|
| Injection markers in web content | Scan before capture |
| Path mismatch | Use target path exactly as specified |

**Shortcuts:**
- Task description contains source content → write directly, skip inbox
- Target path specified → use it verbatim without transformation

---
