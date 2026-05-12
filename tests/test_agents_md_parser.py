import pytest
from agent.agents_md_parser import parse_agents_md


def test_empty_string_returns_empty_dict():
    assert parse_agents_md("") == {}


def test_no_sections_returns_empty_dict():
    assert parse_agents_md("just some intro text\nno headers") == {}


def test_single_section():
    content = "## Brand Aliases\nheco = Heco\nmaker = Maker GmbH"
    result = parse_agents_md(content)
    assert "brand_aliases" in result
    assert result["brand_aliases"] == ["heco = Heco", "maker = Maker GmbH"]


def test_multiple_sections():
    content = "## Brand Aliases\nheco = Heco\n## Kind Synonyms\nscrew = bolt\nfastener = bolt"
    result = parse_agents_md(content)
    assert set(result.keys()) == {"brand_aliases", "kind_synonyms"}
    assert result["brand_aliases"] == ["heco = Heco"]
    assert result["kind_synonyms"] == ["screw = bolt", "fastener = bolt"]


def test_section_name_lowercased_and_underscored():
    content = "## Folder Roles\nsome/path = archive"
    result = parse_agents_md(content)
    assert "folder_roles" in result


def test_leading_content_before_first_section_ignored():
    content = "# Top-level heading\nIntro text\n## Brand Aliases\nheco = Heco"
    result = parse_agents_md(content)
    assert list(result.keys()) == ["brand_aliases"]


def test_empty_section_has_empty_lines():
    content = "## Brand Aliases\n## Kind Synonyms\nscrew = bolt"
    result = parse_agents_md(content)
    assert result["brand_aliases"] == []
    assert result["kind_synonyms"] == ["screw = bolt"]


def test_h1_heading_not_treated_as_section():
    content = "# Main Title\n## Brand Aliases\nheco = Heco"
    result = parse_agents_md(content)
    assert "main_title" not in result
    assert "brand_aliases" in result
