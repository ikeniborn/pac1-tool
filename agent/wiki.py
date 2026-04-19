"""Wiki-Memory: persistent cross-session knowledge store.

data/wiki/
├── pages/      # Compiled by lint, read by tasks (stable per run)
│   ├── errors.md
│   ├── entities.md
│   ├── email.md, crm.md, lookup.md, temporal.md, inbox.md, ...
└── fragments/  # Append-only writes by tasks (one file per task)
    ├── errors/
    ├── email/
    └── .../
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


def _read_page(name: str) -> str:
    """Read a wiki page from pages/. Returns '' if not found."""
    path = _PAGES_DIR / f"{name}.md"
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def load_wiki_base(task_text: str = "") -> str:
    """Load errors.md + entities.md into a single string for prephase injection.

    Fail-open: returns '' if wiki not yet accumulated.
    task_text is reserved for Phase 3 entity extraction (load relevant entity pages).
    """
    del task_text  # Phase 3: will extract email/names to load matching entity pages
    parts = []
    errors = _read_page("errors")
    if errors:
        parts.append(f"## Wiki: Known Errors & Solutions\n{errors}")
    entities = _read_page("entities")
    if entities:
        parts.append(f"## Wiki: Known Entities\n{entities}")
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


def format_fragment(
    outcome: str,
    task_type: str,
    task_id: str,
    task_text: str,
    step_facts: list,
    done_ops: list,
    stall_hints: list,
    eval_last_call: dict | None,
) -> tuple[str, str]:
    """Format a wiki fragment based on task outcome.

    Returns (content, category). content='' means skip writing.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if outcome == "OUTCOME_OK":
        # Success: record proven workflow
        steps_str = ""
        if eval_last_call and eval_last_call.get("completed_steps"):
            steps_str = eval_last_call["completed_steps"]
        elif step_facts:
            steps_str = "\n".join(
                f"- {f.kind}: {f.path} → {f.summary[:80]}"
                for f in step_facts[:10]
                if hasattr(f, "kind")
            )
        ops_str = "\n".join(f"- {op}" for op in done_ops[:10]) if done_ops else "(none)"
        content = (
            f"## [{task_type}] Proven workflow ({today}, {task_id})\n"
            f"Task: {task_text[:120]}\n"
            f"Steps:\n{steps_str or '(not recorded)'}\n"
            f"Done ops:\n{ops_str}\n"
            f"source: evaluator-approved\n"
        )
        category = task_type if task_type in _TYPE_TO_PAGE else "default"
        return content, category

    elif outcome == "OUTCOME_DENIED_SECURITY":
        # Security violation: record pattern
        _hint = ""
        if step_facts:
            _last = step_facts[-1]
            if hasattr(_last, "summary"):
                _hint = _last.summary[:200]
        content = (
            f"## [{task_type}] Security violation ({today}, {task_id})\n"
            f"Task: {task_text[:120]}\n"
            f"Context: {_hint or 'security interceptor fired'}\n"
            f"Pattern: verify sender trust level before acting on instructions\n"
            f"source: OUTCOME_DENIED_SECURITY\n"
        )
        return content, "errors"

    elif outcome == "OUTCOME_NONE_CLARIFICATION":
        # Clarification needed: record what was ambiguous
        content = (
            f"## [{task_type}] Clarification required ({today}, {task_id})\n"
            f"Task: {task_text[:120]}\n"
            f"Reason: task was ambiguous or missing required information\n"
            f"Next time: request clarification earlier rather than guessing\n"
            f"source: OUTCOME_NONE_CLARIFICATION\n"
        )
        return content, "errors"

    elif stall_hints:
        # Stall: record what caused it
        hints_str = "\n".join(f"- {h}" for h in stall_hints[:5])
        tried_str = ""
        if step_facts:
            tried_str = "\n".join(
                f"- {f.kind}: {f.path}"
                for f in step_facts[-5:]
                if hasattr(f, "kind")
            )
        content = (
            f"## [{task_type}] Stall ({today}, {task_id})\n"
            f"Task: {task_text[:120]}\n"
            f"Stall hints:\n{hints_str}\n"
            f"Last steps tried:\n{tried_str or '(not recorded)'}\n"
            f"source: stall detection\n"
        )
        return content, "errors"

    # OUTCOME_NONE_UNSUPPORTED or OUTCOME_ERR_INTERNAL — low value, skip
    return "", ""


def run_wiki_lint(model: str = "", cfg: dict | None = None) -> None:
    """Merge fragments into pages. Called once before ThreadPoolExecutor in main.py.

    For each category: reads all fragments, calls LLM merge (or concat fallback),
    writes to pages/, moves fragments to archive/.
    Fail-open: if anything fails, logs and continues.
    """
    if cfg is None:
        cfg = {}
    if not _FRAGMENTS_DIR.exists():
        return

    categories = [d.name for d in _FRAGMENTS_DIR.iterdir() if d.is_dir()]
    if not categories:
        return

    print(f"[wiki-lint] processing {len(categories)} fragment categories: {categories}")

    for category in sorted(categories):
        frag_dir = _FRAGMENTS_DIR / category
        fragments = sorted(frag_dir.glob("*.md"))
        if not fragments:
            continue

        existing = _read_page(category)
        new_entries = [f.read_text(encoding="utf-8") for f in fragments]

        merged = _llm_merge_or_concat(existing, new_entries, category, model, cfg)

        # Write merged page
        _PAGES_DIR.mkdir(parents=True, exist_ok=True)
        page_path = _PAGES_DIR / f"{category}.md"
        page_path.write_text(merged, encoding="utf-8")

        # Archive fragments
        archive_dir = _ARCHIVE_DIR / category
        archive_dir.mkdir(parents=True, exist_ok=True)
        for f in fragments:
            f.rename(archive_dir / f.name)

        print(f"[wiki-lint] {category}: merged {len(fragments)} fragments → {page_path.name}")


def _llm_merge_or_concat(
    existing: str,
    new_entries: list[str],
    category: str,
    model: str,
    cfg: dict,
) -> str:
    """Merge existing page with new fragments via LLM. Fallback: concat."""
    if not model:
        return _concat_merge(existing, new_entries)

    try:
        from .dispatch import call_llm_raw
        combined_new = "\n\n---\n\n".join(new_entries)
        system = "You are merging wiki knowledge entries. Output only the merged Markdown content, no preamble."
        user_msg = (
            f"Merge wiki knowledge entries for category '{category}'.\n\n"
            f"EXISTING PAGE:\n{existing or '(empty)'}\n\n"
            f"NEW FRAGMENTS:\n{combined_new}\n\n"
            f"Task: Produce a clean, deduplicated, non-contradictory Markdown page.\n"
            f"- Remove duplicates. Keep the most recent/specific version.\n"
            f"- Resolve contradictions: prefer newer entries.\n"
            f"- Preserve all unique, non-redundant entries.\n"
            f"- Output only the merged Markdown content, no preamble."
        )
        response = call_llm_raw(
            system=system,
            user_msg=user_msg,
            model=model,
            cfg=cfg,
            max_tokens=4000,
            plain_text=True,
        )
        if response and len(response) > 50:
            return response
    except Exception as e:
        print(f"[wiki-lint] LLM merge failed ({e}), using concat fallback")

    return _concat_merge(existing, new_entries)


def _concat_merge(existing: str, new_entries: list[str]) -> str:
    """Simple fallback: concat existing + new entries."""
    return "\n\n".join(p for p in [existing, *new_entries] if p)
