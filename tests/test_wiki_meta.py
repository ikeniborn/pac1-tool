import pytest


def _load():
    from agent.wiki import (
        _read_page_meta_from_content,
        _write_page_meta,
        _parse_page_sections,
        _page_quality,
    )
    return _read_page_meta_from_content, _write_page_meta, _parse_page_sections, _page_quality


# --- _page_quality ---

def test_quality_nascent():
    _, _, _, _page_quality = _load()
    assert _page_quality(0) == "nascent"
    assert _page_quality(4) == "nascent"


def test_quality_developing():
    _, _, _, _page_quality = _load()
    assert _page_quality(5) == "developing"
    assert _page_quality(14) == "developing"


def test_quality_mature():
    _, _, _, _page_quality = _load()
    assert _page_quality(15) == "mature"
    assert _page_quality(100) == "mature"


# --- _write_page_meta ---

def test_write_page_meta_basic():
    _, _write_page_meta, _, _ = _load()
    meta = {
        "category": "email",
        "quality": "nascent",
        "fragment_count": 3,
        "fragment_ids": ["t01_20260101T120000Z", "t02_20260102T130000Z"],
        "last_synthesized": "2026-04-30",
        "aspects_covered": "workflow_steps,pitfalls",
    }
    result = _write_page_meta(meta)
    assert result.startswith("<!-- wiki:meta")
    assert "category: email" in result
    assert "quality: nascent" in result
    assert "fragment_count: 3" in result
    assert "t01_20260101T120000Z" in result
    assert result.strip().endswith("-->")


def test_write_page_meta_empty_ids():
    _, _write_page_meta, _, _ = _load()
    meta = {"category": "crm", "quality": "nascent", "fragment_count": 0,
            "fragment_ids": [], "last_synthesized": "2026-04-30", "aspects_covered": ""}
    result = _write_page_meta(meta)
    assert "fragment_ids: []" in result


# --- _read_page_meta_from_content ---

def test_read_page_meta_roundtrip():
    _read_page_meta_from_content, _write_page_meta, _, _ = _load()
    meta_in = {
        "category": "email",
        "quality": "developing",
        "fragment_count": 7,
        "fragment_ids": ["t01_abc", "t02_def"],
        "last_synthesized": "2026-04-30",
        "aspects_covered": "workflow_steps,pitfalls,shortcuts",
    }
    header = _write_page_meta(meta_in)
    page_content = header + "\n\n## Workflow steps\nsome content\n"
    meta_out = _read_page_meta_from_content(page_content)
    assert meta_out["quality"] == "developing"
    assert meta_out["fragment_count"] == 7
    assert "t01_abc" in meta_out["fragment_ids"]
    assert "t02_def" in meta_out["fragment_ids"]


def test_read_page_meta_missing_header_returns_defaults():
    _read_page_meta_from_content, _, _, _ = _load()
    content = "## Workflow steps\nsome content without meta header\n"
    meta = _read_page_meta_from_content(content)
    assert meta["quality"] == "nascent"
    assert meta["fragment_count"] == 0
    assert meta["fragment_ids"] == []


def test_read_page_meta_empty_content():
    _read_page_meta_from_content, _, _, _ = _load()
    meta = _read_page_meta_from_content("")
    assert meta["quality"] == "nascent"
    assert meta["fragment_count"] == 0
    assert meta["fragment_ids"] == []


# --- _parse_page_sections ---

def test_parse_page_sections_basic():
    _, _, _parse_page_sections, _ = _load()
    content = """<!-- wiki:meta
category: email
quality: nascent
fragment_count: 0
fragment_ids: []
last_synthesized: 2026-04-30
aspects_covered:
-->

## Workflow steps
Step 1: do this.
Step 2: do that.

## Key pitfalls
- Avoid X.
"""
    sections = _parse_page_sections(content)
    assert "workflow_steps" in sections
    assert "key_pitfalls" in sections
    assert "Step 1: do this." in sections["workflow_steps"]
    assert "Avoid X." in sections["key_pitfalls"]


def test_parse_page_sections_no_meta():
    _, _, _parse_page_sections, _ = _load()
    content = "## Shortcuts\nUse find before read.\n\n## Key pitfalls\nDon't guess.\n"
    sections = _parse_page_sections(content)
    assert "shortcuts" in sections
    assert "key_pitfalls" in sections


def test_parse_page_sections_empty():
    _, _, _parse_page_sections, _ = _load()
    assert _parse_page_sections("") == {}
    assert _parse_page_sections("<!-- wiki:meta\n-->") == {}
