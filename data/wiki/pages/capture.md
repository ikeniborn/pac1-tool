<!-- wiki:meta
category: capture
quality: developing
fragment_count: 5
fragment_ids: [t09_20260504T211010Z, t33_20260504T222716Z, t33_20260504T233057Z, t33_20260505T003027Z, t33_20260505T165332Z]
last_synthesized: 2026-05-05
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
**Capture Sequence Log (t09)**
- **Date:** <date>
- **Source:** substack.com
- **Task Type:** capture
- **Outcome:** DENIED — Security validation failed
- **Content Snippet:** "Teams get more leverage from agent tooling when they treat prompts, evals, and review loops as one system rather than three separate concerns. The pract..."
- **Sequence Pattern:** Website source → Security checkpoint → Vault path
- **Security Gate:** OUTCOME_DENIED_SECURITY indicates source domain (substack.com) triggered content policy restrictions during capture validation phase

**Proven Pattern:** Not all website sources pass security validation. Substack domains require additional verification before content can be captured into vault paths. Capture sequences must include security checkpoint failure handling.

**Capture Sequence Log (t33)**
- **Date:** <date>
- **Source:** docs.anthropic.com
- **Task Type:** capture
- **Outcome:** OUTCOME_OK
- **Vault Path:** 01_capture/influential/2026-04-04__agent-evals-notes.md
- **Content Snippet:** "Teams get more leverage from agent tooling when they treat prompts, evals, and revie..."
- **Sequence Pattern:** Website source → Security checkpoint → Vault path
- **Security Gate:** OUTCOME_OK — Anthropic documentation domain passed validation without restrictions (pattern confirmed from prior t33 entry)

## Key pitfalls
**Source Misidentification Risks**
- The agent may attempt to capture content from unverified or restricted sources (e.g., substack.com, behind paywalls or access controls) without confirming source legitimacy or access permissions
- Security gates (OUTCOME_DENIED_SECURITY) may block captures when source verification fails or when the requested content resides in restricted environments
- Example: A capture task targeting substack.com without validating whether the content is publicly accessible or authorized for capture triggers denial
- Legitimate public documentation sources (e.g., docs.anthropic.com) provide examples of correctly verified accessible sources, distinguishing them from restricted environments where capture attempts should be denied
- Sources like medium.com that return OUTCOME_OK indicate verified accessible environments, but capture attempts still require validation against access controls; the distinction between accessible (medium.com, docs.anthropic.com) and restricted (substack.com) sources must be maintained

**Partial Capture Risks**
- Snippet requests may be truncated mid-content, resulting in incomplete captures that lack necessary context or full meaning
- Partial captures can lead to misrepresentation of source material or lost critical information
- Interrupted or cut-off capture attempts may leave the file system in an inconsistent state with partial data written
- Captured snippets that end mid-sentence lack concluding context needed for accurate interpretation and reuse
- Truncation can occur mid-word, demonstrating that content termination points are unpredictable and may leave critical trailing content uncaptured
- Even successful captures (OUTCOME_OK) can produce truncated content; a snippet reading "...revie" demonstrates capture ending abruptly mid-thought, leaving the reader without the completed argument about structured outputs and schema design
- Task t33 exemplifies this: capturing from docs.anthropic.com produced "Teams get more leverage from agent tooling when they treat prompts, evals, and revie" which cuts off mid-word, preventing full understanding of the author's argument

**Wrong Target Path Risks**
- Capture operations targeting incorrect or unintended directory paths risk overwriting existing files or polluting wrong directories
- Source misidentification compounds this risk when the agent cannot properly resolve the intended destination due to ambiguous source references
- Consistent path conventions (e.g., date-prefixed filenames like "2026-04-04__agent-evals-notes.md") help reduce ambiguity and mis-targeting, but risk remains when snippet content is fragmented and context is lost
- Even with correct path conventions like the date-prefixed format, destination accuracy depends on the agent correctly interpreting source references and verifying the target directory exists and is writable before capture execution
- The path "01_capture/influential/2026-04-04__prompting-review-snippet.md" demonstrates proper use of date-prefixed naming within structured directory hierarchy, reducing ambiguity in target resolution
- Capturing into files that already exist (e.g., 01_capture/influential/2026-04-04__agent-evals-notes.md) risks overwriting or appending to prior captures, creating data inconsistency when combined with partial content truncations
- The fragmented capture content underscores that even with correct path conventions, partial content can leave critical context missing, making downstream verification and reuse challenging

## Shortcuts
t09 | capture | OUTCOME_DENIED_SECURITY | <date> | Capture from substack.com denied — security policy blocks this domain. Insight: External content domains like substack.com may be restricted, requiring alternative access methods (copy/paste, approved mirrors, or local caching) before capture operations.
t33 | capture | OUTCOME_OK | <date> | Capture from docs.anthropic.com succeeded — first-party and corporate/developer domains (anthropic.com, openai.com, google.com) are whitelisted for capture operations. Insight: AI developer documentation (prompt engineering, eval frameworks, agent tooling) is high-value content to capture as it directly informs agent system development and optimization.
t33 | capture | OUTCOME_OK | <date> | Capture from medium.com succeeded — content publishing platforms (medium.com, dev.to, etc.) generally have fewer security restrictions than newsletter platforms. Insight: Content platforms are reliable capture targets when accessible, offering accessible alternatives when user content domains are restricted.

## Successful pattern: t33 (2026-05-04)
<!-- researcher: t33:e3b0c44298fc -->

**Goal shape:** Capture this snippet from website docs.anthropic.com into 01_capture/influential/2026-04-04__agent-e

**Final answer:** (unspecified)

**Trajectory:**
1. ?
2. ?

**Key insights:**
- (none)

**Applies when:** capture
