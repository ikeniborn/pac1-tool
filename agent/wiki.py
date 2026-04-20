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
from datetime import datetime, timezone
from pathlib import Path

_WIKI_DIR = Path(__file__).parent.parent / "data" / "wiki"
_PAGES_DIR = _WIKI_DIR / "pages"
_FRAGMENTS_DIR = _WIKI_DIR / "fragments"
_ARCHIVE_DIR = _WIKI_DIR / "archive"

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# Task type → wiki page name mapping
_TYPE_TO_PAGE: dict[str, str] = {
    "email": "email",
    "inbox": "inbox",
    "crm": "crm",
    "lookup": "lookup",
    "temporal": "temporal",
    "queue": "queue",
    "capture": "capture",
    "distill": "distill",
    "think": "think",
    "default": "default",
}

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
        "remove entries with no actionable solution, merge similar patterns."
    ),
    "contacts": (
        "You are curating a workflow wiki for an AI file-system agent.\n"
        "From the raw task fragments below, extract:\n"
        "1. Proven step sequences that led to task success (with OUTCOME_OK)\n"
        "2. Key risks and pitfalls encountered\n"
        "3. Task-type specific insights and shortcuts\n\n"
        "Format as structured Markdown sections with ## headers.\n"
        "Rules: deduplicate, remove outdated entries, prefer concrete over generic.\n"
        "IMPORTANT: do NOT add individual contact entries — do NOT output ## email, "
        "## cont_NNN, ## <name> sections. Output only patterns, steps, and pitfalls."
    ),
    "accounts": (
        "You are curating a workflow wiki for an AI file-system agent.\n"
        "From the raw task fragments below, extract:\n"
        "1. Proven step sequences that led to task success (with OUTCOME_OK)\n"
        "2. Key risks and pitfalls encountered\n"
        "3. Task-type specific insights and shortcuts\n\n"
        "Format as structured Markdown sections with ## headers.\n"
        "Rules: deduplicate, remove outdated entries, prefer concrete over generic.\n"
        "IMPORTANT: do NOT add individual account entries — do NOT output ## acct_NNN, "
        "## <company> sections. Output only patterns, steps, and pitfalls."
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
        "or entries like 'Handle X verified via Y'. Output only general patterns and steps."
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
    """Load errors.md + contacts.md + accounts.md for prephase injection.

    Fail-open: returns '' if wiki not yet accumulated.
    task_text is reserved for Phase 3 entity extraction.
    """
    del task_text  # Phase 3: will extract email/names to load matching entity pages
    parts = []
    for name, header in [
        ("errors",   "Wiki: Known Errors & Solutions"),
        ("contacts", "Wiki: Known Contacts"),
        ("accounts", "Wiki: Known Accounts"),
    ]:
        content = _read_page(name)
        if content:
            parts.append(f"## {header}\n{content}")
    return "\n\n".join(parts)


def load_wiki_patterns(task_type: str) -> str:
    """Load patterns page for the given task type.

    Fail-open: returns '' if page doesn't exist.
    """
    page_name = _TYPE_TO_PAGE.get(task_type, task_type)
    content = _read_page(page_name)
    if content:
        return f"## Wiki: {task_type} Patterns\n{content}"
    return ""


def write_fragment(task_id: str, category: str, content: str) -> None:
    """Write an append-only fragment to fragments/{category}/{task_id}_{ts}.md.

    Thread-safe: unique filename per call, no read-modify-write.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    frag_dir = _FRAGMENTS_DIR / category
    frag_dir.mkdir(parents=True, exist_ok=True)
    path = frag_dir / f"{task_id}_{ts}.md"
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


def format_fragment(
    outcome: str,
    task_type: str,
    task_id: str,
    task_text: str,
    step_facts: list,
    done_ops: list,
    stall_hints: list,
    eval_last_call: dict | None,
) -> list[tuple[str, str]]:
    """Format wiki fragments based on task outcome.

    Returns list of (content, category) pairs. Empty list = nothing to write.
    Always extracts entity fragments from step_facts regardless of outcome.
    """
    results: list[tuple[str, str]] = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Main outcome fragment
    write_main = outcome in (
        "OUTCOME_OK",
        "OUTCOME_DENIED_SECURITY",
        "OUTCOME_NONE_CLARIFICATION",
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

    # Entity fragments — always extract from step_facts, independent of outcome
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

    categories = [d.name for d in _FRAGMENTS_DIR.iterdir() if d.is_dir()]
    if not categories:
        return

    print(f"[wiki-lint] processing {len(categories)} categories: {categories}")

    for category in sorted(categories):
        frag_dir = _FRAGMENTS_DIR / category
        fragments = sorted(frag_dir.glob("*.md"))
        if not fragments:
            continue

        existing = _read_page(category)
        new_entries = [f.read_text(encoding="utf-8") for f in fragments]

        merged = _llm_synthesize(existing, new_entries, category, model, cfg)

        _PAGES_DIR.mkdir(parents=True, exist_ok=True)
        (_PAGES_DIR / f"{category}.md").write_text(merged, encoding="utf-8")

        archive_dir = _ARCHIVE_DIR / category
        archive_dir.mkdir(parents=True, exist_ok=True)
        for f in fragments:
            f.rename(archive_dir / f.name)

        print(f"[wiki-lint] {category}: synthesized {len(fragments)} fragments → {category}.md")


def _llm_synthesize(
    existing: str,
    new_entries: list[str],
    category: str,
    model: str,
    cfg: dict,
) -> str:
    """Synthesize wiki page from fragments via LLM. Fallback: concat."""
    if not model:
        return _concat_merge(existing, new_entries)

    synthesis_prompt = _LINT_PROMPTS.get(category, _LINT_PROMPTS["_pattern_default"])
    combined_new = "\n\n---\n\n".join(new_entries)
    user_msg = (
        f"{synthesis_prompt}\n\n"
        f"EXISTING PAGE:\n{existing or '(empty)'}\n\n"
        f"NEW FRAGMENTS:\n{combined_new}\n\n"
        f"Output only the merged Markdown content, no preamble."
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
            return response
    except Exception as e:
        print(f"[wiki-lint] LLM synthesis failed for '{category}' ({e}), using concat")

    return _concat_merge(existing, new_entries)


def _concat_merge(existing: str, new_entries: list[str]) -> str:
    return "\n\n".join(p for p in [existing, *new_entries] if p)
