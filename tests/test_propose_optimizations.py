import json
import os
import yaml
import pytest
from pathlib import Path
from unittest.mock import patch

import scripts.propose_optimizations as po


def _write_eval_log(path: Path, entries: list) -> None:
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")


def _eval_entry(rule_opts=None, security_opts=None, prompt_opts=None):
    return {
        "task_text": "Do you have product X with attr Y=3?",
        "cycles": 2,
        "final_outcome": "OUTCOME_NONE_CLARIFICATION",
        "score": 0.1,
        "rule_optimization": rule_opts or [],
        "security_optimization": security_opts or [],
        "prompt_optimization": prompt_opts or [],
    }


def _setup(tmp_path):
    eval_log = tmp_path / "eval_log.jsonl"
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    security_dir = tmp_path / "security"
    security_dir.mkdir()
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    prompts_optimized_dir = prompts_dir / "optimized"
    prompts_optimized_dir.mkdir()
    processed_file = tmp_path / ".eval_optimizations_processed"
    return eval_log, rules_dir, security_dir, prompts_dir, prompts_optimized_dir, processed_file


def _base_patches(eval_log, rules_dir, security_dir, prompts_dir, prompts_optimized_dir, processed_file):
    return [
        patch.object(po, "_EVAL_LOG", eval_log),
        patch.object(po, "_RULES_DIR", rules_dir),
        patch.object(po, "_SECURITY_DIR", security_dir),
        patch.object(po, "_PROMPTS_DIR", prompts_dir),
        patch.object(po, "_PROMPTS_OPTIMIZED_DIR", prompts_optimized_dir),
        patch.object(po, "_PROCESSED_FILE", processed_file),
        patch.object(po, "_load_model_cfg", return_value={}),
        patch.object(po, "load_dotenv"),
        patch.dict(os.environ, {"MODEL_EVALUATOR": "test-model"}),
    ]


def test_writes_rule_yaml(tmp_path):
    eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed = _setup(tmp_path)
    _write_eval_log(eval_log, [_eval_entry(rule_opts=["Never prefix model with brand."])])

    patches = _base_patches(eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed)
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], patches[8], \
         patch.object(po, "_synthesize_rule", return_value="Never prefix model with brand."), \
         patch.object(po, "_synthesize_security_gate", return_value=None), \
         patch.object(po, "_synthesize_prompt_patch", return_value=None):
        po.main(dry_run=False)

    files = list(rules_dir.glob("*.yaml"))
    assert len(files) == 1
    rule = yaml.safe_load(files[0].read_text())
    assert rule["verified"] is False
    assert rule["source"] == "eval"
    assert rule["phase"] == "sql_plan"
    assert "Never prefix model" in rule["content"]
    assert rule["eval_score"] == pytest.approx(0.1)


def test_writes_security_yaml(tmp_path):
    eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed = _setup(tmp_path)
    _write_eval_log(eval_log, [_eval_entry(security_opts=["Add gate for UNION SELECT"])])

    gate_spec = {"pattern": "UNION.*SELECT", "check": None, "message": "UNION SELECT prohibited"}
    patches = _base_patches(eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed)
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], patches[8], \
         patch.object(po, "_synthesize_rule", return_value=None), \
         patch.object(po, "_synthesize_security_gate", return_value=gate_spec), \
         patch.object(po, "_synthesize_prompt_patch", return_value=None):
        po.main(dry_run=False)

    files = list(security_dir.glob("*.yaml"))
    assert len(files) == 1
    gate = yaml.safe_load(files[0].read_text())
    assert gate["verified"] is False
    assert gate["source"] == "eval"
    assert gate["action"] == "block"
    assert gate["pattern"] == "UNION.*SELECT"
    assert "check" not in gate


