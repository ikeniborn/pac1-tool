"""Contracts module for multi-agent architecture.

This module defines the typed Pydantic contracts that serve as communication
boundaries between independent agents. It is the ONLY shared import boundary
between agents.

All agents import contracts from this single location to ensure type safety
and enable easy refactoring of inter-agent communication.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# Re-export existing types so consumers only import from agent.contracts
from agent.contract_models import Contract
from agent.models import ReportTaskCompletion
from agent.prephase import PrephaseResult


class TaskInput(BaseModel):
    """Input provided by harness to ExecutorAgent."""
    task_text: str
    harness_url: str
    trial_id: str


class ClassificationResult(BaseModel):
    """Result from ClassifierAgent."""
    task_type: str
    model: str
    model_cfg: dict
    confidence: float


class WikiReadRequest(BaseModel):
    """Request to WikiGraphAgent to load wiki context."""
    task_type: str
    task_text: str


class WikiContext(BaseModel):
    """Wiki context returned by WikiGraphAgent to be injected in prompts."""
    patterns_text: str
    graph_section: str
    injected_node_ids: list[str]


class PlannerInput(BaseModel):
    """Input to PlannerAgent to negotiate a contract."""
    task_input: TaskInput
    classification: ClassificationResult
    wiki_context: WikiContext
    prephase: PrephaseResult

    model_config = {"arbitrary_types_allowed": True}


class ExecutionPlan(BaseModel):
    """Plan output by PlannerAgent after contract negotiation."""
    base_prompt: str
    addendum: str
    contract: Contract | None
    route: Literal["EXECUTE", "DENY_SECURITY", "CLARIFY", "UNSUPPORTED"]
    in_tokens: int
    out_tokens: int

    model_config = {"arbitrary_types_allowed": True}


class SecurityRequest(BaseModel):
    """Request to SecurityAgent to validate a tool invocation."""
    tool_name: str
    tool_args: dict
    task_type: str
    message_text: str | None = None


class SecurityCheck(BaseModel):
    """Security validation result from SecurityAgent."""
    passed: bool
    violation_type: str | None = None
    detail: str | None = None


class StepGuardRequest(BaseModel):
    """Request to StepGuardAgent to validate a tool invocation against contract."""
    step_index: int
    tool_name: str
    tool_args: dict
    contract: Contract

    model_config = {"arbitrary_types_allowed": True}


class StepValidation(BaseModel):
    """Validation result from StepGuardAgent."""
    valid: bool
    deviation: str | None = None
    suggestion: str | None = None


class StallRequest(BaseModel):
    """Request to StallAgent to detect and handle stalls in execution."""
    step_index: int
    fingerprints: list[str]
    error_counts: dict[str, int]
    steps_without_write: int
    step_facts_dicts: list[dict] = []
    contract_plan_steps: list[str] | None = None


class StallResult(BaseModel):
    """Stall detection result from StallAgent."""
    detected: bool
    hint: str | None = None
    escalation_level: int = 0


class CompactionRequest(BaseModel):
    """Request to CompactionAgent to compact the message log."""
    messages: list[dict]
    preserve_prefix: list[dict]
    step_facts_dicts: list[dict]
    token_limit: int


class CompactedLog(BaseModel):
    """Compacted log returned by CompactionAgent."""
    messages: list[dict]
    tokens_saved: int


class CompletionRequest(BaseModel):
    """Request to VerifierAgent to verify task completion.

    Passed from ExecutorAgent to VerifierAgent at each ReportTaskCompletion.
    """
    report: ReportTaskCompletion
    task_type: str
    task_text: str
    wiki_context: WikiContext
    contract: Contract | None
    # Fields needed by evaluate_completion() — populated from loop state
    done_ops: list[str] = []
    digest_str: str = ""
    evaluator_model: str = ""
    evaluator_cfg: dict = {}
    rejection_count: int = 0

    model_config = {"arbitrary_types_allowed": True}


class VerificationResult(BaseModel):
    """Verification result from VerifierAgent."""
    approved: bool
    feedback: str | None = None
    rejection_count: int = 0
    hard_gate_triggered: str | None = None


class ExecutorInput(BaseModel):
    """Full input to ExecutorAgent for task execution."""
    task_input: TaskInput
    plan: ExecutionPlan
    wiki_context: WikiContext
    prephase: PrephaseResult
    harness_url: str          # ExecutorAgent creates vm from this
    task_type: str
    evaluator_model: str
    evaluator_cfg: dict

    model_config = {"arbitrary_types_allowed": True}


class ExecutionResult(BaseModel):
    """Result of task execution from ExecutorAgent."""
    status: Literal["completed", "denied", "timeout", "error"]
    outcome: str
    token_stats: dict[str, int]
    step_facts: list[dict]
    injected_node_ids: list[str]
    rejection_count: int


class WikiFeedbackRequest(BaseModel):
    """Request to WikiGraphAgent to update graph with execution feedback."""
    task_type: str
    task_text: str
    execution_result: ExecutionResult
    wiki_context: WikiContext
    score: float


__all__ = [
    "TaskInput",
    "ClassificationResult",
    "WikiReadRequest",
    "WikiContext",
    "PlannerInput",
    "ExecutionPlan",
    "SecurityRequest",
    "SecurityCheck",
    "StepGuardRequest",
    "StepValidation",
    "StallRequest",
    "StallResult",
    "CompactionRequest",
    "CompactedLog",
    "CompletionRequest",
    "VerificationResult",
    "ExecutorInput",
    "ExecutionResult",
    "WikiFeedbackRequest",
    # Re-exported types
    "Contract",
    "ReportTaskCompletion",
    "PrephaseResult",
]
