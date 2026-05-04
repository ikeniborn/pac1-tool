"""Tests for explicit vault date extraction in prephase (FIX-400)."""
import re


def _extract_explicit_vault_date(agents_md_content: str) -> str:
    """Replicate the FIX-400 AGENTS.MD extraction logic."""
    for line in agents_md_content.splitlines():
        m = re.match(r"(?:VAULT_DATE|today)\s*:\s*(\d{4}-\d{2}-\d{2})", line, re.IGNORECASE)
        if m:
            return m.group(1)
    return ""


def test_agents_md_vault_date_field():
    """AGENTS.MD with VAULT_DATE: 2026-03-17 → extracted correctly."""
    content = "# Vault\nVAULT_DATE: 2026-03-17\nOther content"
    assert _extract_explicit_vault_date(content) == "2026-03-17"


def test_agents_md_today_field():
    """AGENTS.MD with today: 2026-03-20 → extracted correctly."""
    content = "# Vault\ntoday: 2026-03-20\nfolders below"
    assert _extract_explicit_vault_date(content) == "2026-03-20"


def test_agents_md_no_date_field():
    """AGENTS.MD without date field → empty string returned."""
    content = "# Vault\nContacts: /contacts/\nOutbox: /outbox/"
    assert _extract_explicit_vault_date(content) == ""


def test_agents_md_date_in_middle_of_line_not_matched():
    """Date buried in prose is not matched — only key: value at line start."""
    content = "# Info\nCreated on 2026-03-17 by admin"
    assert _extract_explicit_vault_date(content) == ""


def test_temporal_prompt_has_task_context_warning():
    """_TEMPORAL prompt must warn that TASK CONTEXT date is system clock, not vault date."""
    from agent.prompt import _TEMPORAL
    assert "TASK CONTEXT" in _TEMPORAL
    assert "system" in _TEMPORAL.lower() or "clock" in _TEMPORAL.lower()


def test_temporal_prompt_has_triangulation():
    """FIX-430: _TEMPORAL must contain multi-signal ESTIMATED_TODAY triangulation logic."""
    from agent.prompt import _TEMPORAL
    assert "TRIANGULATE" in _TEMPORAL
    assert "MEDIAN" in _TEMPORAL
    assert "VAULT_DATE + 10" in _TEMPORAL