def test_writes_prompt_md(tmp_path):
    eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed = _setup(tmp_path)
    _write_eval_log(eval_log, [_eval_entry(prompt_opts=["answer.md: add rule for empty grounding_refs"])])

    patch_result = {"target_file": "answer.md", "content": "## Grounding guard\nNever emit empty grounding_refs."}
    patches = _base_patches(eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed)
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], patches[8], \
         patch.object(po, "_synthesize_rule", return_value=None), \
         patch.object(po, "_synthesize_security_gate", return_value=None), \
         patch.object(po, "_synthesize_prompt_patch", return_value=patch_result):
        po.main(dry_run=False)

    files = list(prom_dir.glob("*.md"))
    assert len(files) == 1
    text = files[0].read_text()
    assert "answer.md" in text
    assert "Never emit empty grounding_refs" in text


def test_dry_run_writes_nothing(tmp_path):
    eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed = _setup(tmp_path)
    _write_eval_log(eval_log, [_eval_entry(
        rule_opts=["r"], security_opts=["s"], prompt_opts=["p"]
    )])

    gate_spec = {"pattern": "DROP", "check": None, "message": "no drop"}
    patch_result = {"target_file": "sql_plan.md", "content": "## X\nDo X."}
    patches = _base_patches(eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed)
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], patches[8], \
         patch.object(po, "_synthesize_rule", return_value="Never X."), \
         patch.object(po, "_synthesize_security_gate", return_value=gate_spec), \
         patch.object(po, "_synthesize_prompt_patch", return_value=patch_result):
        po.main(dry_run=True)

    assert list(rules_dir.glob("*.yaml")) == []
    assert list(security_dir.glob("*.yaml")) == []
    assert list(prom_dir.glob("*.md")) == []
    assert not processed.exists()


def test_dedup_skips_processed(tmp_path):
    eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed = _setup(tmp_path)
    rec = "Never prefix model."
    entry = _eval_entry(rule_opts=[rec])
    _write_eval_log(eval_log, [entry])
    h = po._entry_hash(entry["task_text"], "rule", rec)
    processed.write_text(h + "\n")

    patches = _base_patches(eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed)
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], patches[8], \
         patch.object(po, "_synthesize_rule", return_value="Never X.") as mock_synth, \
         patch.object(po, "_synthesize_security_gate", return_value=None), \
         patch.object(po, "_synthesize_prompt_patch", return_value=None):
        po.main(dry_run=False)

    mock_synth.assert_not_called()


def test_missing_model_evaluator_exits(tmp_path):
    eval_log, _rules_dir, _security_dir, _prompts_dir, prom_dir, processed = _setup(tmp_path)
    _write_eval_log(eval_log, [_eval_entry(rule_opts=["x"])])

    with patch.object(po, "_EVAL_LOG", eval_log), \
         patch.object(po, "load_dotenv"), \
         patch.dict(os.environ):
        os.environ.pop("MODEL_EVALUATOR", None)
        with pytest.raises(SystemExit):
            po.main()


def test_existing_security_text_returns_id_message(tmp_path):
    import agent.knowledge_loader as kl
    sec_dir = tmp_path / "security"
    sec_dir.mkdir()
    (sec_dir / "sec-001.yaml").write_text(
        "id: sec-001\naction: block\nmessage: DDL prohibited\n"
    )
    (sec_dir / "sec-002.yaml").write_text(
        "id: sec-002\ncheck: no_where_clause\naction: block\nmessage: Full scan prohibited\n"
    )
    with patch.object(kl, "_SECURITY_DIR", sec_dir):
        result = kl.existing_security_text()
    assert "sec-001: DDL prohibited" in result
    assert "sec-002: Full scan prohibited" in result


def test_existing_security_text_skips_invalid(tmp_path):
    import agent.knowledge_loader as kl
    sec_dir = tmp_path / "security"
    sec_dir.mkdir()
    (sec_dir / "bad.yaml").write_text("not: valid: yaml: [")
    (sec_dir / "no-msg.yaml").write_text("id: sec-003\naction: block\n")
    with patch.object(kl, "_SECURITY_DIR", sec_dir):
        result = kl.existing_security_text()
    assert result == ""


