"""Metrics for the three DSPy targets.

All metrics return `dspy.Prediction(score, feedback)`. COPRO consumes only the
scalar via a wrapper in CoproBackend; GEPA uses both fields.
"""
from __future__ import annotations

import dspy

from agent.optimization.feedback import (
    build_builder_feedback,
    build_evaluator_feedback,
    build_classifier_feedback,
)


def builder_metric(example: dspy.Example, prediction, trace=None) -> dspy.Prediction:
    """Score addendum: 1.0 if source score >= 0.8 and bullet_count >= 2; 0.5 sparse; 0.0 if source bad."""
    source_score: float = getattr(example, "score", 1.0)
    if source_score < 0.8:
        score = 0.0
    else:
        addendum: str = getattr(prediction, "addendum", "") or ""
        bullet_count = sum(1 for line in addendum.splitlines() if line.strip().startswith("-"))
        score = 0.5 if bullet_count < 2 else 1.0
    return dspy.Prediction(
        score=score,
        feedback=build_builder_feedback(example, prediction, score),
    )


def evaluator_metric(example: dspy.Example, prediction, trace=None) -> dspy.Prediction:
    """Exact-match between predicted approved_str and expected."""
    expected: str = getattr(example, "approved_str", "yes")
    predicted: str = (getattr(prediction, "approved_str", "") or "").strip().lower()
    score = 1.0 if predicted == expected.lower() else 0.0
    return dspy.Prediction(
        score=score,
        feedback=build_evaluator_feedback(example, prediction, score),
    )


def classifier_metric(example: dspy.Example, prediction, trace=None) -> dspy.Prediction:
    """Exact-match between predicted task_type and expected."""
    expected: str = getattr(example, "task_type", "default")
    predicted: str = (getattr(prediction, "task_type", "") or "").strip().lower()
    score = 1.0 if predicted == expected else 0.0
    return dspy.Prediction(
        score=score,
        feedback=build_classifier_feedback(example, prediction, score),
    )
