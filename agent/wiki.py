"""Wiki-Memory: persistent cross-session knowledge store.

data/wiki/
├── pages/      # Compiled by lint (LLM synthesis), read by tasks
│   ├── errors.md
│   ├── contacts.md
│   ├── accounts.md
│   ├── email.md, crm.md, lookup.md, temporal.md, inbox.md, ...
└── fragments/  # Append-only raw writes by tasks (one file per task)
    ├── errors/
    ├── contacts/
    ├── accounts/
    ├── email/
    └── .../

Lint runs twice per `make run`:
  - before tasks: compile fragments from previous runs into pages
  - after tasks:  compile fragments written in this run into pages

LLM in lint is the synthesis brain (Variant C): it extracts structured knowledge
from raw fragments using category-specific prompts, not just deduplication.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

# FIX-N+6: path-unsafe chars in task_id → fragment writes fail with ENOENT when
# the caller derives task_id from task_text containing '/' or similar.
_TASK_ID_SANITIZE_RE = re.compile(r"[^A-Za-z0-9._-]+")

_WIKI_DIR = Path(__file__).parent.parent / "data" / "wiki"
_PAGES_DIR = _WIKI_DIR / "pages"
_FRAGMENTS_DIR = _WIKI_DIR / "fragments"
_ARCHIVE_DIR = _WIKI_DIR / "archive"

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# FIX-389: gate the normal-mode graph autobuild path; orthogonal to
# WIKI_GRAPH_ENABLED (read-side).
_GRAPH_AUTOBUILD = os.environ.get("WIKI_GRAPH_AUTOBUILD", "1") == "1"
# FIX-413: ingest archived error fragments as antipattern nodes (no LLM).
_GRAPH_ERRORS_INGEST = os.environ.get("WIKI_GRAPH_ERRORS_INGEST", "0") == "1"

# FIX-410: dead-end injection from error fragments at agent startup.
_WIKI_NEGATIVES_ENABLED = os.environ.get("WIKI_NEGATIVES_ENABLED", "1") == "1"
try:
    _WIKI_NEGATIVES_MAX_CHARS = int(os.environ.get("WIKI_NEGATIVES_MAX_CHARS", "800"))
except ValueError:
    _WIKI_NEGATIVES_MAX_CHARS = 800

# FIX-389: matches a fenced ```json ... ``` block (multi-line, lazy).
_JSON_FENCE_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)

_GRAPH_INSTRUCTION_SUFFIX = (
    "\n\nAfter the merged Markdown, append a fenced JSON block describing "
    "graph deltas for this category (used by the knowledge graph index):\n"
    "```json\n"
    "{\"graph_deltas\": {\n"
    "  \"new_insights\": [{\"text\": \"<≤120 chars>\", \"tags\": [\"<category>\"], \"confidence\": 0.5}],\n"
    "  \"new_rules\":     [{\"text\": \"<≤120 chars>\", \"tags\": [\"<category>\"]}],\n"
    "  \"antipatterns\":  [{\"text\": \"<≤120 chars>\", \"tags\": [\"<category>\"]}],\n"
    "  \"edges\":         [{\"from\": \"<text of node A>\", \"rel\": \"requires|conflicts_with|generalizes|precedes\", \"to\": \"<text of node B>\"}]\n"
    "}}\n"
    "```\n"
    "Rules: 1-line text only; max 6 items per array; do not duplicate items "
    "already on the existing page; if nothing worth recording, output empty arrays. "
    "Edges: reference nodes by their exact text; only emit edges between nodes in this delta."
)

_PAGES_GRAPH_PROMPT = (
    "You are indexing a wiki page into a knowledge graph.\n"
    "From the Markdown page below, extract concrete insights, rules, and antipatterns.\n"
    "Focus on ## Successful pattern:, ## Verified refusal:, key rules, and pitfall sections.\n"
    "Do NOT rewrite or summarize the page.\n"
    "Output ONLY a fenced JSON block:\n"
    "```json\n"
    "{\"graph_deltas\": {\n"
    "  \"new_insights\": [{\"text\": \"<≤120 chars>\", \"tags\": [\"<category>\"], \"confidence\": 0.7}],\n"
    "  \"new_rules\":    [{\"text\": \"<≤120 chars>\", \"tags\": [\"<category>\"]}],\n"
    "  \"antipatterns\": [{\"text\": \"<≤120 chars>\", \"tags\": [\"<category>\"]}],\n"
    "  \"edges\":        [{\"from\": \"<text of A>\", \"rel\": \"requires|conflicts_with\", \"to\": \"<text of B>\"}]\n"
    "}}\n"
    "```\n"
    "Rules: 1-line text only; max 8 items per array; confidence=0.7 for verified patterns."
)

# Task type → wiki page name mapping (FIX-325: driven by data/task_types.json).
# 'think' is not a registered task type but a legacy synthesis-prompt bucket;
# keep it pinned in the map so wiki-lint for 'think' fragments still resolves.
from .task_types import wiki_folder_map as _wiki_folder_map
_TYPE_TO_PAGE: dict[str, str] = {**_wiki_folder_map(), "think": "think"}

# Category-specific LLM synthesis prompts (Variant C)
_LINT_PROMPTS: dict[str, str] = {
    "errors": (
        "You are curating an error wiki for an AI file-system agent.\n"
        "From the raw task fragments below, extract concrete error patterns.\n"
        "For each error: give it a short name, state the condition it occurs under, "
        "the root cause, and the solution.\n"
        "Format each entry as:\n"
        "## <Error Name>\n- Condition: ...\n- Root cause: ...\n- Solution: ...\n\n"
        "Rules: deduplicate entries, prefer specific over vague, "
        "remove entries with no actionable solution, merge similar patterns.\n"
        "FORBIDDEN — FIX-357: NEVER introduce a 'Stale Vault Date Used as Temporal "
        "Anchor' entry or any entry that advises 'always derive current date from "
        "system/session clock' / 'never infer today from vault file prefixes'. The "
        "benchmark's real 'today' runs in vault-time; system clock is 3–6 weeks "
        "ahead. Vault signals ARE the correct anchor for temporal tasks. Any error "
        "entry matching this pattern must be dropped from the synthesis."
    ),
    "contacts": (
        "You are curating a workflow wiki for an AI file-system agent.\n"
        "From the raw task fragments below, extract:\n"
        "1. Proven step sequences that led to task success (with OUTCOME_OK)\n"
        "2. Key risks and pitfalls encountered\n"
        "3. Task-type specific insights and shortcuts\n\n"
        "Format as structured Markdown sections with ## headers.\n"
        "Rules: deduplicate, remove outdated entries, prefer concrete over generic.\n"
        "IMPORTANT — FIX-337: do NOT add individual contact entries — do NOT output "
        "## email, ## cont_NNN, ## <name> sections, registry tables mapping "
        "cont_NNN → name → email, or specific email addresses. Output only "
        "patterns, steps, and pitfalls. No entity IDs, no person names, no emails."
    ),
    "accounts": (
        "You are curating a workflow wiki for an AI file-system agent.\n"
        "From the raw task fragments below, extract:\n"
        "1. Proven step sequences that led to task success (with OUTCOME_OK)\n"
        "2. Key risks and pitfalls encountered\n"
        "3. Task-type specific insights and shortcuts\n\n"
        "Format as structured Markdown sections with ## headers.\n"
        "Rules: deduplicate, remove outdated entries, prefer concrete over generic.\n"
        "IMPORTANT — FIX-337: do NOT add individual account entries — do NOT output "
        "## acct_NNN, ## <company> sections, registry tables mapping acct_NNN → "
        "name → industry, account_manager names, or specific entity values. Output "
        "only patterns, steps, and pitfalls. No entity IDs, no company names.\n"
        "PRESERVE — FIX-346: keep the top-of-page 'Do NOT Mutate Fields the Task "
        "Didn't Name' banner verbatim. Never reintroduce a 'Confirmed writable "
        "fields: name, account_manager, status, industry' line — that phrasing "
        "invites the agent to rewrite account_manager on reschedule tasks, which "
        "breaks field-diff checks. If the banner is absent from EXISTING PAGE, "
        "re-insert it at the top."
    ),
    "queue": (
        "You are curating a workflow wiki for an AI file-system agent.\n"
        "From the raw task fragments below, extract:\n"
        "1. Proven step sequences that led to task success (with OUTCOME_OK)\n"
        "2. Key risks and pitfalls encountered\n"
        "3. Task-type specific insights and shortcuts\n\n"
        "Format as structured Markdown sections with ## headers.\n"
        "Rules: deduplicate, remove outdated entries, prefer concrete over generic.\n"
        "IMPORTANT: do NOT include vault-specific data — do NOT output specific handles, "
        "usernames, OTP token values, sequence IDs, channel names from specific vaults, "
        "or entries like 'Handle X verified via Y'. Output only general patterns and steps.\n"
        "PRESERVE — FIX-343/FIX-347/FIX-351: keep the 'Latest Invoice for an Account' sub-sequence "
        "intact across syntheses. Strict rules: filter invoices ONLY by content.account_id "
        "(filename first-block is NOT account_id — never use filename-prefix as an owner proxy); "
        "never introduce a filename-suffix-as-recency fallback for unreadable candidates "
        "(it misattributes invoices across accounts); if a potentially-"
        "newer candidate is unreadable, return OUTCOME_NONE_CLARIFICATION rather than guess. "
        "Keep the rule: NEVER return NONE_CLARIFICATION before running list/find/tree. "
        "FIX-351: preserve 'Account resolution priority' block — when inbox body names a "
        "specific company, the BODY-named company wins over sender-email domain matching. "
        "Only fall back to sender→contact→account_id if body does NOT name a company. "
        "Also preserve the 'recipient identity' rule: outbox `to` = exact `From:` header "
        "of the inbox message, NOT the account primary contact or manager. "
        "DO NOT include concrete company names, email addresses, or person names as "
        "examples — the model treats them as directives and copies them into the outbox."
    ),
    "crm": (
        "You are curating a workflow wiki for an AI file-system agent.\n"
        "From the raw task fragments below, extract:\n"
        "1. Proven step sequences that led to task success (with OUTCOME_OK)\n"
        "2. Key risks and pitfalls encountered\n"
        "3. Task-type specific insights and shortcuts\n\n"
        "Format as structured Markdown sections with ## headers.\n"
        "Rules: deduplicate, remove outdated entries, prefer concrete over generic.\n"
        "IMPORTANT — no vault-specific entity data (no cont_NNN, acct_NNN, company or "
        "person names, specific dates tied to a single task).\n"
        "PRESERVE — FIX-344: keep the top-of-page 'Preserve All Fields on Write' banner "
        "and its 5-step checklist verbatim. Every reschedule/audit failure we've seen "
        "comes from the model generating a stripped-down JSON from memory and dropping "
        "fields like contact_id, priority, region. Do not shorten, do not remove, do not "
        "move below the fold. If the banner is absent from EXISTING PAGE, re-insert it."
    ),
    "temporal": (
        "You are curating a workflow wiki for an AI file-system agent.\n"
        "From the raw task fragments below, extract:\n"
        "1. Proven step sequences that led to task success (with OUTCOME_OK)\n"
        "2. Key risks and pitfalls encountered\n"
        "3. Task-type specific insights and shortcuts\n\n"
        "Format as structured Markdown sections with ## headers.\n"
        "Rules: deduplicate, remove outdated entries, prefer concrete over generic.\n"
        "PRESERVE — FIX-357: the page teaches DERIVATION of benchmark 'today' from "
        "observable vault signals, NOT lookup from a single field. Keep the 'Baseline "
        "Anchor — Derivation, Not Lookup' block at the top verbatim (3-rule priority: "
        "artifact-anchored > vault-content-lookup (INVERT: candidate filename + N = "
        "implied today) > pure arithmetic (derive ESTIMATED_TODAY = VAULT_DATE + "
        "~5 day gap for past-anchored sources, −3 day for future-anchored)). Keep the "
        "'Vault Content Lookup by Relative Date' block with the INVERSION approach "
        "(iterate candidate files, compute implied_today = D + N, pick the one in "
        "[VAULT_DATE, VAULT_DATE+10]). Do NOT re-introduce the old 'compute "
        "TARGET_DATE = currentDate − N, search for file' logic — it assumes today is "
        "known, which it is not.\n"
        "NEVER embed concrete post-mortem result dates from specific runs as canonical "
        "examples (e.g. 'VAULT_DATE = 2026-03-20 → 21-03-2026'). Benchmark today is "
        "randomized per run; baked-in dates teach the wrong anchor. Always use symbolic "
        "placeholders (BASE, VAULT_DATE, ESTIMATED_TODAY, ARTIFACT_DATE) in examples.\n"
        "Do NOT re-introduce any 'VAULT_DATE is ≥7 days behind currentDate' threshold — "
        "that logic is superseded by FIX-357. VAULT_DATE is a LOWER BOUND on today, "
        "not a substitute for today; always add a gap to derive ESTIMATED_TODAY. "
        "Also preserve the rule: never return NONE_CLARIFICATION on temporal tasks "
        "before running at least one list/find/tree."
    ),
    "inbox": (
        "You are curating a workflow wiki for an AI file-system agent.\n"
        "From the raw task fragments below, extract:\n"
        "1. Proven step sequences that led to task success (with OUTCOME_OK)\n"
        "2. Key risks and pitfalls encountered\n"
        "3. Task-type specific insights and shortcuts\n\n"
        "Format as structured Markdown sections with ## headers.\n"
        "Rules: deduplicate, remove outdated entries, prefer concrete over generic.\n"
        "IMPORTANT: do NOT include vault-specific data — do NOT output specific handles, "
        "usernames, contact names, channel entries, or OTP token values from specific vaults. "
        "Output only general patterns and steps."
    ),
    "email": (
        "You are curating a workflow wiki for an AI file-system agent.\n"
        "From the raw task fragments below, extract:\n"
        "1. Proven step sequences that led to task success (with OUTCOME_OK)\n"
        "2. Key risks and pitfalls encountered\n"
        "3. Task-type specific insights and shortcuts\n\n"
        "Format as structured Markdown sections with ## headers.\n"
        "Rules: deduplicate, remove outdated entries, prefer concrete over generic.\n"
        "IMPORTANT — FIX-337: do NOT include ANY vault-specific entity data.\n"
        "  - NO email addresses (no user@domain strings),\n"
        "  - NO contact IDs (cont_NNN) or account IDs (acct_NNN, mgr_NNN),\n"
        "  - NO company names, person names, role titles tied to specific records,\n"
        "  - NO 'wiki-known account/contact' shortcuts that let the agent skip a\n"
        "    contact-file read,\n"
        "  - NO registries / tables mapping account↔contact↔email.\n"
        "The agent MUST always read /contacts/ before writing outbox — wiki-cached\n"
        "recipient info caused wrong-recipient failures (t14/t26). Output only\n"
        "ABSTRACT workflow patterns (e.g. 'search contacts by name → read → use\n"
        "that file's email field'). Entity-specific data is the poison, not the cure."
    ),
    "lookup": (
        "You are curating a workflow wiki for an AI file-system agent.\n"
        "From the raw task fragments below, extract:\n"
        "1. Proven step sequences that led to task success (with OUTCOME_OK)\n"
        "2. Key risks and pitfalls encountered\n"
        "3. Task-type specific insights and shortcuts\n\n"
        "Format as structured Markdown sections with ## headers.\n"
        "Rules: deduplicate, remove outdated entries, prefer concrete over generic.\n"
        "IMPORTANT — FIX-337: do NOT output vault-specific entity data (cont_NNN,\n"
        "acct_NNN, email addresses, person names, company names). Output only\n"
        "abstract workflow patterns."
    ),
    "_pattern_default": (
        "You are curating a workflow wiki for an AI file-system agent.\n"
        "From the raw task fragments below, extract:\n"
        "1. Proven step sequences that led to task success (with OUTCOME_OK)\n"
        "2. Key risks and pitfalls encountered\n"
        "3. Task-type specific insights and shortcuts\n\n"
        "Format as structured Markdown sections with ## headers.\n"
        "Rules: deduplicate, remove outdated entries, prefer concrete over generic."
    ),
}


def _read_page(name: str) -> str:
    """Read a wiki page from pages/. Returns '' if not found."""
    path = _PAGES_DIR / f"{name}.md"
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def load_wiki_base(task_text: str = "") -> str:
    """Load contacts.md + accounts.md for prephase injection.

    FIX-358: `errors.md` НЕ загружается в runtime-prompt агента. Синтез errors.md
    из fragments/errors/ продолжается (curated knowledge base для людей), но
    провальные ран'ы (NONE_CLARIFICATION, DENIED_SECURITY, stall) не должны
    самоподкреплять ложные паттерны через подмешивание в prompt следующих задач.
    Fail-open: returns '' if wiki not yet accumulated.
    task_text is reserved for Phase 3 entity extraction.
    """
    del task_text  # Phase 3: will extract email/names to load matching entity pages
    parts = []
    for name, header in [
        ("contacts", "Wiki: Known Contacts"),
        ("accounts", "Wiki: Known Accounts"),
    ]:
        content = _read_page(name)
        if content:
            parts.append(f"## {header}\n{content}")
    return "\n\n".join(parts)


def load_wiki_patterns(task_type: str, include_negatives: bool = True) -> str:
    """Load patterns page for the given task type.

    include_negatives=True (default) appends a KNOWN DEAD ENDS block from the
    last 5 error fragments for this task_type (FIX-410). Fail-open.
    """
    page_name = _TYPE_TO_PAGE.get(task_type, task_type)
    content = _read_page(page_name)
    parts = []
    if content:
        parts.append(f"## Wiki: {task_type} Patterns\n{content}")
    if include_negatives:
        negatives = _load_dead_ends(task_type)
        if negatives:
            parts.append(negatives)
    return "\n\n".join(parts)


def load_contract_constraints(task_type: str) -> list[dict]:
    """FIX-415: Parse ## Contract constraints section from a wiki page.

    Returns list of {id: str, rule: str} dicts. Fail-open → [].
    """
    page_name = _TYPE_TO_PAGE.get(task_type, task_type)
    content = _read_page(page_name)
    if not content:
        return []

    # Find the ## Contract constraints section
    section_match = re.search(
        r"^## Contract constraints\s*\n(.*?)(?=^## |\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    if not section_match:
        return []

    section = section_match.group(1)
    constraints: list[dict] = []

    # Each constraint starts with <!-- constraint: <id> -->
    # followed by **ID:** line and **Rule:** line
    for block in re.split(r"<!--\s*constraint:\s*\S+\s*-->", section):
        id_match = re.search(r"\*\*ID:\*\*\s*(\S+)", block)
        rule_match = re.search(r"\*\*Rule:\*\*\s*(.*?)(?=\n\n|\n\*\*|\Z)", block, re.DOTALL)
        if id_match and rule_match:
            constraints.append({
                "id": id_match.group(1).strip(),
                "rule": re.sub(r"\s+", " ", rule_match.group(1)).strip(),
            })

    return constraints


def _load_dead_ends(task_type: str) -> str:
    """FIX-410: load last 5 error fragments and format as KNOWN DEAD ENDS block.

    Parses ## Dead end: blocks written by _build_dead_end_block.
    Falls back to frontmatter task_id/outcome for legacy fragments.
    Returns '' if no error fragments exist for this task_type.
    """
    if not _WIKI_NEGATIVES_ENABLED:
        return ""
    domain = _TYPE_TO_PAGE.get(task_type, task_type)
    frag_dir = _FRAGMENTS_DIR / "errors" / domain
    if not frag_dir.exists():
        return ""

    try:
        frags = sorted(frag_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
    except OSError:
        return ""
    if not frags:
        return ""

    entries: list[str] = []
    for frag_path in reversed(frags):  # chronological: oldest first
        try:
            text = frag_path.read_text(encoding="utf-8")
            m = re.search(
                r"^## Dead end: (\S+)\nOutcome: (\S+)\nWhat failed:\n(.*?)(?=\n## |\Z)",
                text, re.MULTILINE | re.DOTALL,
            )
            if m:
                tid, out, what = m.group(1), m.group(2), m.group(3).strip()
                first_fail = what.splitlines()[0] if what.splitlines() else "(unknown)"
                entries.append(f"- {tid} ({out}): {first_fail[:120]}")
            else:
                # Legacy fragment without dead-end block
                tid_m = re.search(r"^task_id: (\S+)", text, re.MULTILINE)
                out_m = re.search(r"^outcome: (\S+)", text, re.MULTILINE)
                if tid_m and out_m:
                    entries.append(f"- {tid_m.group(1)} ({out_m.group(1)}): (legacy fragment)")
        except Exception:
            continue

    if not entries:
        return ""

    header = f"## KNOWN DEAD ENDS ({task_type})"
    # Trim oldest entries if over char limit
    while entries and len(header + "\n" + "\n".join(entries)) > _WIKI_NEGATIVES_MAX_CHARS:
        entries.pop(0)

    return (header + "\n" + "\n".join(entries)) if entries else ""


def _ingest_error_fragments(category: str, n: int = 10) -> list[dict]:
    """FIX-413: parse archived error fragments into antipattern dicts without LLM.

    Reads last N files from archive/errors/{category}/ by mtime (newest first).
    Returns a list of {"text": ..., "tags": [...], "confidence": 0.4} dicts
    suitable for merge_updates(g, {"antipatterns": items}).
    """
    archive_dir = _ARCHIVE_DIR / "errors" / category
    if not archive_dir.exists():
        return []
    try:
        frags = sorted(
            archive_dir.glob("*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:n]
    except OSError:
        return []

    items: list[dict] = []
    for frag_path in frags:
        try:
            text = frag_path.read_text(encoding="utf-8")

            # Try structured dead-end block (FIX-410 format).
            dead_m = re.search(
                r"^## Dead end: \S+\nOutcome: \S+\nWhat failed:\n(.*?)(?=\n## |\Z)",
                text, re.MULTILINE | re.DOTALL,
            )
            if dead_m:
                lines = dead_m.group(1).strip().splitlines()
                first = re.sub(r"^-\s*", "", lines[0]).strip() if lines else ""
                apt_text = first[:120]
            else:
                # Legacy: outcome + first stall description.
                outcome_m = re.search(r"^outcome: (\S+)", text, re.MULTILINE)
                stall_m = re.search(r"- stall:.*?→ (.{10,80})", text)
                outcome = outcome_m.group(1) if outcome_m else "OUTCOME_FAIL"
                stall = stall_m.group(1).strip() if stall_m else ""
                apt_text = f"{outcome}: {stall[:80]}" if stall else outcome

            apt_text = _scrub_entity(apt_text.strip())
            if apt_text and len(apt_text) > 10:
                items.append({"text": apt_text, "tags": [category], "confidence": 0.4})
        except Exception:
            continue

    return items


_ENTITY_PATTERNS = [
    (re.compile(r"\bcont_\d+\b", re.IGNORECASE), "<contact>"),
    (re.compile(r"\bacct_\d+\b", re.IGNORECASE), "<account>"),
    (re.compile(r"\bmgr_\d+\b", re.IGNORECASE), "<manager>"),
    (re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"), "<email>"),
    (re.compile(r"/contacts/[^\s)\]]+"), "/contacts/<file>"),
    (re.compile(r"/accounts/[^\s)\]]+"), "/accounts/<file>"),
    (re.compile(r"/outbox/[^\s)\]]+"), "/outbox/<file>"),
    (re.compile(r"/inbox/[^\s)\]]+"), "/inbox/<file>"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "<date>"),
]


def _scrub_entity(text: str) -> str:
    """FIX-362: redact vault-specific identifiers so promoted patterns stay abstract.

    Strips cont_NNN / acct_NNN / mgr_NNN, email addresses, concrete entity file
    paths, and ISO dates. Preserves overall structure so the trajectory remains
    readable as a shape.
    """
    if not text:
        return text
    for pat, repl in _ENTITY_PATTERNS:
        text = pat.sub(repl, text)
    return text


def promote_successful_pattern(
    task_type: str,
    task_id: str,
    traj_hash: str,
    trajectory: list[dict],
    insights: list[str],
    goal_shape: str = "",
    final_answer: str = "",
    max_patterns: int = 10,
) -> bool:
    """Promote a verified success trajectory into pages/<task_type>.md.

    Idempotent by (task_id, traj_hash): repeated promotion of the same
    trajectory is a no-op. Oldest patterns are rotated to archive/ when
    page accumulates > max_patterns entries.

    trajectory: list of {"tool": str, "path": str, "summary": str} dicts.
    goal_shape / final_answer: abstract single-sentence summaries from reflector.

    Returns True if a new pattern was written, False if it was already present.
    """
    page_name = _TYPE_TO_PAGE.get(task_type, task_type)
    page_path = _PAGES_DIR / f"{page_name}.md"
    page_path.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_page(page_name)

    marker = f"<!-- researcher: {task_id}:{traj_hash} -->"
    if marker in existing:
        return False

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines: list[str] = []
    for i, step in enumerate(trajectory, 1):
        tool = _scrub_entity(str(step.get("tool", "") or "?"))
        path = _scrub_entity(str(step.get("path", "") or ""))
        summary = _scrub_entity(str(step.get("summary", "") or ""))[:140]
        head = f"{tool}({path})" if path else tool
        lines.append(f"{i}. {head}" + (f" — {summary}" if summary else ""))
    traj_block = "\n".join(lines) or "(no trajectory)"
    insights_block = "\n".join(f"- {_scrub_entity(ins)}" for ins in insights) or "- (none)"
    goal_line = _scrub_entity(goal_shape).strip() or "(unspecified)"
    answer_line = _scrub_entity(final_answer).strip() or "(unspecified)"
    new_section = (
        f"\n\n## Successful pattern: {task_id} ({ts})\n"
        f"{marker}\n\n"
        f"**Goal shape:** {goal_line}\n\n"
        f"**Final answer:** {answer_line}\n\n"
        f"**Trajectory:**\n{traj_block}\n\n"
        f"**Key insights:**\n{insights_block}\n\n"
        f"**Applies when:** {task_type}\n"
    )

    merged = (existing.rstrip() + new_section) if existing else new_section.lstrip()

    # Rotate oldest sections if above cap.
    sections = re.split(r"(?m)^## Successful pattern: ", merged)
    # sections[0] = preamble; sections[1:] = individual patterns (without the leading "## Successful pattern: ")
    if len(sections) - 1 > max_patterns:
        keep_n = max_patterns
        preamble = sections[0]
        patterns = sections[1:]
        archived = patterns[: len(patterns) - keep_n]
        kept = patterns[len(patterns) - keep_n :]
        archive_dir = _ARCHIVE_DIR / "patterns" / page_name
        archive_dir.mkdir(parents=True, exist_ok=True)
        for idx, pat in enumerate(archived):
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            archive_path = archive_dir / f"{page_name}_{stamp}_{idx}.md"
            archive_path.write_text("## Successful pattern: " + pat, encoding="utf-8")
        merged = preamble + "".join("## Successful pattern: " + p for p in kept)

    page_path.write_text(merged, encoding="utf-8")
    if _LOG_LEVEL == "DEBUG":
        print(f"[wiki] promoted pattern {task_id}:{traj_hash[:8]} → {page_path}")
    return True


def promote_verified_refusal(
    task_type: str,
    task_id: str,
    outcome: str,
    goal_shape: str,
    refusal_reason: str,
    trajectory: list[dict],
    max_refusals: int = 10,
) -> bool:
    """FIX-366: promote a verified-correct refusal into pages/<task_type>.md.

    A refusal is "verified" when benchmark score == 1.0 (the graders agreed the
    correct action was to refuse) AND the agent returned one of the terminal
    refusal outcomes (NONE_CLARIFICATION, NONE_UNSUPPORTED, DENIED_SECURITY).
    Lives in its own section (## Verified refusal:) so patterns and refusals
    don't fight for space.

    Idempotent via <!-- refusal: task_id:outcome_hash --> marker. Rotation at
    max_refusals into archive/refusals/<page>.
    """
    page_name = _TYPE_TO_PAGE.get(task_type, task_type)
    page_path = _PAGES_DIR / f"{page_name}.md"
    page_path.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_page(page_name)

    marker = f"<!-- refusal: {task_id}:{outcome} -->"
    if marker in existing:
        return False

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    goal_line = _scrub_entity(goal_shape).strip() or "(unspecified)"
    reason_line = _scrub_entity(refusal_reason).strip() or "(unspecified)"
    traj_lines: list[str] = []
    for i, step in enumerate(trajectory[:6], 1):
        tool = _scrub_entity(str(step.get("tool", "") or "?"))
        path = _scrub_entity(str(step.get("path", "") or ""))
        head = f"{tool}({path})" if path else tool
        traj_lines.append(f"{i}. {head}")
    probe_block = "\n".join(traj_lines) or "(no discovery steps)"

    new_section = (
        f"\n\n## Verified refusal: {task_id} ({ts})\n"
        f"{marker}\n\n"
        f"**Goal shape:** {goal_line}\n\n"
        f"**Outcome:** {outcome}\n\n"
        f"**Why refuse:** {reason_line}\n\n"
        f"**Probes before refusal:**\n{probe_block}\n\n"
        f"**Applies when:** {task_type}\n"
    )

    merged = (existing.rstrip() + new_section) if existing else new_section.lstrip()

    sections = re.split(r"(?m)^## Verified refusal: ", merged)
    if len(sections) - 1 > max_refusals:
        preamble = sections[0]
        refusals = sections[1:]
        archived = refusals[: len(refusals) - max_refusals]
        kept = refusals[len(refusals) - max_refusals :]
        archive_dir = _ARCHIVE_DIR / "refusals" / page_name
        archive_dir.mkdir(parents=True, exist_ok=True)
        for idx, r in enumerate(archived):
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            (archive_dir / f"{page_name}_{stamp}_{idx}.md").write_text(
                "## Verified refusal: " + r, encoding="utf-8"
            )
        merged = preamble + "".join("## Verified refusal: " + r for r in kept)

    page_path.write_text(merged, encoding="utf-8")
    if _LOG_LEVEL == "DEBUG":
        print(f"[wiki] promoted refusal {task_id}:{outcome} → {page_path}")
    return True


def write_fragment(task_id: str, category: str, content: str) -> None:
    """Write an append-only fragment to fragments/{category}/{task_id}_{ts}.md.

    Thread-safe: unique filename per call, no read-modify-write.
    FIX-N+6: task_id is sanitized to a flat ASCII slug so that callers deriving
    it from task_text (which may contain '/') don't produce ENOENT on write.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_task_id = _TASK_ID_SANITIZE_RE.sub("_", task_id).strip("_") or "task"
    frag_dir = _FRAGMENTS_DIR / category
    frag_dir.mkdir(parents=True, exist_ok=True)
    path = frag_dir / f"{safe_task_id}_{ts}.md"
    path.write_text(content, encoding="utf-8")
    if _LOG_LEVEL == "DEBUG":
        print(f"[wiki] fragment written: {path}")


def _build_raw_fragment(
    outcome: str,
    task_type: str,
    task_id: str,
    task_text: str,
    today: str,
    step_facts: list,
    done_ops: list,
    stall_hints: list,
    eval_last_call: dict | None,
) -> str:
    """Build a raw structured fragment with all available data for LLM synthesis."""
    ops_str = "\n".join(f"- {op}" for op in done_ops) if done_ops else "(none)"
    facts_str = "\n".join(
        f"- {f.kind}: {f.path} → {f.summary}"
        for f in step_facts
        if hasattr(f, "kind")
    ) or "(none)"
    hints_str = "\n".join(f"- {h}" for h in stall_hints) if stall_hints else ""

    eval_section = ""
    if eval_last_call:
        approved = "true" if outcome == "OUTCOME_OK" else "false"
        steps = eval_last_call.get("completed_steps", "")
        eval_section = f"\nEVALUATOR:\napproved: {approved}\nsteps: {steps}\n"

    stall_section = f"\nSTALL HINTS:\n{hints_str}\n" if hints_str else ""

    return (
        f"---\n"
        f"task_id: {task_id}\n"
        f"task_type: {task_type}\n"
        f"outcome: {outcome}\n"
        f"date: {today}\n"
        f"task: {task_text[:200]!r}\n"
        f"---\n\n"
        f"DONE OPS:\n{ops_str}\n\n"
        f"STEP FACTS:\n{facts_str}\n"
        f"{eval_section}"
        f"{stall_section}"
    )


def _build_entity_raw(task_id: str, today: str, facts: list) -> str:
    """Build a raw entity fragment from contact/account step_facts."""
    facts_str = "\n".join(
        f"- {f.kind}: {f.path} → {f.summary}"
        for f in facts
        if hasattr(f, "kind")
    )
    return (
        f"---\n"
        f"task_id: {task_id}\n"
        f"date: {today}\n"
        f"---\n\n"
        f"{facts_str}\n"
    )


def _build_dead_end_block(task_id: str, outcome: str, step_facts: list) -> str:
    """FIX-410: structured dead-end block appended to error fragments."""
    error_facts = [f for f in step_facts if hasattr(f, "error") and f.error]
    what_failed_lines = [
        f"- {f.kind}({f.path}): {f.error[:100]}"
        for f in error_facts
    ] or ["- (see outcome above)"]
    return (
        f"\n## Dead end: {task_id}\n"
        f"Outcome: {outcome}\n"
        f"What failed:\n" + "\n".join(what_failed_lines) + "\n"
    )


def format_fragment(
    outcome: str,
    task_type: str,
    task_id: str,
    task_text: str,
    step_facts: list,
    done_ops: list,
    stall_hints: list,
    eval_last_call: dict | None,
    score: float = -1.0,
) -> list[tuple[str, str]]:
    """Format wiki fragments gated by benchmark score (FIX-358).

    Returns list of (content, category) pairs. Empty list = nothing to write.

    Score routing:
      score == 1.0  → success: category = task_type (e.g. `temporal`, `crm`)
      score  < 1.0  → failure: category = `errors/<task_type>` (nested, domain-separated)
      score == -1.0 → legacy fallback: gate by self-reported outcome (unused
                      in main.py path — kept for safety if called without score).

    Entity fragments (contacts/accounts) — only on score == 1.0: incorrect runs
    may contain mis-extracted entity data. On failure we don't pollute entity pages.
    """
    results: list[tuple[str, str]] = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Score-gated routing (FIX-358)
    if score >= 1.0:
        # Success path: write success fragment into task_type page
        raw = _build_raw_fragment(
            outcome, task_type, task_id, task_text, today,
            step_facts, done_ops, stall_hints, eval_last_call,
        )
        category = task_type if task_type in _TYPE_TO_PAGE else "default"
        results.append((raw, category))

        # Entity fragments — only on verified success
        contact_facts = [
            f for f in step_facts
            if hasattr(f, "path") and "contacts/" in (f.path or "")
        ]
        account_facts = [
            f for f in step_facts
            if hasattr(f, "path") and "accounts/" in (f.path or "")
        ]
        if contact_facts:
            results.append((_build_entity_raw(task_id, today, contact_facts), "contacts"))
        if account_facts:
            results.append((_build_entity_raw(task_id, today, account_facts), "accounts"))
        return results

    if 0.0 <= score < 1.0:
        # Failure path: domain-separated errors (not mixed into pages used at runtime)
        raw = _build_raw_fragment(
            outcome, task_type, task_id, task_text, today,
            step_facts, done_ops, stall_hints, eval_last_call,
        )
        domain = task_type if task_type in _TYPE_TO_PAGE else "default"
        raw += _build_dead_end_block(task_id, outcome, step_facts)  # FIX-410
        results.append((raw, f"errors/{domain}"))
        return results

    # Legacy path (score == -1.0, caller didn't pass score) — conservative default:
    # behave as before to avoid data loss, but this branch should be dead in prod.
    write_main = outcome in (
        "OUTCOME_OK", "OUTCOME_DENIED_SECURITY", "OUTCOME_NONE_CLARIFICATION",
    ) or bool(stall_hints)
    if write_main:
        raw = _build_raw_fragment(
            outcome, task_type, task_id, task_text, today,
            step_facts, done_ops, stall_hints, eval_last_call,
        )
        category = task_type if outcome == "OUTCOME_OK" else "errors"
        if category not in _TYPE_TO_PAGE:
            category = "errors"
        results.append((raw, category))
    return results


def run_wiki_lint(model: str = "", cfg: dict | None = None) -> None:
    """Merge fragments into pages via LLM synthesis (Variant C).

    Called twice per make run: before and after ThreadPoolExecutor.
    For each category: reads all fragments, calls LLM synthesis (or concat fallback),
    writes to pages/, archives processed fragments.
    Fail-open: if anything fails, logs and continues.
    """
    if cfg is None:
        cfg = {}
    if not _FRAGMENTS_DIR.exists():
        return

    # FIX-358: categories include top-level (e.g. `temporal`, `crm`) and
    # nested `errors/<domain>` subdirs. Errors pages land at `pages/errors/<domain>.md`
    # (not loaded into runtime prompts — curated-only, domain-separated history).
    categories: list[str] = []
    for top in sorted(_FRAGMENTS_DIR.iterdir()):
        if not top.is_dir():
            continue
        # Skip research/* — not processed by LLM lint synthesis.
        if top.name == "research":
            continue
        if top.name == "errors":
            for sub in sorted(top.iterdir()):
                if sub.is_dir():
                    categories.append(f"errors/{sub.name}")
        else:
            categories.append(top.name)

    if not categories:
        return

    # FIX-390: skip lint entirely when no category has fragments. Avoids the
    # noisy "processing N categories" log followed by zero work and keeps
    # pre-run lint silent on cold start.
    has_any = any(
        any((_FRAGMENTS_DIR / c).glob("*.md")) for c in categories
    )
    if not has_any:
        return

    print(f"[wiki-lint] processing {len(categories)} categories: {categories}")

    # FIX-390: per-category persistence. Previously aggregated all deltas and
    # called merge_updates+save_graph once at the end (agent/wiki.py:693). If
    # the process was killed mid-loop (CC quota, SIGTERM) the entire graph
    # contribution was lost — observed in run 20260425_210938 where lint died
    # after 2/18 categories with no graph.json written. Now save after each
    # successful synthesis so kill-mid-loop loses at most one category.
    graph_module = None
    graph_state = None
    if _GRAPH_AUTOBUILD:
        try:
            from . import wiki_graph as _wg
            graph_module = _wg
            graph_state = _wg.load_graph()
        except Exception as e:
            print(f"[wiki-graph] init failed ({e}) — graph autobuild disabled this run")
            graph_module = None

    n_total_items = 0
    n_total_touched = 0

    for category in categories:
        frag_dir = _FRAGMENTS_DIR / category
        fragments = sorted(frag_dir.glob("*.md"))
        if not fragments:
            continue

        existing = _read_page(category)
        new_entries = [f.read_text(encoding="utf-8") for f in fragments]

        merged, deltas = _llm_synthesize(existing, new_entries, category, model, cfg)
        merged = _sanitize_synthesized_page(merged)  # FIX-328

        page_path = _PAGES_DIR / f"{category}.md"
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(merged, encoding="utf-8")

        archive_dir = _ARCHIVE_DIR / category
        archive_dir.mkdir(parents=True, exist_ok=True)
        for f in fragments:
            f.rename(archive_dir / f.name)

        # FIX-390: per-category diagnostic + immediate persist.
        if graph_module is not None and graph_state is not None:
            n_ins = len(deltas.get("new_insights") or []) if isinstance(deltas, dict) else 0
            n_rul = len(deltas.get("new_rules") or []) if isinstance(deltas, dict) else 0
            n_apt = len(deltas.get("antipatterns") or []) if isinstance(deltas, dict) else 0
            print(
                f"[wiki-graph] {category}: deltas insights={n_ins} rules={n_rul} antipatterns={n_apt}"
            )
            if deltas and (n_ins or n_rul or n_apt):
                _stamp_category_tag(deltas, category)
                try:
                    touched = graph_module.merge_updates(graph_state, deltas)
                    graph_module.save_graph(graph_state)
                    n_total_items += n_ins + n_rul + n_apt
                    n_total_touched += len(touched)
                    print(
                        f"[wiki-graph] {category}: persisted, touched {len(touched)} nodes"
                    )
                except Exception as e:
                    print(f"[wiki-graph] {category}: merge failed: {e}")

        print(f"[wiki-lint] {category}: synthesized {len(fragments)} fragments → {category}.md")

    if graph_module is not None and n_total_items:
        print(
            f"[wiki-graph] run total: {n_total_items} delta items, {n_total_touched} node touches"
        )

    # FIX-412: pages lint pass — extract graph_deltas from compiled pages.
    if graph_module is not None and graph_state is not None:
        try:
            _run_pages_lint_pass(graph_module, graph_state, model, cfg)
        except Exception as _plp_exc:
            print(f"[wiki-graph] pages-lint pass failed ({_plp_exc})")

    # FIX-413: error fragment ingest — antipattern nodes from archive/errors/.
    if graph_module is not None and graph_state is not None and _GRAPH_ERRORS_INGEST:
        _errors_dir = _ARCHIVE_DIR / "errors"
        _error_cats = (
            [c.name for c in _errors_dir.iterdir() if c.is_dir()]
            if _errors_dir.exists() else []
        )
        for _ec in _error_cats:
            _items = _ingest_error_fragments(_ec)
            if _items:
                try:
                    _touched = graph_module.merge_updates(graph_state, {"antipatterns": _items})
                    graph_module.save_graph(graph_state)
                    print(f"[wiki-graph] error-ingest '{_ec}': {len(_touched)} antipattern nodes")
                except Exception as _ei_exc:
                    print(f"[wiki-graph] error-ingest '{_ec}' failed ({_ei_exc})")


def _stamp_category_tag(deltas: dict, category: str) -> None:
    """FIX-389: ensure every item in deltas has the category in its tags list.
    Mutates in place. Robust to malformed item shapes."""
    for key in ("new_insights", "new_rules", "antipatterns"):
        items = deltas.get(key)
        if not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            tags = it.get("tags")
            if not isinstance(tags, list):
                tags = []
            if category not in tags:
                tags = [*tags, category]
            it["tags"] = tags


def _llm_synthesize(
    existing: str,
    new_entries: list[str],
    category: str,
    model: str,
    cfg: dict,
) -> tuple[str, dict]:
    """Synthesize wiki page from fragments via LLM. Fallback: concat.

    FIX-389: returns (markdown, graph_deltas). graph_deltas is empty when
    autobuild is off, when the LLM omits the JSON fence, or when parsing fails.
    """
    if not model:
        return _concat_merge(existing, new_entries), {}

    # FIX-360: skip LLM synthesis when there's nothing to merge (single new
    # fragment, empty existing page). Concat is equivalent, and the CC tier
    # often returns empty result here (model attempts a banned built-in tool,
    # tool_use block is stripped, result="" → 3×retry before fallback).
    if len(new_entries) == 1 and not (existing or "").strip():
        return _concat_merge(existing, new_entries), {}

    # FIX-358: errors/<domain> categories fall back to the errors-synthesis prompt
    if category.startswith("errors/") and category not in _LINT_PROMPTS:
        synthesis_prompt = _LINT_PROMPTS.get("errors", _LINT_PROMPTS["_pattern_default"])
    else:
        synthesis_prompt = _LINT_PROMPTS.get(category, _LINT_PROMPTS["_pattern_default"])
    combined_new = "\n\n---\n\n".join(new_entries)
    graph_suffix = _GRAPH_INSTRUCTION_SUFFIX if _GRAPH_AUTOBUILD else ""
    user_msg = (
        f"{synthesis_prompt}\n\n"
        f"EXISTING PAGE:\n{existing or '(empty)'}\n\n"
        f"NEW FRAGMENTS:\n{combined_new}\n\n"
        f"Output the merged Markdown content first, no preamble."
        f"{graph_suffix}"
    )

    try:
        from .dispatch import call_llm_raw
        response = call_llm_raw(
            system="You are a knowledge curator. Output only clean Markdown, no commentary.",
            user_msg=user_msg,
            model=model,
            cfg=cfg,
            max_tokens=4000,
            plain_text=True,
        )
        if response and len(response) > 50:
            markdown, deltas = _split_markdown_and_deltas(response)
            return markdown, deltas
    except Exception as e:
        print(f"[wiki-lint] LLM synthesis failed for '{category}' ({e}), using concat")

    return _concat_merge(existing, new_entries), {}


def _split_markdown_and_deltas(response: str) -> tuple[str, dict]:
    """FIX-403: extract graph_deltas from synthesis response.

    Search order:
    1. Any ```json ... ``` fenced block containing graph_deltas key (any position).
    2. Bare `graph_deltas: {...}` marker in response text.
    3. Fail-open: return (response, {}).

    Tries json.loads first, json5 as fallback (trailing commas / single quotes).
    """
    if not _GRAPH_AUTOBUILD:
        return response, {}
    import json as _json

    def _parse(raw: str) -> dict | None:
        try:
            return _json.loads(raw)
        except Exception:
            pass
        try:
            from agent.json_extract import _try_json5
            return _try_json5(raw)
        except Exception:
            return None

    # 1. Fenced ```json ... ``` block — search any position
    for m in _JSON_FENCE_RE.finditer(response):
        parsed = _parse(m.group(1))
        if isinstance(parsed, dict) and isinstance(parsed.get("graph_deltas"), dict):
            markdown = (response[:m.start()] + response[m.end():]).strip()
            return markdown, parsed["graph_deltas"]

    # 2. Bare graph_deltas: {...} marker (no fence)
    bare = re.search(r'"?graph_deltas"?\s*:\s*(\{.*?\})\s*$', response, re.DOTALL)
    if bare:
        parsed = _parse(bare.group(1))
        if isinstance(parsed, dict):
            print("[wiki-graph] fence: found bare graph_deltas marker")
            return response, parsed

    print("[wiki-graph] fence: missing — LLM did not emit ```json block")
    return response, {}


def _concat_merge(existing: str, new_entries: list[str]) -> str:
    return "\n\n".join(p for p in [existing, *new_entries] if p)


# FIX-328: strip negative-boilerplate lines that the LLM synthesizer occasionally
# emits ("Halt and request clarification", "No OUTCOME_OK recorded", etc.).
# These lines poison lookup/temporal/inbox prompts and push the agent toward
# premature OUTCOME_NONE_CLARIFICATION (see failures t16, t29, t30, t34, t38, t40).
_NEGATIVE_BOILERPLATE_PATTERNS = [
    re.compile(r"(?im)^.*\bHalt and request clarification\b.*$"),
    re.compile(r"(?im)^.*\bstop for clarification instead of guessing\b.*$"),
    re.compile(r"(?im)^.*\bNo\s+`?OUTCOME_OK`?\s+signal\s+yet\b.*$"),
    re.compile(r"(?im)^.*\bNo\s+`?OUTCOME_OK`?\s+recorded\b.*$"),
    re.compile(r"(?im)^.*\bNo\s+OUTCOME_OK\b.*$"),
    re.compile(r"(?im)^.*\bcandidate patterns?\b.*\buntil\b.*$"),
    re.compile(r"(?im)^.*\bunverified\b.*\bdo not treat\b.*$"),
    re.compile(r"(?im)^>\s*No\s+`?OUTCOME_OK`?\s+marker.*$"),
    # FIX-361: broader clarification-bias catchers. The sanitizer already killed
    # "Halt and request clarification"; these cover the paraphrases that leaked
    # into email/default/accounts pages and drove a 66% regression run by
    # pushing the agent to premature OUTCOME_NONE_CLARIFICATION. Do NOT match
    # the full enum form `OUTCOME_NONE_CLARIFICATION` — queue.md legitimately
    # uses it (protected by FIX-351).
    re.compile(r"(?im)^.*\breturn clarification\b.*$"),
    re.compile(r"(?im)^.*\bescalate to clarification\b.*$"),
    re.compile(r"(?im)^.*=\s*clarification\b(?!\s*[A-Z_]).*$"),
    re.compile(r"(?im)^.*\bclarification,\s*not\s+guessing\b.*$"),
    re.compile(r"(?im)^.*\bclarification,\s*never\s+a\s+write\b.*$"),
]


def _sanitize_synthesized_page(content: str) -> str:
    """FIX-328: Remove negative-boilerplate lines from synthesized wiki page.

    FIX-363c: also run _scrub_entity to strip entity-specific data (cont_NNN,
    acct_NNN, email addresses, concrete filenames, ISO dates) that LLM
    synthesis tends to re-introduce from fragments. This enforces the FIX-337
    abstraction policy across the whole lint pipeline, not just promotion.
    """
    if not content:
        return content
    for p in _NEGATIVE_BOILERPLATE_PATTERNS:
        content = p.sub("", content)
    content = _scrub_entity(content)
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip() + "\n"


def _run_pages_lint_pass(graph_module, graph_state, model: str, cfg: dict) -> None:
    """FIX-412: extract graph_deltas from compiled wiki pages.

    Pages contain verified/promoted patterns — confidence=0.7 (above fragment default 0.6).
    Adds 'wiki_page' tag so nodes from this pass can be identified.
    Called at end of run_wiki_lint when graph_module is available.
    """
    if not _GRAPH_AUTOBUILD or not model:
        return
    if not _PAGES_DIR.exists():
        return
    pages = [p for p in sorted(_PAGES_DIR.glob("*.md")) if p.is_file()]
    if not pages:
        return

    n_touched = 0
    for page_path in pages:
        category = page_path.stem
        try:
            content = page_path.read_text(encoding="utf-8")
            if not content.strip():
                continue

            user_msg = (
                f"{_PAGES_GRAPH_PROMPT}\n\n"
                f"PAGE ({category}):\n{content[:6000]}"
            )
            try:
                from . import dispatch as _dispatch
                response = _dispatch.call_llm_raw(
                    system="You are a knowledge graph curator. Output only the JSON fence block.",
                    user_msg=user_msg,
                    model=model,
                    cfg=cfg,
                    max_tokens=1000,
                    plain_text=True,
                )
            except Exception as exc:
                print(f"[wiki-graph] pages-lint '{category}' LLM failed ({exc}), skipping")
                continue

            if not response:
                continue
            _, deltas = _split_markdown_and_deltas(response)
            if not deltas:
                continue

            _stamp_category_tag(deltas, category)
            for key in ("new_insights", "new_rules", "antipatterns"):
                for item in (deltas.get(key) or []):
                    if isinstance(item, dict):
                        tags = item.get("tags") or []
                        if "wiki_page" not in tags:
                            item["tags"] = [*tags, "wiki_page"]

            try:
                touched = graph_module.merge_updates(graph_state, deltas)
                graph_module.save_graph(graph_state)
                n_touched += len(touched)
                print(f"[wiki-graph] pages-lint '{category}': touched {len(touched)} nodes")
            except Exception as exc:
                print(f"[wiki-graph] pages-lint '{category}' merge failed ({exc})")
        except Exception as exc:
            print(f"[wiki-graph] pages-lint '{category}' error ({exc}), skipping")

    if n_touched:
        print(f"[wiki-graph] pages-lint total: {n_touched} node touches")
