"""FIX-378 regression: force-read-contact gate auto-relaxes after >=2 empty
/contacts/ searches so a valid email task is not blocked indefinitely (t11
post-mortem).

The gate (FIX-336) was correct in intent — protect against wiki-cached stale
recipients — but its blocking message convinced the agent to give up with
OUTCOME_NONE_CLARIFICATION instead of trying alternatives. After two failed
searches by recipient name, the recipient is provably absent from the vault;
the gate then steps aside and the write proceeds with the task-supplied
address.
"""
from unittest.mock import MagicMock


def _pre_dispatch():
    from agent.loop import _pre_dispatch
    return _pre_dispatch


def _loop_state():
    from agent.loop import _LoopState
    return _LoopState


def _step_fact():
    from agent.log_compaction import _StepFact
    return _StepFact


def _make_write_job(path: str = "/outbox/email_001.json", content: str = '{"to":"x"}'):
    """Build a NextStep-shaped MagicMock targeting a Req_Write on outbox."""
    from agent.models import Req_Write, NextStep
    write = Req_Write(tool="write", path=path, content=content)
    job = NextStep(
        current_state="draft outbox email",
        plan_remaining_steps_brief=["write outbox file"],
        task_completed=False,
        function=write,
    )
    return job


def _make_state(facts: list):
    LoopState = _loop_state()
    st = LoopState()
    st.step_facts = facts
    return st


# ---------------------------------------------------------------------------
# TC1 — bypass: 2 empty /contacts/ searches relax the gate.
# ---------------------------------------------------------------------------

def test_bypass_after_two_empty_contacts_searches():
    SF = _step_fact()
    facts = [
        SF(kind="search", path="/contacts", summary="(no matches)"),
        SF(kind="search", path="/contacts", summary="(no matches)"),
    ]
    st = _make_state(facts)
    job = _make_write_job()
    vm = MagicMock()
    err = _pre_dispatch()(job, "email", vm, st)
    # No force-read-contact block; downstream guards (write-scope etc.) may still
    # produce other errors, so just assert the specific gate did not fire.
    assert err is None or "force-read-contact" not in err


def test_bypass_search_with_error_field():
    SF = _step_fact()
    facts = [
        SF(kind="search", path="/contacts", summary="", error="ERROR not found"),
        SF(kind="search", path="/contacts", summary="", error="ERROR not found"),
    ]
    st = _make_state(facts)
    job = _make_write_job()
    vm = MagicMock()
    err = _pre_dispatch()(job, "email", vm, st)
    assert err is None or "force-read-contact" not in err


# ---------------------------------------------------------------------------
# TC2 — block sustained when only 1 empty search occurred.
# ---------------------------------------------------------------------------

def test_block_with_only_one_empty_search():
    SF = _step_fact()
    facts = [
        SF(kind="search", path="/contacts", summary="(no matches)"),
    ]
    st = _make_state(facts)
    job = _make_write_job()
    vm = MagicMock()
    err = _pre_dispatch()(job, "email", vm, st)
    assert err is not None
    assert "force-read-contact" in err


# ---------------------------------------------------------------------------
# TC3 — block sustained when step_facts is empty.
# ---------------------------------------------------------------------------

def test_block_with_empty_step_facts():
    st = _make_state([])
    job = _make_write_job()
    vm = MagicMock()
    err = _pre_dispatch()(job, "email", vm, st)
    assert err is not None
    assert "force-read-contact" in err


# ---------------------------------------------------------------------------
# TC4 — gate does not apply for non-email task types (existing behavior).
# ---------------------------------------------------------------------------

def test_gate_inert_for_default_task_type():
    st = _make_state([])
    job = _make_write_job()
    vm = MagicMock()
    err = _pre_dispatch()(job, "default", vm, st)
    # The force-read-contact gate is gated on task_type in (email, inbox).
    # For `default`, this gate must not fire (other gates may still apply).
    assert err is None or "force-read-contact" not in err


# ---------------------------------------------------------------------------
# TC5 — searches with hits do NOT bypass: actual contact existed and should
# have been read.
# ---------------------------------------------------------------------------

def test_no_bypass_when_searches_have_hits():
    SF = _step_fact()
    facts = [
        SF(kind="search", path="/contacts", summary="contacts/cont_001.json:3"),
        SF(kind="search", path="/contacts", summary="contacts/cont_002.json:5"),
    ]
    st = _make_state(facts)
    job = _make_write_job()
    vm = MagicMock()
    err = _pre_dispatch()(job, "email", vm, st)
    assert err is not None
    assert "force-read-contact" in err
