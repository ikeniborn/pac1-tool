"""Unit tests for deterministic feedback builders."""
from agent.optimization.feedback import (
    build_builder_feedback,
    build_evaluator_feedback,
    build_classifier_feedback,
)


def _ex(**kw):
    """Tiny SimpleNamespace-like shim — feedback builders read attributes."""
    class _E: pass
    e = _E()
    for k, v in kw.items():
        setattr(e, k, v)
    return e


# -------- builder --------

def test_builder_score_one_with_three_bullets():
    ex = _ex(task_type="email", score=1.0, stall_detected=False, write_scope_violations=False)
    pred = _ex(addendum="- a\n- b\n- c")
    fb = build_builder_feedback(ex, pred, score=1.0)
    assert "score=1.0" in fb
    assert "≥3" in fb or "3-5" in fb


def test_builder_score_one_with_one_bullet():
    ex = _ex(task_type="email", score=1.0, stall_detected=False, write_scope_violations=False)
    pred = _ex(addendum="- a")
    fb = build_builder_feedback(ex, pred, score=1.0)
    assert "1 bullets" in fb or "only 1" in fb
    assert "3-5" in fb


def test_builder_failed_with_stall():
    ex = _ex(task_type="email", score=0.0, stall_detected=True, write_scope_violations=False)
    pred = _ex(addendum="- a\n- b")
    fb = build_builder_feedback(ex, pred, score=0.0)
    assert "stall" in fb.lower()
    assert "anti-loop" in fb.lower()


def test_builder_failed_with_write_scope():
    ex = _ex(task_type="email", score=0.0, stall_detected=False, write_scope_violations=True)
    pred = _ex(addendum="- a\n- b")
    fb = build_builder_feedback(ex, pred, score=0.0)
    assert "write" in fb.lower()
    assert "outbox" in fb.lower()


def test_builder_failed_generic():
    ex = _ex(task_type="lookup", score=0.0, stall_detected=False, write_scope_violations=False)
    pred = _ex(addendum="- a\n- b")
    fb = build_builder_feedback(ex, pred, score=0.0)
    assert "task_type=lookup" in fb


def test_builder_no_bullets():
    ex = _ex(task_type="email", score=1.0, stall_detected=False, write_scope_violations=False)
    pred = _ex(addendum="some plain text")
    fb = build_builder_feedback(ex, pred, score=0.5)
    assert "bullet" in fb.lower()


# -------- evaluator --------

def test_evaluator_correct():
    ex = _ex(approved_str="yes", task_type="email", proposed_outcome="OUTCOME_OK",
             done_ops="- WRITTEN: /outbox/x.json", task_text="Send mail to John")
    pred = _ex(approved_str="yes")
    assert build_evaluator_feedback(ex, pred, 1.0) == "Correct: yes."


def test_evaluator_false_approve_no_ops():
    ex = _ex(approved_str="no", task_type="default", proposed_outcome="OUTCOME_OK",
             done_ops="(none)", task_text="Delete archive items")
    pred = _ex(approved_str="yes")
    fb = build_evaluator_feedback(ex, pred, 0.0)
    assert "False approve" in fb
    assert "side-effects" in fb


def test_evaluator_false_approve_truncated():
    ex = _ex(approved_str="no", task_type="inbox", proposed_outcome="OUTCOME_OK",
             done_ops="- read inbox/1.json", task_text="Pr...")
    pred = _ex(approved_str="yes")
    fb = build_evaluator_feedback(ex, pred, 0.0)
    assert "ambiguous" in fb or "truncated" in fb.lower()


def test_evaluator_false_reject():
    ex = _ex(approved_str="yes", task_type="lookup", proposed_outcome="OUTCOME_OK",
             done_ops="- read contacts/cont_007.json", task_text="What is Maria's email?")
    pred = _ex(approved_str="no")
    fb = build_evaluator_feedback(ex, pred, 0.0)
    assert "False reject" in fb
    assert "lookup" in fb


# -------- classifier --------

def test_classifier_correct():
    ex = _ex(task_type="email", task_text="Send X to Y")
    pred = _ex(task_type="email")
    assert build_classifier_feedback(ex, pred, 1.0) == "Correct: email."


def test_classifier_confused_pair_email_vs_lookup():
    ex = _ex(task_type="email", task_text="Send mail to John")
    pred = _ex(task_type="lookup")
    fb = build_classifier_feedback(ex, pred, 0.0)
    assert "lookup is read-only" in fb


def test_classifier_generic_mismatch():
    ex = _ex(task_type="capture", task_text="capture this idea")
    pred = _ex(task_type="email")
    fb = build_classifier_feedback(ex, pred, 0.0)
    assert "predicted=email" in fb
    assert "expected=capture" in fb
