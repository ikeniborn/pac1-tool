"""ExecutorAgent: task execution wrapper over run_loop with DI support.

Receives ExecutorInput (prephase result, execution plan, model routing),
creates the PCM vm connection, and delegates to run_loop with injected
agent instances for security/stall/compaction/step_guard/verifier.
"""
from __future__ import annotations

from agent.agents.compaction_agent import CompactionAgent
from agent.agents.security_agent import SecurityAgent
from agent.agents.stall_agent import StallAgent
from agent.agents.step_guard_agent import StepGuardAgent
from agent.agents.verifier_agent import VerifierAgent
from agent.contracts import ExecutionResult, ExecutorInput


def _status_from_outcome(outcome: str) -> str:
    if outcome == "OUTCOME_OK":
        return "completed"
    if outcome == "OUTCOME_DENIED_SECURITY":
        return "denied"
    if outcome == "OUTCOME_ERR_INTERNAL":
        return "error"
    return "error"


class ExecutorAgent:
    """Wraps run_loop, injecting agent instances for DI.

    Agents are stateless helpers — the same instances can be reused
    across multiple ExecutorAgent.run() calls.
    """

    def __init__(
        self,
        security: SecurityAgent,
        stall: StallAgent,
        compaction: CompactionAgent,
        step_guard: StepGuardAgent,
        verifier: VerifierAgent,
    ) -> None:
        self._security = security
        self._stall = stall
        self._compaction = compaction
        self._step_guard = step_guard
        self._verifier = verifier

    def run(self, inp: ExecutorInput) -> ExecutionResult:
        """Execute task via run_loop with injected agents.

        Creates a PCM VM connection from inp.harness_url, delegates
        all loop logic to run_loop with DI agent params.
        """
        from agent.loop import run_loop
        from bitgn.vm.pcm_connect import PcmRuntimeClientSync

        vm = PcmRuntimeClientSync(inp.harness_url)
        stats = run_loop(
            vm,
            inp.model,
            inp.task_input.task_text,
            inp.prephase,
            inp.model_cfg,
            task_type=inp.task_type,
            evaluator_model=inp.evaluator_model,
            evaluator_cfg=inp.evaluator_cfg,
            contract=inp.plan.contract,
            _security_agent=self._security,
            _stall_agent=self._stall,
            _compaction_agent=self._compaction,
            _step_guard_agent=self._step_guard,
            _verifier_agent=self._verifier,
        )
        return ExecutionResult(
            status=_status_from_outcome(stats.get("outcome", "")),
            outcome=stats.get("outcome", ""),
            token_stats={k: v for k, v in stats.items() if "tok" in k},
            step_facts=stats.get("step_facts", []),
            injected_node_ids=stats.get("graph_injected_node_ids", []),
            rejection_count=stats.get("eval_rejection_count", 0),
        )
