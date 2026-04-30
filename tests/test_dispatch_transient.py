# tests/test_dispatch_transient.py
from unittest.mock import MagicMock, patch

from agent.dispatch import TRANSIENT_KWS, HARD_CONNECTION_KWS


def test_broken_pipe_in_hard_connection_kws():
    err = "[Errno 32] Broken pipe"
    assert any(kw.lower() in err.lower() for kw in HARD_CONNECTION_KWS)


def test_errno_32_in_hard_connection_kws():
    err = "errno 32"
    assert any(kw.lower() in err.lower() for kw in HARD_CONNECTION_KWS)


def test_connection_aborted_in_hard_connection_kws():
    assert any(kw in "connection aborted" for kw in HARD_CONNECTION_KWS)


def test_connection_reset_in_hard_connection_kws():
    """FIX-416b: connection reset is a dead-socket error, not a soft transient."""
    err = "connection reset by peer"
    assert any(kw.lower() in err.lower() for kw in HARD_CONNECTION_KWS)


def test_connection_reset_not_in_transient_kws():
    """FIX-416b: connection reset must NOT be in TRANSIENT_KWS."""
    assert not any(kw in "connection reset" for kw in TRANSIENT_KWS)


def test_rate_limit_still_in_transient_kws():
    assert any(kw in "429" for kw in TRANSIENT_KWS)


def test_overloaded_still_in_transient_kws():
    assert any(kw in "overloaded" for kw in TRANSIENT_KWS)


def test_broken_pipe_not_in_transient_kws():
    """Hard errors must NOT be in TRANSIENT_KWS to avoid the 3-retry loop."""
    assert not any(kw in "broken pipe" for kw in TRANSIENT_KWS)


def test_hard_connection_error_retries_at_most_once():
    """FIX-416: a hard connection error (e.g. ECONNRESET) should result in exactly
    1 retry (2 total call attempts, 1 sleep call), not the 3-retry soft-transient path."""
    from agent.loop import _call_openai_tier

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = ConnectionResetError(
        "connection reset by peer"
    )

    with patch("agent.loop.time.sleep") as mock_sleep:
        result = _call_openai_tier(
            fake_client,
            model="openrouter/test-model",
            log=[{"role": "user", "content": "hi"}],
            max_tokens=100,
            label="TestTier",
        )

    # Hard errors: 1 retry max → sleep called exactly once with delay=2
    assert mock_sleep.call_count == 1, (
        f"Expected 1 sleep (1 retry), got {mock_sleep.call_count}"
    )
    assert mock_sleep.call_args[0][0] == 2, (
        f"Expected hard-error delay=2s, got {mock_sleep.call_args[0][0]}"
    )
    # After the single retry fails, result should be None (no valid response)
    assert result[0] is None


import os
from unittest.mock import patch, call as mcall


def test_call_llm_raw_falls_back_on_total_failure(monkeypatch):
    """When all tiers return None, call_llm_raw retries with MODEL_FALLBACK."""
    monkeypatch.setenv("MODEL_FALLBACK", "fallback-model:test")

    results = iter([None, '{"type": "lookup"}'])

    def fake_single(system, user_msg, model, cfg, **kwargs):
        return next(results)

    # Reload to pick up MODEL_FALLBACK env var
    import importlib
    import agent.dispatch as disp
    importlib.reload(disp)

    with patch.object(disp, "_call_raw_single_model", side_effect=fake_single) as mock:
        result = disp.call_llm_raw(
            "sys", "user", "primary-model:test", {}, max_tokens=10,
        )

    assert result == '{"type": "lookup"}'
    assert mock.call_count == 2
    # Second call uses fallback model
    assert mock.call_args_list[1][0][2] == "fallback-model:test"


def test_call_llm_raw_no_fallback_when_unset(monkeypatch):
    """MODEL_FALLBACK not set → single attempt, returns None on failure."""
    monkeypatch.delenv("MODEL_FALLBACK", raising=False)

    import importlib
    import agent.dispatch as disp
    importlib.reload(disp)

    with patch.object(disp, "_call_raw_single_model", return_value=None) as mock:
        result = disp.call_llm_raw("sys", "user", "primary:test", {}, max_tokens=10)

    assert result is None
    assert mock.call_count == 1
