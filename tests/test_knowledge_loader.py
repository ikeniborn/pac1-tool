from unittest.mock import patch
import agent.knowledge_loader as kl


def test_existing_rules_text_includes_id(tmp_path):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "sql-001.yaml").write_text(
        "id: sql-001\nphase: sql_plan\nverified: true\ncontent: Never SELECT star.\n"
    )
    with patch.object(kl, "_RULES_DIR", rules_dir):
        result = kl.existing_rules_text()
    assert "- sql-001: Never SELECT star." in result


def test_existing_rules_text_skips_missing_fields(tmp_path):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "sql-002.yaml").write_text("phase: sql_plan\n")  # no id, no content
    with patch.object(kl, "_RULES_DIR", rules_dir):
        result = kl.existing_rules_text()
    assert result == ""


def test_existing_security_text_includes_id_message(tmp_path):
    sec_dir = tmp_path / "security"
    sec_dir.mkdir()
    (sec_dir / "sec-001.yaml").write_text(
        "id: sec-001\naction: block\nmessage: DDL prohibited\n"
    )
    with patch.object(kl, "_SECURITY_DIR", sec_dir):
        result = kl.existing_security_text()
    assert "- sec-001: DDL prohibited" in result


def test_existing_prompts_text_includes_main_and_optimized(tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "answer.md").write_text("# Answer\nDo X.\n")
    optimized = prompts_dir / "optimized"
    optimized.mkdir()
    (optimized / "2026-05-13-01-answer.md").write_text("## Extra\nShould appear.\n")
    with patch.object(kl, "_PROMPTS_DIR", prompts_dir), \
         patch.object(kl, "_PROMPTS_OPTIMIZED_DIR", optimized):
        result = kl.existing_prompts_text()
    assert "=== answer.md ===" in result
    assert "Do X." in result
    assert "=== optimized/2026-05-13-01-answer.md ===" in result
    assert "Should appear." in result


def test_existing_prompts_text_empty(tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    with patch.object(kl, "_PROMPTS_DIR", prompts_dir), \
         patch.object(kl, "_PROMPTS_OPTIMIZED_DIR", prompts_dir / "optimized"):
        result = kl.existing_prompts_text()
    assert result == ""
