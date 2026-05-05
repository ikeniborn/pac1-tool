<!-- wiki:meta
category: capture
quality: nascent
fragment_count: 4
fragment_ids: [t09_20260504T211010Z, t33_20260504T222716Z, t33_20260504T233057Z, t33_20260505T003027Z]
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
- **Content Snippet:** "The article argues that structured outputs help most when paired with narrow schemas"
- **Sequence Pattern:** Website source → Security checkpoint → Vault path
- **Security Gate:** OUTCOME_OK indicates Anthropic documentation domain passed validation without restrictions

**Proven Pattern:** Anthropic documentation domains (docs.anthropic.com) successfully pass security validation. Capture sequences to official documentation sources proceed directly to vault path assignment when source domain is recognized as trusted developer documentation.

**Capture Sequence Log (t33)**
- **Date:** <date>
- **Source:** medium.com
- **Task Type:** capture
- **Outcome:** OUTCOME_OK
- **Vault Path:** 01_capture/influential/2026-04-04__structured-outputs-clip.md
- **Content Snippet:** "The article argues that structured outputs help most when paired with narrow schemas a"
- **Sequence Pattern:** Website source → Security checkpoint → Vault path
- **Security Gate:** OUTCOME_OK indicates Medium publication platform passed validation without restrictions

**Proven Pattern:** Medium.com domains successfully pass security validation. Capture sequences to Medium articles proceed directly to vault path assignment when source domain is recognized as standard publication platform. Medium.com operates as a trusted content source similar to documentation domains, allowing straightforward capture into vault paths.

**Capture Sequence Log (t33)**
- **Date:** <date>
- **Source:** medium.com
- **Task Type:** capture
- **Outcome:** OUTCOME_OK
- **Vault Path:** 01_capture/influential/2026-04-04__prompting-review-snippet.md
- **Content Snippet:** "The article argues that structured outputs help most when paired with narrow schemas "
- **Sequence Pattern:** Website source → Security checkpoint → Vault path
- **Security Gate:** OUTCOME_OK indicates Medium publication platform passed validation without restrictions

## Key pitfalls
**Source Misidentification Risks**
- The agent may attempt to capture content from unverified or restricted sources (e.g., substack.com, behind paywalls or access controls) without confirming source legitimacy or access permissions
- Security gates (OUTCOME_DENIED_SECURITY) may block captures when source verification fails or when the requested content resides in restricted environments
- Example: A capture task targeting substack.com without validating whether the content is publicly accessible or authorized for capture triggers denial
- Legitimate public documentation sources (e.g., docs.anthropic.com) provide examples of correctly verified accessible sources, distinguishing them from restricted environments where capture attempts should be denied
- Sources like medium.com that return OUTCOME_OK indicate verified accessible environments, but capture attempts still require validation against access controls; the distinction between accessible (medium.com, docs.anthropic.com) and restricted (substack.com) sources must be maintained

**Partial Capture Risks**
- Snippet requests may be truncated mid-content, resulting in incomplete captures ("...The pract") that lack necessary context or full meaning
- Partial captures can lead to misrepresentation of source material or lost critical information
- Interrupted or cut-off capture attempts may leave the file system in an inconsistent state with partial data written
- Captured snippets that end mid-sentence (e.g., "...narrow schemas") may lack concluding context needed for accurate interpretation and reuse
- Truncation can occur mid-word as seen in "narrow schemas a" where the capture ends abruptly on a single letter, demonstrating that content termination points are unpredictable and may leave critical trailing content uncaptured
- Even successful captures (OUTCOME_OK) can produce truncated content; a snippet reading "...paired with narrow schemas " demonstrates incomplete capture where the text cuts off mid-word before any concluding punctuation or context, leaving the reader without the completed thought and potentially misrepresenting the author's argument about structured outputs and schema design

**Wrong Target Path Risks**
- Capture operations targeting incorrect or unintended directory paths risk overwriting existing files or polluting wrong directories
- Source misidentification compounds this risk when the agent cannot properly resolve the intended destination due to ambiguous source references
- Consistent path conventions (e.g., date-prefixed filenames like "2026-04-04__agent-evals-notes.md") help reduce ambiguity and mis-targeting, but risk remains when snippet content is fragmented and context is lost
- Even with correct path conventions like the date-prefixed format "2026-04-04__structured-outputs-clip.md", destination accuracy depends on the agent correctly interpreting source references and verifying the target directory exists and is writable before capture execution
- The path "01_capture/influential/2026-04-04__prompting-review-snippet.md" demonstrates proper use of date-prefixed naming within structured directory hierarchy, reducing ambiguity in target resolution; however, the fragmented capture content ("...narrow schemas ") underscores that even with correct path conventions, partial content can leave critical context missing, making downstream verification and reuse challenging

## Shortcuts
t09 | capture | OUTCOME_DENIED_SECURITY | <date> | Capture from substack.com denied — security policy blocks this domain. Insight: External content domains like substack.com may be restricted, requiring alternative access methods (copy/paste, approved mirrors, or local caching) before capture operations.
t33 | capture | OUTCOME_OK | <date> | Capture from docs.anthropic.com succeeded — first-party domains like anthropic.com are whitelisted for capture operations. Insight: Corporate/developer documentation domains (anthropic.com, openai.com, google.com) often have security exceptions, making them reliable capture targets when access to user content domains is restricted.
t33 | capture | OUTCOME_OK | <date> | Capture from medium.com succeeded — content platform domains like medium.com are accessible for capture operations, unlike restricted sites like substack.com. Insight: Content publishing platforms (medium.com, dev.to, etc.) generally have fewer security restrictions than newsletter platforms, making them reliable capture targets when accessible.
t33 | capture | OUTCOME_OK | <date> | Capture from medium.com succeeded — content platform domains like medium.com are accessible for capture operations, unlike restricted sites like substack.com. Insight: Content publishing platforms (medium.com, dev.to, etc.) generally have fewer security restrictions than newsletter platforms, making them reliable capture targets when accessible.

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
