# tests/test_dispatch_transient.py
from agent.dispatch import TRANSIENT_KWS, HARD_CONNECTION_KWS


def test_broken_pipe_in_hard_connection_kws():
    err = "[Errno 32] Broken pipe"
    assert any(kw.lower() in err.lower() for kw in HARD_CONNECTION_KWS)


def test_errno_32_in_hard_connection_kws():
    err = "errno 32"
    assert any(kw.lower() in err.lower() for kw in HARD_CONNECTION_KWS)


def test_connection_aborted_in_hard_connection_kws():
    assert any(kw in "connection aborted" for kw in HARD_CONNECTION_KWS)


def test_rate_limit_still_in_transient_kws():
    assert any(kw in "429" for kw in TRANSIENT_KWS)


def test_overloaded_still_in_transient_kws():
    assert any(kw in "overloaded" for kw in TRANSIENT_KWS)


def test_broken_pipe_not_in_transient_kws():
    """Hard errors must NOT be in TRANSIENT_KWS to avoid the 3-retry loop."""
    assert not any(kw in "broken pipe" for kw in TRANSIENT_KWS)
