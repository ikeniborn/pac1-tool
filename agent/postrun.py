from __future__ import annotations
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from agent.maintenance.purge import run_purge
from agent.maintenance.distill import run_distill
from agent.maintenance.candidates import log_candidates
from agent.wiki import run_wiki_lint

log = logging.getLogger(__name__)

_CONTRACT_EXAMPLES = Path("data/dspy_contract_examples.jsonl")
_DSPY_EXAMPLES = Path("data/dspy_examples.jsonl")


def run_postrun() -> None:
    """FIX-427: Run postrun maintenance. Raises SystemExit(1) on non-candidate failures."""
    _do_purge()
    _do_wiki_lint()
    _do_distill_contracts()
    _do_log_candidates()
    _do_optimize_if_enabled()
    log.info("[postrun] all steps complete")


def _do_purge() -> None:
    try:
        result = run_purge(apply=True)
        log.info(
            "[postrun] purge: removed=%d nodes, deduped=%d, page_blocks=%d, fragments=%d",
            len(result.removed_node_ids), result.deduped_count,
            result.purged_page_blocks, result.cleared_fragments,
        )
    except Exception as exc:
        log.error("[postrun] purge failed: %s", exc)
        sys.exit(1)


def _do_wiki_lint() -> None:
    model = os.getenv("MODEL_WIKI") or os.getenv("MODEL_DEFAULT") or ""
    cfg: dict = {}
    models_path = Path("models.json")
    if models_path.exists():
        try:
            cfg = json.loads(models_path.read_text(encoding="utf-8")).get(model, {})
        except Exception:
            pass
    try:
        run_wiki_lint(model=model, cfg=cfg)
    except Exception as exc:
        log.error("[postrun] wiki lint failed: %s", exc)
        sys.exit(1)


def _do_distill_contracts() -> None:
    min_ex = int(os.getenv("POSTRUN_DISTILL_MIN_EXAMPLES", "10"))
    count = _count_contract_examples()
    if count < min_ex:
        log.info("[postrun] %d contract examples < min=%d, skipping distill", count, min_ex)
        return
    try:
        result = run_distill(min_examples=min_ex, apply=True)
        log.info("[postrun] distill: processed=%s skipped=%s", result.types_processed, result.types_skipped)
    except Exception as exc:
        log.error("[postrun] distill failed: %s", exc)
        sys.exit(1)


def _do_log_candidates() -> None:
    min_count = int(os.getenv("POSTRUN_PROMOTE_MIN_COUNT", "5"))
    try:
        log_candidates(min_count=min_count)
    except Exception as exc:
        log.warning("[postrun] candidates log failed (non-critical): %s", exc)


def _count_dspy_examples() -> int:
    if not _DSPY_EXAMPLES.exists():
        return 0
    return sum(1 for ln in _DSPY_EXAMPLES.read_text(encoding="utf-8").splitlines() if ln.strip())


def _do_optimize_if_enabled() -> None:
    # FIX-429: non-fatal optimizer with sys.executable and full stdout+stderr capture
    # FIX-438: min_examples threshold to skip optimize when too few examples collected
    if os.getenv("POSTRUN_OPTIMIZE", "0") != "1":
        return
    min_ex = int(os.getenv("POSTRUN_OPTIMIZE_MIN_EXAMPLES", "10"))
    count = _count_dspy_examples()
    if count < min_ex:
        log.info("[postrun] optimize skipped: %d dspy examples < min=%d", count, min_ex)
        return
    try:
        proc = subprocess.run(
            [sys.executable, "scripts/optimize_prompts.py", "--target", "all"],
            check=True,
            capture_output=True,
            text=True,
        )
        tail = proc.stdout[-500:] if proc.stdout else ""
        log.info("[postrun] optimize done: %s", tail)
    except subprocess.CalledProcessError as exc:
        out = (exc.stdout or "")[-500:]
        err = (exc.stderr or "")[-300:]
        log.warning("[postrun] optimize skipped (exit %d): stdout=%s stderr=%s", exc.returncode, out, err)


def _count_contract_examples() -> int:
    if not _CONTRACT_EXAMPLES.exists():
        return 0
    return sum(1 for ln in _CONTRACT_EXAMPLES.read_text(encoding="utf-8").splitlines() if ln.strip())