def test_existing_prompts_text_returns_full_content(tmp_path):
    import agent.knowledge_loader as kl
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "answer.md").write_text("# Answer\n\nDo X.\n")
    (prompts_dir / "sql_plan.md").write_text("# SQL Plan\n\nDo Y.\n")
    optimized_dir = prompts_dir / "optimized"
    optimized_dir.mkdir()
    (optimized_dir / "2026-05-12-01-answer.md").write_text("## Extra\nShould appear.\n")
    with patch.object(kl, "_PROMPTS_DIR", prompts_dir), \
         patch.object(kl, "_PROMPTS_OPTIMIZED_DIR", optimized_dir):
        result = kl.existing_prompts_text()
    assert "=== answer.md ===" in result
    assert "Do X." in result
    assert "=== sql_plan.md ===" in result
    assert "Do Y." in result
    assert "Should appear." in result


def test_existing_prompts_text_empty_dir(tmp_path):
    import agent.knowledge_loader as kl
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    with patch.object(kl, "_PROMPTS_DIR", prompts_dir), \
         patch.object(kl, "_PROMPTS_OPTIMIZED_DIR", prompts_dir / "optimized"):
        result = kl.existing_prompts_text()
    assert result == ""


def test_synthesize_security_gate_receives_existing_context(tmp_path):
    import agent.knowledge_loader as kl
    eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed = _setup(tmp_path)
    _write_eval_log(eval_log, [_eval_entry(security_opts=["Add gate for UNION SELECT"])])

    gate_spec = {"pattern": "UNION.*SELECT", "check": None, "message": "UNION SELECT prohibited"}
    patches = _base_patches(eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed)
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], patches[8], \
         patch.object(po, "_synthesize_rule", return_value=None), \
         patch.object(po, "_synthesize_security_gate", return_value=gate_spec) as mock_sec, \
         patch.object(po, "_synthesize_prompt_patch", return_value=None), \
         patch.object(kl, "existing_security_text", return_value="- sec-001: DDL prohibited"):
        po.main(dry_run=False)

    args = mock_sec.call_args
    assert args[0][1] == "- sec-001: DDL prohibited"


def test_synthesize_prompt_patch_receives_existing_context(tmp_path):
    import agent.knowledge_loader as kl
    eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed = _setup(tmp_path)
    _write_eval_log(eval_log, [_eval_entry(prompt_opts=["answer.md: add grounding rule"])])

    patch_result = {"target_file": "answer.md", "content": "## Guard\nNever X."}
    patches = _base_patches(eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed)
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], patches[8], \
         patch.object(po, "_synthesize_rule", return_value=None), \
         patch.object(po, "_synthesize_security_gate", return_value=None), \
         patch.object(po, "_synthesize_prompt_patch", return_value=patch_result) as mock_prompt, \
         patch.object(kl, "existing_prompts_text", return_value="=== answer.md ===\n# Answer\n"):
        po.main(dry_run=False)

    args = mock_prompt.call_args
    assert args[0][1] == "=== answer.md ===\n# Answer\n"


def test_main_uses_knowledge_loader_for_rules(tmp_path):
    """Ensure propose_optimizations imports rules text from knowledge_loader, not its own helper."""
    import agent.knowledge_loader as kl
    eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed = _setup(tmp_path)
    _write_eval_log(eval_log, [_eval_entry(rule_opts=["Never X."])])

    patches = _base_patches(eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed)
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], patches[8], \
         patch.object(kl, "existing_rules_text", return_value="- sql-001: existing rule") as mock_kl, \
         patch.object(po, "_synthesize_rule", return_value="Never X.") as mock_synth, \
         patch.object(po, "_synthesize_security_gate", return_value=None), \
         patch.object(po, "_synthesize_prompt_patch", return_value=None):
        po.main(dry_run=False)

    # synthesize_rule must be called with the string returned by knowledge_loader
    args = mock_synth.call_args
    assert args[0][1] == "- sql-001: existing rule"
