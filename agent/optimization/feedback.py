"""Deterministic feedback builders for GEPA metrics.

Each builder is a pure function that produces a short (~400 char) string
describing why the prediction succeeded or failed, using only fields available
on the trace example. No LLM calls.
"""
from __future__ import annotations


_TASK_TYPE_HINTS = {
    "email":    "email tasks must end in /outbox/",
    "inbox":    "inbox tasks require classification before write",
    "queue":    "queue tasks process pending items in order",
    "lookup":   "lookup tasks are read-only — no writes",
    "capture":  "capture tasks save to /capture/",
    "crm":      "crm tasks update /contacts/ records",
    "temporal": "temporal tasks require date/time anchoring",
    "preject":  "preject tasks set up project scaffolding",
    "think":    "think tasks return reasoning, no side effects",
    "distill":  "distill tasks produce concise summaries",
    "default":  "follow vault discovery and write-scope rules",
}


def build_builder_feedback(example, prediction, score: float) -> str:
    """Return short feedback for prompt_builder metric."""
    task_type = getattr(example, "task_type", "default")
    addendum = (getattr(prediction, "addendum", "") or "")
    bullet_count = sum(1 for line in addendum.splitlines() if line.strip().startswith("-"))
    source_score = float(getattr(example, "score", 1.0))
    stall = bool(getattr(example, "stall_detected", False))
    scope_bad = bool(getattr(example, "write_scope_violations", False))

    if bullet_count == 0:
        return "Addendum has no bullet structure — bullets ('- ...') are required."

    if source_score >= 0.8:
        if bullet_count >= 3:
            return f"OK: addendum led to score=1.0; keep bullet density ≥3."
        return (f"Score=1.0 but addendum has only {bullet_count} bullets — "
                f"terse may regress on harder cases; aim for 3-5.")

    # source_score < 0.8 — failure case
    if stall:
        return (f"Task failed (stall detected). Addendum did not surface "
                f"anti-loop guidance for task_type={task_type}.")
    if scope_bad:
        return (f"Task failed: agent wrote outside the allowed scope for "
                f"task_type={task_type}. Addendum should encode the write-scope rule "
                f"({_TASK_TYPE_HINTS.get(task_type, _TASK_TYPE_HINTS['default'])}).")
    hint = _TASK_TYPE_HINTS.get(task_type, _TASK_TYPE_HINTS["default"])
    return (f"Task failed. Addendum produced {bullet_count} bullets for "
            f"task_type={task_type}; consider mentioning: {hint}.")


def build_evaluator_feedback(example, prediction, score: float) -> str:
    """Return short feedback for evaluator metric."""
    expected = (getattr(example, "approved_str", "yes") or "").strip().lower()
    predicted = (getattr(prediction, "approved_str", "") or "").strip().lower()
    task_type = getattr(example, "task_type", "default")
    proposed = getattr(example, "proposed_outcome", "")
    done_ops = (getattr(example, "done_ops", "") or "").strip()
    task_text = getattr(example, "task_text", "") or ""

    if predicted == expected:
        return f"Correct: {expected}."

    refusal_set = {"OUTCOME_NONE_CLARIFICATION", "OUTCOME_NONE_UNSUPPORTED", "OUTCOME_DENIED_SECURITY"}
    if predicted == "yes" and expected == "no":
        if proposed == "OUTCOME_OK" and (not done_ops or done_ops == "(none)"):
            return (f"False approve: agent claimed OUTCOME_OK without any write/delete ops. "
                    f"Tighten the 'side-effects required' check for task_type={task_type}.")
        if len(task_text) < 30 or task_text.endswith("..."):
            return ("False approve: task_text was ambiguous/truncated and agent answered "
                    "without clarification. Should have rejected → CLARIFICATION.")
        return f"False approve for task_type={task_type}; outcome did not match the task constraint."

    if predicted == "no" and expected == "yes":
        ops_short = done_ops[:80] if done_ops else "(no ops)"
        if proposed in refusal_set:
            return (f"False reject: refusal {proposed} was actually correct "
                    f"(benchmark score=1.0). Refusal-acceptance rules should be more lenient.")
        return (f"False reject: outcome was actually correct (benchmark score=1.0). "
                f"Avoid over-skepticism on task_type={task_type}; the {ops_short} were sufficient.")

    return f"Mismatch: predicted={predicted}, expected={expected}, task_type={task_type}."


_CONFUSED_PAIRS = {
    ("lookup", "email"): ("Misclassified: task implies sending an email "
                          "(action verb 'send/write/email'); lookup is read-only. "
                          "Hint: presence of recipient name → email."),
    ("default", "inbox"): ("Misclassified: task references /inbox/ items implicitly via "
                           "'process'/'classify'/'sort'; default is too generic."),
    ("think", "temporal"): ("Misclassified: temporal markers ('next week', 'before Friday', "
                            "explicit date in task_text); think is for open-ended reasoning."),
}


def build_classifier_feedback(example, prediction, score: float) -> str:
    """Return short feedback for classifier metric."""
    expected = (getattr(example, "task_type", "default") or "").strip().lower()
    predicted = (getattr(prediction, "task_type", "") or "").strip().lower()
    task_text = (getattr(example, "task_text", "") or "")[:120]

    if predicted == expected:
        return f"Correct: {expected}."

    pair_msg = _CONFUSED_PAIRS.get((predicted, expected))
    if pair_msg:
        return pair_msg

    return (f"Misclassified: predicted={predicted}, expected={expected}. "
            f"Task text: {task_text!r}.")


def build_contract_feedback(example, prediction, score: float) -> str:
    """Return short feedback for contract_metric."""
    task_type = getattr(example, "task_type", "default")
    src_score = float(getattr(example, "score", 0.0))
    rounds = int(getattr(example, "rounds_taken", 3))
    stall = bool(getattr(example, "stall_detected", False))
    scope_bad = bool(getattr(example, "write_scope_violations", False))

    if src_score < 1.0:
        if stall:
            return (f"Contract failed (task stalled). Negotiation for {task_type} "
                    f"did not produce actionable plan steps — reduce ambiguity.")
        if scope_bad:
            hint = _TASK_TYPE_HINTS.get(task_type, _TASK_TYPE_HINTS["default"])
            return (f"Contract failed: write-scope violation for {task_type}. "
                    f"Evaluator should enforce: {hint}.")
        return (f"Contract failed for {task_type} after {rounds} round(s). "
                f"Tighten success criteria or reduce open_questions.")

    if rounds == 1:
        return f"Excellent: consensus on round 1 for {task_type} — keep concise proposals."
    if rounds == 2:
        return f"Good: consensus on round 2 for {task_type}."
    return (f"Slow convergence: {rounds} rounds needed for {task_type}. "
            f"Executor should address evaluator objections more directly.")
