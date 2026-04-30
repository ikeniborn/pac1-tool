from __future__ import annotations

import os

from agent.contracts import ExecutionPlan, PlannerInput
from agent.prompt import build_system_prompt

_PROMPT_BUILDER_MAX_TOKENS = int(os.getenv("PROMPT_BUILDER_MAX_TOKENS", "500"))
_CONTRACT_MAX_ROUNDS = int(os.getenv("CONTRACT_MAX_ROUNDS", "3"))


class PlannerAgent:
    def __init__(
        self,
        model: str,
        cfg: dict,
        prompt_builder_enabled: bool | None = None,
        contract_enabled: bool | None = None,
    ) -> None:
        self._model = model
        self._cfg = cfg
        self._builder = (os.getenv("PROMPT_BUILDER_ENABLED", "1") == "1"
                         if prompt_builder_enabled is None else prompt_builder_enabled)
        self._contract = (os.getenv("CONTRACT_ENABLED", "0") == "1"
                          if contract_enabled is None else contract_enabled)

    def run(self, inp: PlannerInput) -> ExecutionPlan:
        task_type = inp.classification.task_type
        task_text = inp.task_input.task_text

        # 1. Base system prompt
        base_prompt = build_system_prompt(task_type)

        # 2. Inject knowledge graph section
        if inp.wiki_context.graph_section:
            base_prompt = base_prompt + "\n\n" + inp.wiki_context.graph_section

        # 3. Dynamic addendum (DSPy prompt builder)
        addendum = ""
        builder_in = builder_out = 0
        if self._builder:
            try:
                from agent.prompt_builder import build_dynamic_addendum
                addendum, builder_in, builder_out = build_dynamic_addendum(
                    task_text=task_text,
                    task_type=task_type,
                    model=self._model,
                    cfg=self._cfg,
                    max_tokens=_PROMPT_BUILDER_MAX_TOKENS,
                    graph_context=inp.wiki_context.graph_section,
                )
            except Exception as exc:
                print(f"[planner] prompt_builder failed ({exc})")

        # Inject addendum into prompt
        if addendum:
            base_prompt = base_prompt + "\n\n## TASK-SPECIFIC GUIDANCE\n" + addendum

        # Update prephase log to use final prompt
        if inp.prephase.log:
            inp.prephase.log[0]["content"] = base_prompt
        if inp.prephase.preserve_prefix:
            inp.prephase.preserve_prefix[0]["content"] = base_prompt

        # 4. Contract negotiation (optional)
        contract = None
        contract_in = contract_out = 0
        if self._contract:
            try:
                from agent.contract_phase import negotiate_contract
                contract, contract_in, contract_out, _rounds = negotiate_contract(
                    task_text=task_text,
                    task_type=task_type,
                    agents_md=inp.prephase.agents_md_content or "",
                    wiki_context=inp.wiki_context.patterns_text,
                    graph_context=inp.wiki_context.graph_section,
                    vault_date_hint=inp.prephase.vault_date_est or "",
                    vault_tree=inp.prephase.vault_tree_text or "",
                    model=self._model,
                    cfg=self._cfg,
                    max_rounds=_CONTRACT_MAX_ROUNDS,
                )
            except Exception as exc:
                print(f"[planner] contract negotiation failed ({exc})")

        return ExecutionPlan(
            base_prompt=base_prompt,
            addendum=addendum,
            contract=contract,
            route="EXECUTE",
            in_tokens=builder_in + contract_in,
            out_tokens=builder_out + contract_out,
        )
