"""Minimal orchestrator for ecom benchmark."""
from __future__ import annotations

import os

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync

from agent.prephase import run_prephase
from agent.loop import run_loop

_MODEL_DEFAULT = os.environ.get("MODEL_DEFAULT", "")


def run_agent(model_configs: dict, harness_url: str, task_text: str) -> dict:
    """Execute a single benchmark task."""
    vm = EcomRuntimeClientSync(harness_url)

    model = _MODEL_DEFAULT
    cfg = model_configs.get(model, {}) if model_configs else {}

    pre = run_prephase(vm, task_text)
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
