"""FIX-377 Unit 1: researcher short-circuits on cycle ≥ 2 INVALID_ARGUMENT.

When the harness rejects a 2nd ReportTaskCompletion (cycle 1 already locked
in an answer), the researcher must NOT call reflect() again — instead it
short-circuits using cycle 1's snapshot.
"""
from __future__ import annotations

import importlib
import types
from unittest.mock import MagicMock, patch


def _fake_prephase():
    return types.SimpleNamespace(
        log=[{"role": "system", "content": ""}],
        preserve_prefix=[{"role": "system", "content": ""}],
    )


def _fake_report(outcome="OUTCOME_OK", message="done"):
    return types.SimpleNamespace(
        outcome=outcome,
        message=message,
        completed_steps_laconic=["step a"],
        done_operations=[],
    )


def _fake_cycle_stats(outcome, *, report=None, dispatch_err_code=None,
                     report_attempted=False):
    return {
        "outcome": outcome,
        "step_facts": [],
        "done_ops": [],
        "input_tokens": 100, "output_tokens": 50,
        "cache_creation_tokens": 0, "cache_read_tokens": 0,
        "llm_elapsed_ms": 0, "ollama_eval_count": 0, "ollama_eval_ms": 0,
        "step_count": 3, "llm_call_count": 1,
        "evaluator_calls": 0, "evaluator_rejections": 0, "evaluator_ms": 0,
        "stall_hints": [], "report": report,
        "report_completion_attempted": report_attempted,
        "report_completion_dispatch_error_code": dispatch_err_code,
        "report_completion_succeeded": report is not None and dispatch_err_code is None,
    }


def _fake_reflection(outcome="solved"):
    from agent.reflector import Reflection
    return Reflection(
        outcome=outcome,
        goal_shape="test shape",
        final_answer="answer" if outcome == "solved" else "",
        hypothesis_for_next="try differently",
        input_tokens=10, output_tokens=5,
    )


def _fake_graph():
    g = MagicMock()
    g.nodes = {}
    g.edges = []
    return g


def _setup_patches(*, cycle_stats_seq, reflections_seq):
    fake_graph = _fake_graph()
    wiki_graph_mock = MagicMock()
    wiki_graph_mock.load_graph.return_value = fake_graph
    wiki_graph_mock.Graph.return_value = fake_graph
    wiki_graph_mock.retrieve_relevant.return_value = ""
    wiki_graph_mock.hash_trajectory.return_value = "hash"
    wiki_graph_mock.merge_updates.return_value = []
    wiki_graph_mock.save_graph.return_value = None
    wiki_graph_mock.add_pattern_node.return_value = None

    return {
        "PcmRuntimeClientSync": MagicMock(return_value=MagicMock()),
        "run_prephase": MagicMock(side_effect=lambda *a, **k: _fake_prephase()),
        "run_loop": MagicMock(side_effect=list(cycle_stats_seq)),
        "reflect": MagicMock(side_effect=list(reflections_seq)),
        "load_wiki_patterns": MagicMock(return_value=""),
        "_load_negative_warnings": MagicMock(return_value=""),
        "_parse_page_patterns": MagicMock(return_value=[]),
        "write_fragment": MagicMock(),
        "render_fragment": MagicMock(return_value=""),
        "build_system_prompt": MagicMock(return_value="SYSTEM"),
        "wiki_graph": wiki_graph_mock,
    }


def _call_run_researcher(monkeypatch, patches, env=None):
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    import agent.researcher as researcher
    importlib.reload(researcher)

    with patch.multiple("agent.researcher", **patches):
        return researcher.run_researcher(
            harness_url="mock://test",
            task_text="test task",
            task_id="t99",
            task_type="default",
            model="mock/model",
            cfg={},
        )


