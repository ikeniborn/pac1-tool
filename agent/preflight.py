from __future__ import annotations
import json
import logging
import sys
from pathlib import Path

from agent.maintenance.health import run_health_check
from agent.maintenance.purge import run_purge

log = logging.getLogger(__name__)


def run_preflight() -> None:
    """FIX-427: Run preflight checks. Raises SystemExit(1) on failure."""
    _check_graph()
    _check_wiki_pages()
    _check_graph_loadable()
    log.info("[preflight] all checks passed")


def _check_graph() -> None:
    result = run_health_check()
    for line in result.report:
        log.info("[preflight] %s", line)

    if result.exit_code < 2:
        return  # OK or WARN — continue

    log.warning("[preflight] graph FAIL — auto-purging contamination")
    run_purge(apply=True)

    result2 = run_health_check()
    for line in result2.report:
        log.info("[preflight] re-check: %s", line)

    if result2.exit_code == 2:
        msg = "; ".join(result2.report)
        log.error("[preflight] graph still FAIL after purge: %s", msg)
        sys.exit(1)


def _check_wiki_pages(pages_dir: Path = Path("data/wiki/pages")) -> None:
    if not pages_dir.exists():
        return
    for page in pages_dir.rglob("*.md"):
        if page.stat().st_size == 0:
            log.error("[preflight] wiki page is empty: %s", page)
            sys.exit(1)


def _check_graph_loadable(graph_path: Path = Path("data/wiki/graph.json")) -> None:
    if not graph_path.exists():
        return
    try:
        data = json.loads(graph_path.read_text(encoding="utf-8"))
        if not isinstance(data.get("nodes"), dict) or not isinstance(data.get("edges"), list):
            raise ValueError("missing 'nodes' dict or 'edges' list")
    except Exception as exc:
        log.error("[preflight] graph.json invalid: %s", exc)
        sys.exit(1)
