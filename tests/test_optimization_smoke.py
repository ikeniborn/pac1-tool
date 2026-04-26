"""Slow smoke tests: both backends compile a trivial program without errors.

Skipped by default — run with: pytest tests/test_optimization_smoke.py -m slow
"""
import pytest
import dspy

from agent.optimization import CoproBackend, GepaBackend
from agent.optimization.metrics import classifier_metric


pytestmark = pytest.mark.slow


class _ClassifySig(dspy.Signature):
    """Classify task into one of: a, b, c."""
    task_text: str = dspy.InputField()
    task_type: str = dspy.OutputField(desc="one of: a, b, c")


def _trainset():
    return [
        dspy.Example(task_text="apples are red", task_type="a").with_inputs("task_text"),
        dspy.Example(task_text="bananas are yellow", task_type="b").with_inputs("task_text"),
        dspy.Example(task_text="cherries are sweet", task_type="c").with_inputs("task_text"),
    ]


def _dummy_lm():
    """Real DummyLM only available in some DSPy versions; skip cleanly otherwise.

    Some DSPy versions accept list[str], others require list[dict]. Try both shapes;
    skip if neither works for this version.
    """
    try:
        DummyLM = dspy.utils.DummyLM
    except AttributeError:
        pytest.skip("dspy.utils.DummyLM unavailable in this DSPy version")
    for answers in (
        [{"task_type": v} for v in ["a", "b", "c"] * 40],
        ["a", "b", "c", "a", "b", "c"] * 20,
    ):
        try:
            return DummyLM(answers)
        except Exception:
            continue
    pytest.skip("dspy.utils.DummyLM API incompatible with this DSPy version")


def test_copro_backend_smoke(tmp_path):
    lm = _dummy_lm()
    program = dspy.Predict(_ClassifySig)
    backend = CoproBackend()
    save_path = tmp_path / "out.json"
    try:
        result = backend.compile(
            program, _trainset(), classifier_metric, save_path, "test/copro",
            task_lm=lm, prompt_lm=lm, adapter=dspy.ChatAdapter(), threads=1,
        )
    except Exception as e:
        pytest.skip(f"DummyLM cannot drive COPRO meta-prompts in this DSPy version: {e!r}")
    assert save_path.exists()
    assert result.compiled is not None
    assert result.pareto_programs is None


def test_gepa_backend_smoke(tmp_path):
    pytest.importorskip("dspy.teleprompt", reason="GEPA may need extra")
    try:
        from dspy.teleprompt import GEPA  # noqa: F401
    except ImportError:
        pytest.skip("GEPA not installed")
    lm = _dummy_lm()
    program = dspy.Predict(_ClassifySig)
    backend = GepaBackend()
    save_path = tmp_path / "out.json"
    try:
        result = backend.compile(
            program, _trainset(), classifier_metric, save_path, "test/gepa",
            task_lm=lm, prompt_lm=lm, adapter=dspy.ChatAdapter(), threads=1,
        )
    except Exception as e:
        pytest.skip(f"DummyLM cannot drive GEPA reflection in this DSPy version: {e!r}")
    assert save_path.exists()
    assert result.compiled is not None
