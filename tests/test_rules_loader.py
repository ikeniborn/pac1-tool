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


def test_append_rule_creates_new_file(tmp_path):
    _make_rules_dir(tmp_path)
    loader = RulesLoader(tmp_path)
    loader.append_rule("New auto rule content.", task_id="t99")
    files_after = list(tmp_path.glob("*.yaml"))
    # Started with 2 files, append creates 1 new file
    assert len(files_after) == 3
    new_files = [f for f in files_after if "t99" not in f.name
                 and f.name not in ("sql-001-verified.yaml", "sql-002-auto.yaml")]
    new_rule = yaml.safe_load(new_files[0].read_text())
    assert new_rule["verified"] is False
    assert new_rule["source"] == "auto"
    assert new_rule["task_id"] == "t99"
    assert new_rule["phase"] == "sql_plan"
    assert "New auto rule content." in new_rule["content"]


def test_append_rule_unique_id(tmp_path):
    _make_rules_dir(tmp_path)
    loader = RulesLoader(tmp_path)
    loader.append_rule("Rule A", task_id="t1")
    loader.append_rule("Rule B", task_id="t2")
    all_rules = [yaml.safe_load(f.read_text()) for f in tmp_path.glob("*.yaml")]
    ids = [r["id"] for r in all_rules]
    assert len(ids) == len(set(ids))


def test_empty_directory_returns_empty(tmp_path):
    loader = RulesLoader(tmp_path)
    assert loader.get_rules_markdown("sql_plan") == ""
