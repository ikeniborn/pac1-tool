"""Tests for FIX-374 researcher retry policy (refusal cap + evaluator gate).

The outer researcher loop is exercised with mocked inner run_loop, reflect,
and evaluator. We verify:
  - Terminal refusals trigger REFUSAL_RETRY up to RESEARCHER_REFUSAL_MAX_RETRIES
    times, then short-circuit with pending_refusal.
  - Self-OUTCOME_OK with RESEARCHER_EVAL_GATED=1 runs evaluator; rejection
    injects EVAL_REJECTED into hypothesis_for_next and continues.
  - Approved OUTCOME_OK sets pending_promotion + builder_used + eval_last_call.
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


def _fake_graph():
    g = MagicMock()
    g.nodes = {}
    g.edges = []
    return g


def _setup_patches(*, cycle_stats_seq, reflections_seq):
    """Return a dict of (target → Mock) to feed into patch.multiple()."""
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
    """Reload researcher with desired env, patch module-level deps, call run_researcher."""
    # Hermetic defaults — keep tests independent of local .env. Individual tests
    # can still override by passing the same key in `env`.
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


def test_refusal_retry_capped(monkeypatch):
    """After RESEARCHER_REFUSAL_MAX_RETRIES refusals, accept refusal & stop."""
    patches = _setup_patches(
        cycle_stats_seq=[
            _fake_cycle_stats("OUTCOME_NONE_CLARIFICATION",
                              report=_fake_report("OUTCOME_NONE_CLARIFICATION"))
            for _ in range(10)
        ],
        reflections_seq=[_fake_reflection("stuck") for _ in range(10)],
    )
    stats = _call_run_researcher(
        monkeypatch, patches,
        env={
            "RESEARCHER_MAX_CYCLES": "10",
            "RESEARCHER_REFUSAL_MAX_RETRIES": "3",
            "RESEARCHER_EVAL_GATED": "0",
            "RESEARCHER_REFUSAL_LAST_CHANCE": "0",  # test pure FIX-374 cap
            "WIKI_GRAPH_ENABLED": "0",
        },
    )
    # 3 retries + 1 accept cycle = 4 total
    assert stats["researcher_refusal_retries"] == 3
    assert stats["researcher_cycles_used"] == 4
    assert stats["researcher_early_stop"] == "OUTCOME_NONE_CLARIFICATION"
    assert "researcher_pending_refusal" in stats
    assert stats.get("researcher_solved", False) is False


def test_evaluator_approves_ok_short_circuits(monkeypatch):
    """OUTCOME_OK + evaluator approve → pending_promotion, builder_used, eval_last_call."""
    patches = _setup_patches(
        cycle_stats_seq=[
            _fake_cycle_stats("OUTCOME_OK", report=_fake_report("OUTCOME_OK")),
        ],
        reflections_seq=[_fake_reflection("solved")],
    )

    with patch("agent.evaluator.evaluate_completion") as eval_mock:
        eval_mock.return_value = types.SimpleNamespace(
            approved=True, issues=[], correction_hint="",
        )
        stats = _call_run_researcher(
            monkeypatch, patches,
            env={
                "RESEARCHER_MAX_CYCLES": "5",
                "RESEARCHER_EVAL_GATED": "1",
                "WIKI_GRAPH_ENABLED": "0",
            },
        )

    assert stats["researcher_solved"] is True
    assert "researcher_pending_promotion" in stats
    assert stats["builder_used"] is True
    # builder_addendum may be empty on cycle 1 (no prior reflections/wiki);
    # main.py gates on `builder_used AND builder_addendum`, so empty addendum
    # simply means nothing to record — not a bug.
    assert stats["eval_last_call"] is not None
    assert stats["eval_last_call"]["proposed_outcome"] == "OUTCOME_OK"
    assert stats["evaluator_calls"] >= 1


def test_evaluator_rejects_then_approves(monkeypatch):
    """Cycle 1: evaluator rejects OK → continue with EVAL_REJECTED.
    Cycle 2: evaluator approves OK → stop."""
    patches = _setup_patches(
        cycle_stats_seq=[
            _fake_cycle_stats("OUTCOME_OK", report=_fake_report("OUTCOME_OK")),
            _fake_cycle_stats("OUTCOME_OK", report=_fake_report("OUTCOME_OK")),
        ],
        reflections_seq=[_fake_reflection("solved"), _fake_reflection("solved")],
    )

    verdicts = [
        types.SimpleNamespace(approved=False, issues=["wrong date"], correction_hint=""),
        types.SimpleNamespace(approved=True, issues=[], correction_hint=""),
    ]
    with patch("agent.evaluator.evaluate_completion", side_effect=verdicts):
        stats = _call_run_researcher(
            monkeypatch, patches,
            env={
                "RESEARCHER_MAX_CYCLES": "5",
                "RESEARCHER_EVAL_GATED": "1",
                "WIKI_GRAPH_ENABLED": "0",
            },
        )

    assert stats["researcher_cycles_used"] == 2
    assert stats["researcher_eval_rejections"] == 1
    assert stats["evaluator_calls"] == 2
    assert "researcher_pending_promotion" in stats
    assert stats["builder_used"] is True


def test_flip_hint_on_repeated_eval_reject(monkeypatch):
    """FIX-375 OK-flip: evaluator rejects OK twice with similar reason →
    OUTCOME_FLIP_HINT injected into hypothesis_for_next."""
    patches = _setup_patches(
        cycle_stats_seq=[
            _fake_cycle_stats("OUTCOME_OK", report=_fake_report("OUTCOME_OK"))
            for _ in range(5)
        ],
        reflections_seq=[_fake_reflection("solved") for _ in range(5)],
    )
    # Evaluator rejects with similar reason across cycles (flip should fire on cycle 2+).
    verdicts = [
        types.SimpleNamespace(approved=False, issues=["no exact match found"], correction_hint=""),
        types.SimpleNamespace(approved=False, issues=["no exact match exists"], correction_hint=""),
        types.SimpleNamespace(approved=False, issues=["no exact match exists"], correction_hint=""),
        types.SimpleNamespace(approved=False, issues=["no exact match exists"], correction_hint=""),
        types.SimpleNamespace(approved=False, issues=["no exact match exists"], correction_hint=""),
    ]
    with patch("agent.evaluator.evaluate_completion", side_effect=verdicts):
        stats = _call_run_researcher(
            monkeypatch, patches,
            env={
                "RESEARCHER_MAX_CYCLES": "5",
                "RESEARCHER_EVAL_GATED": "1",
                "RESEARCHER_FLIP_HINT_ENABLED": "1",
                "RESEARCHER_FLIP_REASON_SIMILARITY_THRESHOLD": "0.5",
                "WIKI_GRAPH_ENABLED": "0",
            },
        )
    # At least one flip hint must have fired (cycle 2 or 3 — similar reasons).
    assert stats.get("researcher_flip_hints_injected", 0) >= 1
    # cycle 5 is final → evaluator skipped; so 4 rejections max
    assert stats["researcher_eval_rejections"] >= 2


def test_flip_hint_on_monotonic_hypotheses(monkeypatch):
    """FIX-375 OK-flip: reflector hypotheses monotonic across cycles →
    flip hint injected even when evaluator reasons differ."""
    from agent.reflector import Reflection

    same_hyp = "try reading the file again and reporting the closest match"
    reflections = [
        Reflection(
            outcome="solved", goal_shape="shape", final_answer="answer",
            hypothesis_for_next=same_hyp, input_tokens=10, output_tokens=5,
        )
        for _ in range(5)
    ]
    patches = _setup_patches(
        cycle_stats_seq=[
            _fake_cycle_stats("OUTCOME_OK", report=_fake_report("OUTCOME_OK"))
            for _ in range(5)
        ],
        reflections_seq=reflections,
    )
    # Different reasons each cycle — only monotonicity detector should fire.
    verdicts = [
        types.SimpleNamespace(approved=False, issues=["alpha reason"], correction_hint=""),
        types.SimpleNamespace(approved=False, issues=["beta different words"], correction_hint=""),
        types.SimpleNamespace(approved=False, issues=["gamma unrelated"], correction_hint=""),
        types.SimpleNamespace(approved=False, issues=["delta orthogonal"], correction_hint=""),
        types.SimpleNamespace(approved=False, issues=["epsilon distinct"], correction_hint=""),
    ]
    with patch("agent.evaluator.evaluate_completion", side_effect=verdicts):
        stats = _call_run_researcher(
            monkeypatch, patches,
            env={
                "RESEARCHER_MAX_CYCLES": "5",
                "RESEARCHER_EVAL_GATED": "1",
                "RESEARCHER_FLIP_HINT_ENABLED": "1",
                "RESEARCHER_FLIP_REASON_SIMILARITY_THRESHOLD": "0.99",  # effectively off
                "RESEARCHER_FLIP_HYP_MONOTONIC_K": "2",
                "RESEARCHER_FLIP_HYP_SIMILARITY_THRESHOLD": "0.6",
                "WIKI_GRAPH_ENABLED": "0",
            },
        )
    assert stats.get("researcher_flip_hints_injected", 0) >= 1


def test_refusal_last_chance_adds_one_cycle(monkeypatch):
    """FIX-375 refusal last-chance: after retry cap, one extra cycle with
    OUTCOME_FLIP_HINT before final accept."""
    # 3 retries + 1 last-chance + 1 final accept = 5 cycles
    patches = _setup_patches(
        cycle_stats_seq=[
            _fake_cycle_stats("OUTCOME_NONE_CLARIFICATION",
                              report=_fake_report("OUTCOME_NONE_CLARIFICATION"))
            for _ in range(6)
        ],
        reflections_seq=[_fake_reflection("stuck") for _ in range(6)],
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
        },
    )
    assert stats["researcher_refusal_retries"] == 3
    assert stats.get("researcher_refusal_last_chance_used") is True
    assert stats.get("researcher_flip_hints_injected", 0) >= 1
    # 3 retries + 1 last-chance + 1 final accept = 5 cycles
    assert stats["researcher_cycles_used"] == 5


def test_refusal_last_chance_disabled(monkeypatch):
    """Last-chance off → behaviour identical to FIX-374 (3 retries + 1 accept)."""
    patches = _setup_patches(
        cycle_stats_seq=[
            _fake_cycle_stats("OUTCOME_NONE_CLARIFICATION",
                              report=_fake_report("OUTCOME_NONE_CLARIFICATION"))
            for _ in range(6)
        ],
        reflections_seq=[_fake_reflection("stuck") for _ in range(6)],
    )
    stats = _call_run_researcher(
        monkeypatch, patches,
        env={
            "RESEARCHER_MAX_CYCLES": "10",
            "RESEARCHER_REFUSAL_MAX_RETRIES": "3",
            "RESEARCHER_REFUSAL_LAST_CHANCE": "0",
            "RESEARCHER_FLIP_HINT_ENABLED": "1",
            "RESEARCHER_EVAL_GATED": "0",
            "WIKI_GRAPH_ENABLED": "0",
        },
    )
    assert stats["researcher_refusal_retries"] == 3
    assert stats.get("researcher_refusal_last_chance_used") is None
    assert stats["researcher_cycles_used"] == 4


def test_ok_loop_hard_guard(monkeypatch):
    """FIX-375b/C: 5 consecutive OUTCOME_OK with same answer triggers hard-guard
    short-circuit to pending_refusal (without waiting for evaluator)."""
    same_msg = "the closest article is X"
    patches = _setup_patches(
        cycle_stats_seq=[
            _fake_cycle_stats(
                "OUTCOME_OK",
                report=_fake_report("OUTCOME_OK", message=same_msg),
            )
            for _ in range(10)
        ],
        reflections_seq=[_fake_reflection("stuck") for _ in range(10)],
    )
    # Eval gate disabled — guard must fire on its own.
    stats = _call_run_researcher(
        monkeypatch, patches,
        env={
            "RESEARCHER_MAX_CYCLES": "10",
            "RESEARCHER_EVAL_GATED": "0",
            "RESEARCHER_OK_LOOP_LIMIT": "5",
            "WIKI_GRAPH_ENABLED": "0",
        },
    )
    assert stats.get("researcher_ok_loop_break") is True
    assert stats["researcher_early_stop"] == "OUTCOME_NONE_CLARIFICATION"
    assert "researcher_pending_refusal" in stats
    # 5 consecutive OK → guard fires on cycle 5
    assert stats["researcher_cycles_used"] == 5


def test_ok_loop_guard_resets_on_different_answer(monkeypatch):
    """Hard-guard counter resets when final_answer changes — agent finding new
    interpretation should not be cut off prematurely."""
    answers = ["answer A", "answer A", "answer B", "answer C", "answer C", "answer D"]
    patches = _setup_patches(
        cycle_stats_seq=[
            _fake_cycle_stats(
                "OUTCOME_OK",
                report=_fake_report("OUTCOME_OK", message=ans),
            )
            for ans in answers
        ],
        reflections_seq=[_fake_reflection("stuck") for _ in range(6)],
    )
    stats = _call_run_researcher(
        monkeypatch, patches,
        env={
            "RESEARCHER_MAX_CYCLES": "6",
            "RESEARCHER_EVAL_GATED": "0",
            "RESEARCHER_OK_LOOP_LIMIT": "3",
            "WIKI_GRAPH_ENABLED": "0",
        },
    )
    # Counter never reaches 3-in-a-row → no hard-guard
    assert stats.get("researcher_ok_loop_break") is None


def test_evaluator_approved_with_stuck_reflector(monkeypatch):
    """FIX-375b/A: evaluator gate fires on OUTCOME_OK even when reflector
    says outcome='stuck'. Approved → short-circuit with pending_promotion."""
    patches = _setup_patches(
        cycle_stats_seq=[
            _fake_cycle_stats("OUTCOME_OK", report=_fake_report("OUTCOME_OK")),
        ],
        reflections_seq=[_fake_reflection("stuck")],  # reflector NOT solved
    )
    with patch("agent.evaluator.evaluate_completion") as eval_mock:
        eval_mock.return_value = types.SimpleNamespace(
            approved=True, issues=[], correction_hint="",
        )
        stats = _call_run_researcher(
            monkeypatch, patches,
            env={
                "RESEARCHER_MAX_CYCLES": "5",
                "RESEARCHER_EVAL_GATED": "1",
                "WIKI_GRAPH_ENABLED": "0",
            },
        )
    # Evaluator was invoked even though reflector said stuck.
    assert stats["evaluator_calls"] >= 1
    assert "researcher_pending_promotion" in stats
    assert stats["researcher_solved"] is True


def test_refusal_counter_resets_on_ok(monkeypatch):
    """FIX-377: refusal cycle (counter=1) → OK cycle (reset to 0) → refusal
    cycle (counter=1, NOT 2). Counter must depend strictly on agent_outcome."""
    # Sequence: refusal, OK, refusal, refusal, refusal, refusal-accept
    outcomes = [
        "OUTCOME_NONE_CLARIFICATION",
        "OUTCOME_OK",
        "OUTCOME_NONE_CLARIFICATION",
        "OUTCOME_NONE_CLARIFICATION",
        "OUTCOME_NONE_CLARIFICATION",
        "OUTCOME_NONE_CLARIFICATION",
    ]
    patches = _setup_patches(
        cycle_stats_seq=[
            _fake_cycle_stats(o, report=_fake_report(o)) for o in outcomes
        ],
        # All reflections "stuck" so OK doesn't short-circuit via is_solved path.
        reflections_seq=[_fake_reflection("stuck") for _ in outcomes],
    )
    # Evaluator off so OK passes through without short-circuit; we'll patch
    # the OK gate via env (EVAL_GATED=0) — OK then continues to next cycle.
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
    # After OK reset, three refusals would increment counter to 3, then 4th
    # refusal hits cap and accepts (cycles 3,4,5 retry; cycle 6 accepts).
    assert stats["researcher_refusal_retries"] == 3
    # Total cycles: 1 refusal + 1 OK + 3 retries + 1 accept = 6
    assert stats["researcher_cycles_used"] == 6
    assert stats["researcher_early_stop"] == "OUTCOME_NONE_CLARIFICATION"


def test_refusal_counter_unaffected_by_consecutive_ok(monkeypatch):
    """FIX-377: pure OUTCOME_OK sequence keeps counter at 0."""
    patches = _setup_patches(
        cycle_stats_seq=[
            _fake_cycle_stats("OUTCOME_OK", report=_fake_report("OUTCOME_OK"))
            for _ in range(4)
        ],
        # stuck reflections so OK doesn't short-circuit via is_solved path.
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


def test_refusal_counter_grows_regardless_of_reflection_outcome(monkeypatch):
    """FIX-377: counter depends ONLY on agent_outcome ∈ _TERMINAL_REFUSALS.
    Even if reflection.outcome='solved', a refusal agent_outcome still
    increments. Reflection branch must not bypass the cap."""
    patches = _setup_patches(
        cycle_stats_seq=[
            _fake_cycle_stats(
                "OUTCOME_NONE_CLARIFICATION",
                report=_fake_report("OUTCOME_NONE_CLARIFICATION"),
            )
            for _ in range(5)
        ],
        # All reflections claim 'solved' — but agent_outcome is refusal.
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
    # Cap reached despite reflection 'solved'.
    assert stats["researcher_refusal_retries"] == 3
    assert stats["researcher_cycles_used"] == 4


def test_refusal_no_evaluator_call(monkeypatch):
    """Terminal refusal must NOT invoke evaluator — retry is unconditional."""
    patches = _setup_patches(
        cycle_stats_seq=[
            _fake_cycle_stats("OUTCOME_NONE_CLARIFICATION",
                              report=_fake_report("OUTCOME_NONE_CLARIFICATION")),
            _fake_cycle_stats("OUTCOME_NONE_CLARIFICATION",
                              report=_fake_report("OUTCOME_NONE_CLARIFICATION")),
        ],
        reflections_seq=[_fake_reflection("stuck"), _fake_reflection("stuck")],
    )
    with patch("agent.evaluator.evaluate_completion") as eval_mock:
        _call_run_researcher(
            monkeypatch, patches,
            env={
                "RESEARCHER_MAX_CYCLES": "2",
                "RESEARCHER_REFUSAL_MAX_RETRIES": "5",
                "RESEARCHER_EVAL_GATED": "1",
                "WIKI_GRAPH_ENABLED": "0",
            },
        )
        assert eval_mock.call_count == 0