def test_cycle2_invalid_argument_short_circuits_with_cycle1_snapshot(monkeypatch):
    """U1.TC1: cycle 1 OUTCOME_OK, cycle 2 INVALID_ARGUMENT on report →
    short-circuit, reflect NOT called for cycle 2, pending_promotion uses
    cycle 1 snapshot."""
    cycle_stats_seq = [
        # Cycle 1: agent reports OK successfully
        _fake_cycle_stats("OUTCOME_OK", report=_fake_report("OUTCOME_OK"),
                          report_attempted=True),
        # Cycle 2: report dispatch fails with INVALID_ARGUMENT
        _fake_cycle_stats("OUTCOME_OK", report=None,
                          dispatch_err_code="INVALID_ARGUMENT",
                          report_attempted=True),
    ]
    reflect_mock = MagicMock(side_effect=[
        _fake_reflection("stuck"),  # cycle 1: not solved → outer continues
    ])
    patches = _setup_patches(
        cycle_stats_seq=cycle_stats_seq,
        reflections_seq=[],
    )
    patches["reflect"] = reflect_mock

    stats = _call_run_researcher(
        monkeypatch, patches,
        env={
            "RESEARCHER_MAX_CYCLES": "5",
            "RESEARCHER_EVAL_GATED": "0",
            "WIKI_GRAPH_ENABLED": "0",
        },
    )

    assert stats.get("researcher_first_answer_final") is True
    assert stats.get("researcher_early_stop") == "first_answer_final"
    assert "researcher_pending_promotion" in stats
    # reflect was called exactly once (cycle 1), NOT cycle 2
    assert reflect_mock.call_count == 1


def test_cycle1_invalid_argument_does_NOT_short_circuit(monkeypatch):
    """U1.TC2: dispatch error on cycle 1 (cycle_index == 1) must NOT trigger
    the short-circuit — there is no snapshot to fall back to."""
    cycle_stats_seq = [
        _fake_cycle_stats("OUTCOME_OK", report=None,
                          dispatch_err_code="INVALID_ARGUMENT",
                          report_attempted=True),
        _fake_cycle_stats("OUTCOME_OK", report=_fake_report("OUTCOME_OK"),
                          report_attempted=True),
    ]
    # Both cycles return reflection.outcome="stuck" so the existing solved
    # short-circuit doesn't fire. We just want to prove the FIX-377 guard
    # does NOT trigger on cycle 1.
    reflect_mock = MagicMock(side_effect=[
        _fake_reflection("stuck"),
        _fake_reflection("stuck"),
    ])
    patches = _setup_patches(
        cycle_stats_seq=cycle_stats_seq,
        reflections_seq=[],
    )
    patches["reflect"] = reflect_mock

    stats = _call_run_researcher(
        monkeypatch, patches,
        env={
            "RESEARCHER_MAX_CYCLES": "2",
            "RESEARCHER_EVAL_GATED": "0",
            "WIKI_GRAPH_ENABLED": "0",
        },
    )

    assert stats.get("researcher_first_answer_final") is not True
    # reflect called for both cycles (cycle 1 dispatch error did NOT short-circuit)
    assert reflect_mock.call_count == 2


def test_cycle2_other_error_code_does_NOT_short_circuit(monkeypatch):
    """U1.TC3: cycle 2 dispatch error with NOT_FOUND (not INVALID_ARGUMENT) →
    no short-circuit."""
    cycle_stats_seq = [
        _fake_cycle_stats("OUTCOME_OK", report=_fake_report("OUTCOME_OK"),
                          report_attempted=True),
        _fake_cycle_stats("OUTCOME_OK", report=None,
                          dispatch_err_code="NOT_FOUND",
                          report_attempted=True),
        _fake_cycle_stats("OUTCOME_OK", report=_fake_report("OUTCOME_OK"),
                          report_attempted=True),
    ]
    reflect_mock = MagicMock(side_effect=[
        _fake_reflection("stuck"),
        _fake_reflection("stuck"),
        _fake_reflection("solved"),
    ])
    patches = _setup_patches(
        cycle_stats_seq=cycle_stats_seq,
        reflections_seq=[],
    )
    patches["reflect"] = reflect_mock

    stats = _call_run_researcher(
        monkeypatch, patches,
        env={
            "RESEARCHER_MAX_CYCLES": "3",
            "RESEARCHER_EVAL_GATED": "0",
            "WIKI_GRAPH_ENABLED": "0",
        },
    )

    assert stats.get("researcher_first_answer_final") is not True
    # reflect called for all cycles up through solve
    assert reflect_mock.call_count == 3
