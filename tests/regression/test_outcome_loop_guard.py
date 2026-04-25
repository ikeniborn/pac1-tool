"""FIX-377: outcome-only loop guard regression tests.

Parallel to FIX-375b/C (same-answer guard). Trips on N consecutive cycles
with identical agent_outcome regardless of message text. Targets t11-class
where refusals are rephrased between cycles so the same-answer guard never
matches.

Pattern: mock run_loop, reflect, evaluator (same as test_researcher_retry).
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


def _fake_cycle_stats(outcome, *, report=None):
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
    }


def _fake_reflection(outcome="stuck"):
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


def test_outcome_loop_guard_refusal_rephrased(monkeypatch):
    """TC1: 4 cycles agent_outcome=OUTCOME_NONE_CLARIFICATION with different
    messages each time → guard trips on cycle 4, accepts refusal early.

    Disable the FIX-374 refusal-retry path so we isolate the new guard.
    Refusal-retry caps at RESEARCHER_REFUSAL_MAX_RETRIES, but with a high
    cap and disabled last-chance, FIX-377 should fire first."""
    messages = ["I cannot determine X", "It's unclear what Y means",
                "The request is ambiguous", "No way to proceed without info"]
    patches = _setup_patches(
        cycle_stats_seq=[
            _fake_cycle_stats(
                "OUTCOME_NONE_CLARIFICATION",
                report=_fake_report("OUTCOME_NONE_CLARIFICATION", message=msg),
            )
            for msg in messages
        ],
        reflections_seq=[_fake_reflection("stuck") for _ in range(4)],
    )
    stats = _call_run_researcher(
        monkeypatch, patches,
        env={
            "RESEARCHER_MAX_CYCLES": "10",
            # Set refusal cap high so FIX-377 outcome-loop guard fires first.
            "RESEARCHER_REFUSAL_MAX_RETRIES": "20",
            "RESEARCHER_REFUSAL_LAST_CHANCE": "0",
            "RESEARCHER_EVAL_GATED": "0",
            "RESEARCHER_OUTCOME_LOOP_LIMIT": "4",
            "WIKI_GRAPH_ENABLED": "0",
        },
    )
    assert stats.get("researcher_outcome_loop_break") is True
    assert stats["researcher_early_stop"] == "OUTCOME_NONE_CLARIFICATION"
    assert "researcher_pending_refusal" in stats
    assert stats["researcher_pending_refusal"]["outcome"] == "OUTCOME_NONE_CLARIFICATION"
    assert stats["researcher_cycles_used"] == 4


def test_outcome_loop_guard_ok_flip(monkeypatch):
    """TC2: 4 cycles agent_outcome=OUTCOME_OK with different final_answer
    each time → guard trips, flips to OUTCOME_NONE_CLARIFICATION.

    FIX-375b/C identical-answer guard does NOT trigger because answers
    differ. FIX-377 outcome-only counter does."""
    answers = ["answer A", "answer B", "answer C", "answer D"]
    patches = _setup_patches(
        cycle_stats_seq=[
            _fake_cycle_stats(
                "OUTCOME_OK",
                report=_fake_report("OUTCOME_OK", message=ans),
            )
            for ans in answers
        ],
        reflections_seq=[_fake_reflection("stuck") for _ in range(4)],
    )
    stats = _call_run_researcher(
        monkeypatch, patches,
        env={
            "RESEARCHER_MAX_CYCLES": "10",
            "RESEARCHER_EVAL_GATED": "0",
            # Set OK_LOOP_LIMIT high so FIX-375b/C does not trigger.
            "RESEARCHER_OK_LOOP_LIMIT": "100",
            "RESEARCHER_OUTCOME_LOOP_LIMIT": "4",
            "WIKI_GRAPH_ENABLED": "0",
        },
    )
    assert stats.get("researcher_outcome_loop_break") is True
    # FIX-375b/C did not fire (different answers).
    assert stats.get("researcher_ok_loop_break") is None
    assert stats["researcher_early_stop"] == "OUTCOME_NONE_CLARIFICATION"
    assert "researcher_pending_refusal" in stats
    assert stats["researcher_pending_refusal"]["outcome"] == "OUTCOME_NONE_CLARIFICATION"
    assert stats["researcher_cycles_used"] == 4


def test_outcome_loop_guard_resets_on_alternation(monkeypatch):
    """TC3: alternating OK/NONE_CLARIFICATION → counter resets each time,
    guard never trips."""
    outcomes = ["OUTCOME_OK", "OUTCOME_NONE_CLARIFICATION",
                "OUTCOME_OK", "OUTCOME_NONE_CLARIFICATION"]
    patches = _setup_patches(
        cycle_stats_seq=[
            _fake_cycle_stats(o, report=_fake_report(o, message=f"msg-{i}"))
            for i, o in enumerate(outcomes)
        ],
        reflections_seq=[_fake_reflection("stuck") for _ in range(4)],
    )
    stats = _call_run_researcher(
        monkeypatch, patches,
        env={
            "RESEARCHER_MAX_CYCLES": "4",
            # High refusal cap → FIX-374 retry path won't short-circuit on
            # the trailing NONE_CLARIFICATION before max_cycles.
            "RESEARCHER_REFUSAL_MAX_RETRIES": "20",
            "RESEARCHER_REFUSAL_LAST_CHANCE": "0",
            "RESEARCHER_EVAL_GATED": "0",
            "RESEARCHER_OK_LOOP_LIMIT": "100",
            "RESEARCHER_OUTCOME_LOOP_LIMIT": "4",
            "WIKI_GRAPH_ENABLED": "0",
        },
    )
    assert stats.get("researcher_outcome_loop_break") is None


def test_outcome_loop_guard_high_limit_no_trigger(monkeypatch):
    """TC4: RESEARCHER_OUTCOME_LOOP_LIMIT=10 → 4 cycles same outcome do not
    cross threshold; guard does not fire."""
    patches = _setup_patches(
        cycle_stats_seq=[
            _fake_cycle_stats(
                "OUTCOME_NONE_CLARIFICATION",
                report=_fake_report("OUTCOME_NONE_CLARIFICATION", message=f"msg-{i}"),
            )
            for i in range(4)
        ],
        reflections_seq=[_fake_reflection("stuck") for _ in range(4)],
    )
    stats = _call_run_researcher(
        monkeypatch, patches,
        env={
            "RESEARCHER_MAX_CYCLES": "4",
            "RESEARCHER_REFUSAL_MAX_RETRIES": "20",
            "RESEARCHER_REFUSAL_LAST_CHANCE": "0",
            "RESEARCHER_EVAL_GATED": "0",
            "RESEARCHER_OUTCOME_LOOP_LIMIT": "10",
            "WIKI_GRAPH_ENABLED": "0",
        },
    )
    assert stats.get("researcher_outcome_loop_break") is None
