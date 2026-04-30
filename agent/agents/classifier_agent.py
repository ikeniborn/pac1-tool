"""ClassifierAgent: task type classification and model selection.

Classifies incoming tasks as one of the registered types (email, inbox, etc.)
and selects the appropriate model for execution.
"""
from __future__ import annotations

from agent.classifier import ModelRouter, classify_task
from agent.contracts import ClassificationResult, TaskInput
from agent.prephase import PrephaseResult


class ClassifierAgent:
    """Classifies task type and selects model.

    Integrates with ModelRouter to leverage both regex fast-path classification
    and LLM-based classification when vault context (prephase) is available.
    """

    def __init__(self, router: ModelRouter) -> None:
        """Initialize with a ModelRouter instance.

        Args:
            router: ModelRouter configured with default model and per-type overrides.
        """
        self._router = router

    def run(
        self,
        task: TaskInput,
        prephase: PrephaseResult | None = None,
    ) -> ClassificationResult:
        """Classify task type and select model.

        When prephase is provided, vault context (AGENTS.MD, folder structure,
        wiki hints) improves classification accuracy via LLM. Without prephase,
        the regex fast-path is used with no vault context.

        Args:
            task: TaskInput with task_text and harness metadata.
            prephase: Optional PrephaseResult providing vault context (AGENTS.MD,
                      file tree, etc.). If None, falls back to regex-only classification.

        Returns:
            ClassificationResult with task_type, selected model, and model config.
        """
        if prephase is not None:
            # Classify with vault hints for higher accuracy
            model, cfg, task_type = self._router.resolve_after_prephase(
                task.task_text, prephase
            )
            confidence = 0.95
        else:
            # Regex fast-path without vault hints
            task_type = classify_task(task.task_text)
            model = self._router.default
            cfg = self._router.configs.get(model, {})
            confidence = 0.8

        return ClassificationResult(
            task_type=task_type,
            model=model,
            model_cfg=cfg,
            confidence=confidence,
        )
