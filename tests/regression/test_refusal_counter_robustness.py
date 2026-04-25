"""FIX-377 regression: refusal counter robustness.

Origin: t11 produced 9 refusal cycles despite RESEARCHER_REFUSAL_MAX_RETRIES=3.
Root cause: the cap check sat below reflection-dependent branches that could
bypass it, and the counter was never reset on a non-refusal outcome.

Invariant under test: stats["researcher_refusal_retries"] depends STRICTLY on
agent_outcome ∈ _TERMINAL_REFUSALS. Reset on OUTCOME_OK. Reflection.outcome
must not influence the counter or the cap.
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
        completed_steps_laconic=["step a", "step b"],
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


def _setup_patches(*, cycle_stats_seq, reflections_seq):
    fake_graph = MagicMock()
    fake_graph.nodes = {}
    fake_graph.edges = []
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
    # Hermetic defaults — independent of local .env.
    _hermetic = {
        "RESEARCHER_REFUSAL_DYNAMIC": "0",
        "RESEARCHER_HINT_FORCING": "0",
        "RESEARCHER_MIDCYCLE_BREAKOUT": "0",
        "RESEARCHER_STEPS_ADAPTIVE": "0",
        "RESEARCHER_SOFT_STALL": "0",
        "RESEARCHER_GRAPH_QUARANTINE": "0",
        "RESEARCHER_DRIFT_HINTS": "0",
        "RESEARCHER_REFLECTOR_DIVERSIFY": "0",
        "RESEARCHER_TOTAL_STEP_BUDGET": "0",
        "RESEARCHER_EVAL_FAIL_CLOSED": "0",
    }
    for k, v in _hermetic.items():
        monkeypatch.setenv(k, v)
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


# ---------------------------------------------------------------------------
# TC1: 5 refusal cycles with varied reflection outcomes (stuck/partial/error/
#      stuck/partial). Counter MUST grow 1,2,3, then last-chance, then accept.
# ---------------------------------------------------------------------------
def test_tc1_varied_reflection_does_not_disturb_counter(monkeypatch):
    refl_outcomes = ["stuck", "partial", "error", "stuck", "partial"]
    patches = _setup_patches(
        cycle_stats_seq=[
            _fake_cycle_stats(
                "OUTCOME_NONE_CLARIFICATION",
                report=_fake_report("OUTCOME_NONE_CLARIFICATION"),
            )
            for _ in refl_outcomes
        ],
        reflections_seq=[_fake_reflection(o) for o in refl_outcomes],
    )
    stats = _call_run_researcher(
        monkeypatch, patches,
        env={
            "RESEARCHER_MAX_CYCLES": "10",
            "RESEARCHER_REFUSAL_MAX_RETRIES": "3",
            "RESEARCHER_REFUSAL_LAST_CHANCE": "1",
            "RESEARCHER_FLIP_HINT_ENABLED": "1",
            "RESEARCHER_EVAL_GATED": "0",
            "WIKI_GRAPH_ENABLED": "0",
            "RESEARCHER_OUTCOME_LOOP_LIMIT": "100",
        },
    )
    # 3 retries + 1 last-chance + 1 final accept = 5 cycles
    assert stats["researcher_refusal_retries"] == 3
    assert stats.get("researcher_refusal_last_chance_used") is True
    assert stats["researcher_cycles_used"] == 5
    assert stats["researcher_early_stop"] == "OUTCOME_NONE_CLARIFICATION"


# ---------------------------------------------------------------------------
# TC2: refusal(c1) → OK(c2: reset) → refusal(c3: counter=1, NOT 2) → ...
# ---------------------------------------------------------------------------
def test_tc2_ok_resets_counter_between_refusal_runs(monkeypatch):
    outcomes = [
        "OUTCOME_NONE_CLARIFICATION",  # c1: counter -> 1
        "OUTCOME_OK",                  # c2: reset to 0 (reflection stuck so no short-circuit)
        "OUTCOME_NONE_CLARIFICATION",  # c3: counter -> 1
        "OUTCOME_NONE_CLARIFICATION",  # c4: counter -> 2
        "OUTCOME_NONE_CLARIFICATION",  # c5: counter -> 3
        "OUTCOME_NONE_CLARIFICATION",  # c6: cap hit -> accept
    ]
    patches = _setup_patches(
        cycle_stats_seq=[
            _fake_cycle_stats(o, report=_fake_report(o)) for o in outcomes
        ],
        reflections_seq=[_fake_reflection("stuck") for _ in outcomes],
    )
    stats = _call_run_researcher(
        monkeypatch, patches,
        env={
            "RESEARCHER_MAX_CYCLES": "10",
            "RESEARCHER_REFUSAL_MAX_RETRIES": "3",
            "RESEARCHER_REFUSAL_LAST_CHANCE": "0",
            "RESEARCHER_EVAL_GATED": "0",
            "RESEARCHER_OK_LOOP_LIMIT": "100",  # disable hard guard
            "WIKI_GRAPH_ENABLED": "0",
        },
    )
    assert stats["researcher_refusal_retries"] == 3
    # 1 refusal + 1 OK + 3 refusal-retries + 1 refusal-accept = 6
    assert stats["researcher_cycles_used"] == 6
    assert stats["researcher_early_stop"] == "OUTCOME_NONE_CLARIFICATION"


# ---------------------------------------------------------------------------
# TC3: only OUTCOME_OK → counter stays 0, never grows.
# ---------------------------------------------------------------------------
def test_tc3_pure_ok_keeps_counter_zero(monkeypatch):
    patches = _setup_patches(
        cycle_stats_seq=[
            _fake_cycle_stats("OUTCOME_OK", report=_fake_report("OUTCOME_OK"))
            for _ in range(4)
        ],
        reflections_seq=[_fake_reflection("stuck") for _ in range(4)],
    )
    stats = _call_run_researcher(
        monkeypatch, patches,
        env={
            "RESEARCHER_MAX_CYCLES": "4",
            "RESEARCHER_EVAL_GATED": "0",
            "RESEARCHER_OK_LOOP_LIMIT": "100",  # disable hard guard
            "WIKI_GRAPH_ENABLED": "0",
        },
    )
    assert stats.get("researcher_refusal_retries", 0) == 0


# ---------------------------------------------------------------------------
# TC4: agent_outcome=refusal + reflection.outcome=solved → counter STILL grows.
#      The cap depends ONLY on agent_outcome, not on reflection.
# ---------------------------------------------------------------------------
def test_tc4_solved_reflection_does_not_bypass_refusal_cap(monkeypatch):
    patches = _setup_patches(
        cycle_stats_seq=[
            _fake_cycle_stats(
                "OUTCOME_NONE_CLARIFICATION",
                report=_fake_report("OUTCOME_NONE_CLARIFICATION"),
            )
            for _ in range(5)
        ],
        # reflection.outcome="solved" — must NOT bypass the cap because
        # agent_outcome is refusal. is_solved branch only fires on OUTCOME_OK.
        reflections_seq=[_fake_reflection("solved") for _ in range(5)],
    )
    stats = _call_run_researcher(
        monkeypatch, patches,
        env={
            "RESEARCHER_MAX_CYCLES": "10",
            "RESEARCHER_REFUSAL_MAX_RETRIES": "3",
            "RESEARCHER_REFUSAL_LAST_CHANCE": "0",
            "RESEARCHER_EVAL_GATED": "0",
            "WIKI_GRAPH_ENABLED": "0",
        },
    )
    assert stats["researcher_refusal_retries"] == 3
    assert stats["researcher_cycles_used"] == 4
    assert stats["researcher_early_stop"] == "OUTCOME_NONE_CLARIFICATION"
