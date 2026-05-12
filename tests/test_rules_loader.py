# tests/test_rules_loader.py
from pathlib import Path
import yaml
import pytest
from agent.rules_loader import RulesLoader, _RULES_DIR


def _make_rules_dir(tmp_path: Path) -> Path:
    """Create a rules directory with two individual rule files."""
    (tmp_path / "sql-001-verified.yaml").write_text(
        yaml.dump({"id": "sql-001", "phase": "sql_plan", "verified": True,
                   "source": "manual", "content": "Never full scan.",
                   "created": "2026-05-12", "task_id": None}, allow_unicode=True)
    )
    (tmp_path / "sql-002-auto.yaml").write_text(
        yaml.dump({"id": "sql-002", "phase": "sql_plan", "verified": False,
                   "source": "auto", "content": "Auto rule.",
                   "created": "2026-05-12", "task_id": "t01"}, allow_unicode=True)
    )
    return tmp_path


def test_load_verified_rules_only(tmp_path):
    _make_rules_dir(tmp_path)
    loader = RulesLoader(tmp_path)
    md = loader.get_rules_markdown(phase="sql_plan", verified_only=True)
    assert "Never full scan." in md
    assert "Auto rule." not in md


def test_load_all_rules(tmp_path):
    _make_rules_dir(tmp_path)
    loader = RulesLoader(tmp_path)
    md = loader.get_rules_markdown(phase="sql_plan", verified_only=False)
    assert "Never full scan." in md
    assert "Auto rule." in md


def test_empty_directory_returns_empty(tmp_path):
    loader = RulesLoader(tmp_path)
    assert loader.get_rules_markdown("sql_plan") == ""
