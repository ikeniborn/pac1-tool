"""Minimal orchestrator for ecom benchmark."""
from __future__ import annotations

import os

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync

from agent.prephase import run_prephase
from agent.pipeline import run_pipeline
from agent.prompt import build_system_prompt

_MODEL = os.environ.get("MODEL", "")


def run_agent(model_configs: dict, harness_url: str, task_text: str, task_id: str = "") -> dict:
    """Execute a single benchmark task."""
    vm = EcomRuntimeClientSync(harness_url)

    model = _MODEL
    cfg = model_configs.get(model, {}) if model_configs else {}

    task_type = "lookup"
    system_prompt = build_system_prompt(task_type)
    pre = run_prephase(vm, task_text, system_prompt)

    stats = run_pipeline(vm, model, task_text, pre, cfg)
    stats["model_used"] = model
    stats["task_type"] = task_type
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
