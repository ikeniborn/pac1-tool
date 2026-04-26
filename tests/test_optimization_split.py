# tests/test_optimization_split.py
"""Unit tests for GepaBackend._split_trainset (deterministic train/val split)."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _get_split():
    mod = importlib.import_module("agent.optimization.gepa_backend")
    return mod._split_trainset


def _make_trainset(n: int) -> list:
    return [{"idx": i} for i in range(n)]


def test_default_split():
    split = _get_split()
    train, val, msg, payload = split(_make_trainset(25), 0.2, 20)
    assert len(train) == 20
    assert val is not None and len(val) == 5
    assert train[-1]["idx"] == 19
    assert val[0]["idx"] == 20
    assert "trainset=20" in msg
    assert "valset=5" in msg
    assert payload["trainset_size"] == 20
    assert payload["valset_size"] == 5
    assert payload["fraction"] == 0.2
    assert "skipped_reason" not in payload


def test_below_min_skips_split():
    split = _get_split()
    train, val, msg, payload = split(_make_trainset(15), 0.2, 20)
    assert len(train) == 15
    assert val is None
    assert "below_min" in msg
    assert payload["valset_size"] == 0
    assert payload["skipped_reason"] == "below_min"


def test_custom_fraction():
    split = _get_split()
    train, val, msg, payload = split(_make_trainset(30), 0.3, 20)
    assert len(train) == 21
    assert val is not None and len(val) == 9
    assert "30%" in msg
    assert payload["fraction"] == 0.3


def test_custom_min_threshold():
    split = _get_split()
    train, val, _msg, _payload = split(_make_trainset(12), 0.2, 10)
    assert len(train) == 9
    assert val is not None and len(val) == 3


def test_invalid_fraction_zero_skips():
    split = _get_split()
    _train, val, msg, payload = split(_make_trainset(30), 0.0, 20)
    assert val is None
    assert payload["skipped_reason"] == "fraction_invalid"
    assert "fraction_invalid" in msg


def test_emit_called():
    split = _get_split()
    calls: list = []
    _train, _val, _msg, payload = split(_make_trainset(25), 0.2, 20)
    emit = lambda event, data: calls.append((event, data))
    emit("split", payload)
    assert len(calls) == 1
    event, data = calls[0]
    assert event == "split"
    assert data["trainset_size"] == 20
    assert data["valset_size"] == 5


def test_no_emit_is_safe():
    split = _get_split()
    _train, _val, _msg, payload = split(_make_trainset(25), 0.2, 20)
    assert isinstance(payload, dict)
