"""Tests for env-driven backend selection."""
import pytest

from agent.optimization import select_backend


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("OPTIMIZER_DEFAULT", "OPTIMIZER_BUILDER",
              "OPTIMIZER_EVALUATOR", "OPTIMIZER_CLASSIFIER"):
        monkeypatch.delenv(k, raising=False)


def test_default_is_copro():
    assert select_backend("builder").name == "copro"


def test_optimizer_default_gepa(monkeypatch):
    monkeypatch.setenv("OPTIMIZER_DEFAULT", "gepa")
    assert select_backend("builder").name == "gepa"
    assert select_backend("evaluator").name == "gepa"


def test_per_target_beats_default(monkeypatch):
    monkeypatch.setenv("OPTIMIZER_DEFAULT", "gepa")
    monkeypatch.setenv("OPTIMIZER_BUILDER", "copro")
    assert select_backend("builder").name == "copro"
    assert select_backend("evaluator").name == "gepa"


def test_uppercase_value(monkeypatch):
    monkeypatch.setenv("OPTIMIZER_BUILDER", "GEPA")
    assert select_backend("builder").name == "gepa"


def test_unknown_target_uses_default(monkeypatch):
    monkeypatch.setenv("OPTIMIZER_DEFAULT", "copro")
    assert select_backend("misc").name == "copro"


def test_invalid_value_falls_back_to_copro(monkeypatch):
    monkeypatch.setenv("OPTIMIZER_BUILDER", "supersonic")
    assert select_backend("builder").name == "copro"


def test_target_label_with_slash(monkeypatch):
    """log_label like 'builder/global' or 'builder/email' should map to OPTIMIZER_BUILDER."""
    monkeypatch.setenv("OPTIMIZER_BUILDER", "gepa")
    assert select_backend("builder/global").name == "gepa"
    assert select_backend("builder/email").name == "gepa"
