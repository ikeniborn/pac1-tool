"""Tests for GEPA budget resolution."""
import pytest

from agent.optimization.budget import resolve_budget


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("GEPA_AUTO", "GEPA_BUDGET_OVERRIDE"):
        monkeypatch.delenv(k, raising=False)


def test_default_is_light():
    assert resolve_budget() == {"auto": "light"}


def test_auto_medium(monkeypatch):
    monkeypatch.setenv("GEPA_AUTO", "medium")
    assert resolve_budget() == {"auto": "medium"}


def test_auto_heavy_uppercase(monkeypatch):
    monkeypatch.setenv("GEPA_AUTO", "HEAVY")
    assert resolve_budget() == {"auto": "heavy"}


def test_override_max_full_evals(monkeypatch):
    monkeypatch.setenv("GEPA_BUDGET_OVERRIDE", "max_full_evals=20")
    assert resolve_budget() == {"max_full_evals": 20}


def test_override_max_metric_calls_with_spaces(monkeypatch):
    monkeypatch.setenv("GEPA_BUDGET_OVERRIDE", " max_metric_calls = 200 ")
    assert resolve_budget() == {"max_metric_calls": 200}


def test_override_beats_auto(monkeypatch):
    monkeypatch.setenv("GEPA_AUTO", "heavy")
    monkeypatch.setenv("GEPA_BUDGET_OVERRIDE", "max_full_evals=5")
    assert resolve_budget() == {"max_full_evals": 5}


def test_invalid_auto_falls_back_to_light(monkeypatch):
    monkeypatch.setenv("GEPA_AUTO", "extreme")
    assert resolve_budget() == {"auto": "light"}
