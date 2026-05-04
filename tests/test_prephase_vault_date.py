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


def test_temporal_prompt_no_domain_knowledge():
    """FIX-434: temporal type uses _CORE + _LOOKUP only — no hardcoded domain formulas."""
    from agent.prompt import build_system_prompt
    p = build_system_prompt("temporal")
    # Domain formulas removed from system prompt (now accumulated in graph/wiki)
    assert "TRIANGULATE" not in p
    assert "MEDIAN" not in p
    assert "PAC1 rule" not in p
    assert "TOTAL_DAYS" not in p


def test_crm_prompt_no_domain_knowledge():
    """FIX-434: crm type uses _CORE + _LOOKUP only — no hardcoded CRM step formulas."""
    from agent.prompt import build_system_prompt
    p = build_system_prompt("crm")
    assert "PAC1 rule" not in p
    assert "TOTAL_DAYS" not in p
