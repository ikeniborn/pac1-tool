"""One-shot wiki sanitation (Block B of quality-degradation-fixes plan).

What it does:
  1. For every pages/<type>.md: remove 'OUTCOME_NONE_CLARIFICATION'-tagged
     temporal-anchor blocks that taught the agent to refuse on 'N days ago'.
  2. Archive graph nodes with confidence < ARCHIVE_THRESHOLD (default 0.4).
  3. Print a summary diff.

Usage:
    uv run python scripts/sanitize_wiki.py --dry-run   # preview
    uv run python scripts/sanitize_wiki.py --apply     # execute
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "data" / "wiki" / "pages"

# Ensure repo root is on sys.path so `agent` package is importable.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Patterns that indicate poisoning: an Input/Outcome example block where the
# input is a temporal-anchor query and the outcome is NONE_CLARIFICATION.
_POISON_BLOCK = re.compile(
    r"-\s*Input:[^\n]*captured.*?\d+\s+days?\s+ago[^\n]*\n"
    r"(?:-\s*Parsed temporal anchor:[^\n]*\n)?"
    r"(?:-\s*Resolution attempt:[^\n]*\n)?"
    r"-\s*Outcome:[^\n]*OUTCOME_NONE_CLARIFICATION[^\n]*\n",
    re.IGNORECASE,
)

# Workflow-step block (lines 17-19 in lookup.md) that codifies refusal as norm.
_WORKFLOW_REFUSAL = re.compile(
    r"\d+\.\s*If no matching article found for specified timeframe:\s*\n"
    r"\s*-\s*Return\s*`?OUTCOME_NONE_CLARIFICATION`?[^\n]*\n"
    r"\s*-\s*Await user clarification[^\n]*\n",
    re.IGNORECASE,
)

# Verified-refusal section (temporal lookup) that records NONE_CLARIFICATION as correct.
# Matches exactly the block structure present in lookup.md.
_VERIFIED_REFUSAL_BLOCK = re.compile(
    r"## Verified refusal:[^\n]*\n"
    r"<!--\s*refusal:[^\n]*OUTCOME_NONE_CLARIFICATION[^\n]*-->\s*\n"
    r"\n"
    r"\*\*Goal shape:\*\*[^\n]*captured[^\n]*days? ago[^\n]*\n"
    r"\n"
    r"\*\*Outcome:\*\*[^\n]*OUTCOME_NONE_CLARIFICATION[^\n]*\n"
    r"(?:[^\n]*\n)*?"
    r"\*\*Applies when:\*\*[^\n]*\n",
    re.IGNORECASE,
)

# Step-procedure block teaching NONE_CLARIFICATION as the action when results are empty
# (temporal article lookup workflow). Targets: ## Lookup Task ... through Failure Handling line.
_LOOKUP_TASK_BLOCK = re.compile(
    r"## Lookup Task: Finding Captured Articles by Date\n"
    r"(?:[^\n]*\n)*?"
    r"\*\*Failure Handling:\*\*[^\n]*OUTCOME_NONE_CLARIFICATION[^\n]*\n",
    re.IGNORECASE,
)


def sanitize_page(path: Path) -> tuple[str, int]:
    text = path.read_text(encoding="utf-8")
    original_len = len(text)
    text2, _ = _POISON_BLOCK.subn("", text)
    text3, _ = _WORKFLOW_REFUSAL.subn("", text2)
    text4, _ = _VERIFIED_REFUSAL_BLOCK.subn("", text3)
    text5, _ = _LOOKUP_TASK_BLOCK.subn("", text4)
    return text5, (original_len - len(text5))


def archive_low_confidence(threshold: float, apply: bool) -> tuple[int, int]:
    from agent import wiki_graph as wg
    g = wg.load_graph()
    low = [nid for nid, n in g.nodes.items()
           if float(n.get("confidence", 1.0)) < threshold]
    if apply and low:
        wg._archive_nodes(low, g.nodes)
        wg.save_graph(g)
    return len(low), len(g.nodes)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--archive-threshold", type=float, default=0.4)
    args = ap.parse_args()
    if not (args.apply or args.dry_run):
        print("ERROR: pass --dry-run or --apply", file=sys.stderr)
        return 2

    total_bytes_dropped = 0
    for page_path in sorted(PAGES.glob("*.md")):
        cleaned, bytes_dropped = sanitize_page(page_path)
        if bytes_dropped > 0:
            print(f"[sanitize] {page_path.name}: -{bytes_dropped} bytes")
            total_bytes_dropped += bytes_dropped
            if args.apply:
                page_path.write_text(cleaned, encoding="utf-8")

    archived_count, total_nodes = archive_low_confidence(args.archive_threshold, apply=args.apply)
    print(f"[sanitize] graph: would archive {archived_count}/{total_nodes} nodes "
          f"with confidence<{args.archive_threshold}")
    print(f"[sanitize] total bytes dropped from pages: {total_bytes_dropped}")
    print(f"[sanitize] mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
