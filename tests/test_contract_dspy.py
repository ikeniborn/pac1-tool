"""Tests for contract DSPy example collection and trainset loading."""
import json


def _make_example(
    task_type="email",
    rounds=None,
    score=1.0,
    is_default=False,
    rounds_taken=2,
    stall_detected=False,
    write_scope_violations=False,
):
    if rounds is None:
        rounds = [
            {
                "round_num": 1,
                "executor_proposal": {
                    "plan_steps": ["list /", "write /out/1.json"],
                    "expected_outcome": "written",
                    "required_tools": ["write"],
                    "open_questions": [],
                    "agreed": True,
                },
                "evaluator_response": {
                    "success_criteria": ["file written"],
                    "failure_conditions": ["no file"],
                    "required_evidence": ["/out/1.json"],
                    "objections": [],
                    "agreed": True,
                },
            }
        ]
    return dict(
        task_text="Send email to alice",
        task_type=task_type,
        rounds=rounds,
        final_contract={
            "plan_steps": ["write /out/1.json"],
            "success_criteria": ["file written"],
            "required_evidence": ["/out/1.json"],
            "failure_conditions": ["no file"],
            "is_default": False,
            "rounds_taken": rounds_taken,
        },
        is_default=is_default,
        rounds_taken=rounds_taken,
        score=score,
        stall_detected=stall_detected,
        write_scope_violations=write_scope_violations,
    )


def test_record_contract_example_writes_jsonl(tmp_path, monkeypatch):
    """record_contract_example appends one JSON line to dspy_contract_examples.jsonl."""
    import agent.dspy_examples as de
    monkeypatch.setattr(de, "_CONTRACT_EXAMPLES_PATH", tmp_path / "contract.jsonl")
    monkeypatch.setattr(de, "_DATA", tmp_path)

    de.record_contract_example(**_make_example())

    lines = (tmp_path / "contract.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["task_type"] == "email"
    assert rec["rounds_taken"] == 2
    assert rec["score"] == 1.0
    assert len(rec["rounds"]) == 1


def test_record_contract_example_skips_default(tmp_path, monkeypatch):
    """is_default=True → nothing written."""
    import agent.dspy_examples as de
    monkeypatch.setattr(de, "_CONTRACT_EXAMPLES_PATH", tmp_path / "contract.jsonl")
    monkeypatch.setattr(de, "_DATA", tmp_path)

    de.record_contract_example(**_make_example(is_default=True))

    assert not (tmp_path / "contract.jsonl").exists()


def test_get_contract_trainset_executor_role(tmp_path, monkeypatch):
    """role='executor' returns one dspy.Example per round with executor inputs."""
    import agent.dspy_examples as de
    monkeypatch.setattr(de, "_CONTRACT_EXAMPLES_PATH", tmp_path / "contract.jsonl")
    monkeypatch.setattr(de, "_DATA", tmp_path)

    de.record_contract_example(**_make_example())

    trainset = de.get_contract_trainset(min_score=1.0, role="executor")
    assert len(trainset) == 1
    item = trainset[0]
    assert hasattr(item, "task_text")
    assert hasattr(item, "evaluator_feedback")
    assert hasattr(item, "plan_steps")
    assert item.score == 1.0


def test_get_contract_trainset_evaluator_role(tmp_path, monkeypatch):
    """role='evaluator' returns one dspy.Example per round with evaluator inputs."""
    import agent.dspy_examples as de
    monkeypatch.setattr(de, "_CONTRACT_EXAMPLES_PATH", tmp_path / "contract.jsonl")
    monkeypatch.setattr(de, "_DATA", tmp_path)

    de.record_contract_example(**_make_example())

    trainset = de.get_contract_trainset(min_score=1.0, role="evaluator")
    assert len(trainset) == 1
    item = trainset[0]
    assert hasattr(item, "executor_proposal")
    assert hasattr(item, "success_criteria")


def test_get_contract_trainset_filters_low_score(tmp_path, monkeypatch):
    """Examples with score < min_score are excluded."""
    import agent.dspy_examples as de
    monkeypatch.setattr(de, "_CONTRACT_EXAMPLES_PATH", tmp_path / "contract.jsonl")
    monkeypatch.setattr(de, "_DATA", tmp_path)

    de.record_contract_example(**_make_example(score=0.5))
    de.record_contract_example(**_make_example(score=1.0))

    trainset = de.get_contract_trainset(min_score=1.0, role="executor")
    assert len(trainset) == 1
    assert trainset[0].score == 1.0


def test_record_contract_example_threshold_hint(tmp_path, monkeypatch, capsys):
    """Prints hint when count first reaches threshold."""
    import agent.dspy_examples as de
    monkeypatch.setattr(de, "_CONTRACT_EXAMPLES_PATH", tmp_path / "contract.jsonl")
    monkeypatch.setattr(de, "_DATA", tmp_path)
    monkeypatch.setattr(de, "_CONTRACT_THRESHOLD", 3)

    for _ in range(3):
        de.record_contract_example(**_make_example())

    captured = capsys.readouterr()
    assert "optimize_prompts.py --target contract" in captured.out


def test_contract_metric_perfect_score():
    """score=1.0, rounds=1, no stall, no scope → metric = 0.95."""
    import dspy
    from agent.optimization.metrics import contract_metric

    example = dspy.Example(
        score=1.0,
        rounds_taken=1,
        stall_detected=False,
        write_scope_violations=False,
        task_type="email",
    )
    result = contract_metric(example, dspy.Prediction())
    # 0.70*1.0 + 0.15*(2/3) + 0.10*1.0 + 0.05*1.0 = 0.70 + 0.10 + 0.10 + 0.05 = 0.95
    assert abs(result.score - 0.95) < 0.01


def test_contract_metric_failed_with_stall():
    """score=0.0, stall=True, rounds=3 → metric = 0.05."""
    import dspy
    from agent.optimization.metrics import contract_metric

    example = dspy.Example(
        score=0.0,
        rounds_taken=3,
        stall_detected=True,
        write_scope_violations=False,
        task_type="email",
    )
    result = contract_metric(example, dspy.Prediction())
    # 0.70*0 + 0.15*0 + 0.10*0 + 0.05*1 = 0.05
    assert abs(result.score - 0.05) < 0.01


def test_contract_metric_returns_prediction_with_feedback():
    """contract_metric returns dspy.Prediction with score and feedback fields."""
    import dspy
    from agent.optimization.metrics import contract_metric

    example = dspy.Example(
        score=1.0, rounds_taken=2, stall_detected=False,
        write_scope_violations=False, task_type="email",
    )
    result = contract_metric(example, dspy.Prediction())
    assert hasattr(result, "score")
    assert hasattr(result, "feedback")
    assert isinstance(result.feedback, str)
    assert len(result.feedback) > 0
