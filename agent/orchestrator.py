"""Minimal orchestrator for ecom benchmark."""
from __future__ import annotations

import json
import os
from pathlib import Path

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync

from agent.prephase import run_prephase
from agent.loop import run_loop
from agent.prompt import build_system_prompt

_MODEL = os.environ.get("MODEL", "")
_DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
_DRY_RUN_LOG = Path(__file__).parent.parent / "data" / "dry_run_analysis.jsonl"


def _write_dry_run(task_id: str, task_text: str, pre) -> None:
    entry = {
        "task_id": task_id,
        "task": task_text,
        "agents_md": pre.agents_md_content,
        "bin_sql_content": pre.bin_sql_content,
    }
    _DRY_RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(_DRY_RUN_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run_agent(model_configs: dict, harness_url: str, task_text: str, task_id: str = "") -> dict:
    """Execute a single benchmark task."""
    vm = EcomRuntimeClientSync(harness_url)

    model = _MODEL
    cfg = model_configs.get(model, {}) if model_configs else {}

    system_prompt = build_system_prompt("lookup")
    pre = run_prephase(vm, task_text, system_prompt, dry_run=_DRY_RUN)

    if _DRY_RUN:
        _write_dry_run(task_id, task_text, pre)
        return {
            "model_used": model,
            "task_type": "lookup",
            "builder_used": False,
            "builder_in_tok": 0,
            "builder_out_tok": 0,
            "builder_addendum": "",
            "contract_rounds_taken": 0,
            "contract_is_default": True,
            "eval_rejection_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "outcome": "DRY_RUN",
        }

    stats = run_loop(vm, model, task_text, pre, cfg)

    stats["model_used"] = model
    stats["task_type"] = "lookup"
    stats["builder_used"] = False
    stats["builder_in_tok"] = 0
    stats["builder_out_tok"] = 0
    stats["builder_addendum"] = ""
    stats["contract_rounds_taken"] = 0
    stats["contract_is_default"] = True
    stats["eval_rejection_count"] = 0
    return stats


def write_wiki_fragment(*args, **kwargs) -> None:
    """No-op: wiki subsystem removed."""
