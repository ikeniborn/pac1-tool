"""FIX-377 Unit 2: skip wiki_graph.merge_updates when cycle was contaminated.

Reflector hallucinates rules from broken trajectories (dispatch errors,
self-reported error/stuck). Verify merge_updates is skipped in those cases
and called normally on clean cycles.
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
        hypothesis_for_next="next",
        input_tokens=10, output_tokens=5,
        graph_deltas={"new_insights": [{"id": "x", "tags": ["t"], "text": "y"}]},
    )


def _build_patches(*, cycle_stats_seq, reflections_seq):
    fake_graph = MagicMock()
    fake_graph.nodes = {}
    fake_graph.edges = []
    wiki_graph_mock = MagicMock()
    wiki_graph_mock.load_graph.return_value = fake_graph
    wiki_graph_mock.Graph.return_value = fake_graph
    wiki_graph_mock.retrieve_relevant.return_value = ""
    wiki_graph_mock.hash_trajectory.return_value = "hash"
    wiki_graph_mock.merge_updates.return_value = ["node1"]
    wiki_graph_mock.save_graph.return_value = None
    wiki_graph_mock.add_pattern_node.return_value = None

    return wiki_graph_mock, {
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


def _call(monkeypatch, patches, env=None):
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


def test_dispatch_error_skips_merge(monkeypatch):
    """U2.TC1: report_completion_dispatch_error_code set → merge skipped,
    counter incremented."""
    cycle_stats_seq = [
        # Cycle 1: clean OK → reflect.outcome=stuck so outer keeps going
        _fake_cycle_stats("OUTCOME_OK", report=_fake_report("OUTCOME_OK"),
                          report_attempted=True),
        # Cycle 2: dispatch error — short-circuit will fire BEFORE merge logic
        # because INVALID_ARGUMENT triggers Unit-1 short-circuit. To exercise
        # Unit-2 alone, use a non-INVALID_ARGUMENT error code.
        _fake_cycle_stats("OUTCOME_OK", report=None,
                          dispatch_err_code="INTERNAL",
                          report_attempted=True),
    ]
    refl_seq = [
        _fake_reflection("stuck"),  # cycle 1: stuck → also triggers skip via outcome
        _fake_reflection("solved"),  # cycle 2: would normally merge, but dispatch_err blocks
    ]
    wiki_graph_mock, patches = _build_patches(
        cycle_stats_seq=cycle_stats_seq,
        reflections_seq=refl_seq,
    )
    stats = _call(
        monkeypatch, patches,
        env={
            "RESEARCHER_MAX_CYCLES": "2",
            "RESEARCHER_EVAL_GATED": "0",
            "WIKI_GRAPH_ENABLED": "1",
        },
    )
    # Cycle 1: skipped (outcome=stuck). Cycle 2: skipped (dispatch_err).
    assert wiki_graph_mock.merge_updates.call_count == 0
    assert stats.get("researcher_graph_merge_skipped", 0) >= 2


def test_reflection_stuck_skips_merge(monkeypatch):
    """U2.TC2: reflection.outcome='stuck' → merge skipped."""
    cycle_stats_seq = [
        _fake_cycle_stats("OUTCOME_OK", report=_fake_report("OUTCOME_OK"),
                          report_attempted=True),
    ]
    refl_seq = [_fake_reflection("stuck")]
    wiki_graph_mock, patches = _build_patches(
        cycle_stats_seq=cycle_stats_seq,
        reflections_seq=refl_seq,
    )
    _call(
        monkeypatch, patches,
        env={
            "RESEARCHER_MAX_CYCLES": "1",
            "RESEARCHER_EVAL_GATED": "0",
            "WIKI_GRAPH_ENABLED": "1",
        },
    )
    assert wiki_graph_mock.merge_updates.call_count == 0


def test_clean_cycle_does_merge(monkeypatch):
    """U2.TC3: clean cycle (no dispatch err, outcome=solved) → merge IS called."""
    cycle_stats_seq = [
        _fake_cycle_stats("OUTCOME_OK", report=_fake_report("OUTCOME_OK"),
                          report_attempted=True),
    ]
    refl_seq = [_fake_reflection("solved")]
    wiki_graph_mock, patches = _build_patches(
        cycle_stats_seq=cycle_stats_seq,
        reflections_seq=refl_seq,
    )
    _call(
        monkeypatch, patches,
        env={
            "RESEARCHER_MAX_CYCLES": "1",
            "RESEARCHER_EVAL_GATED": "0",
            "WIKI_GRAPH_ENABLED": "1",
        },
    )
    assert wiki_graph_mock.merge_updates.call_count == 1
