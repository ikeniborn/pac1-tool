import agent.json_extract as je


def test_normalize_parsed_removed():
    assert not hasattr(je, "_normalize_parsed"), "_normalize_parsed should be removed"


def test_extract_json_fenced_block():
    text = '```json\n{"reasoning": "test", "queries": ["SELECT 1"]}\n```'
    result = je._extract_json_from_text(text)
    assert result == {"reasoning": "test", "queries": ["SELECT 1"]}


def test_extract_json_plain_object():
    text = 'Some text {"queries": ["SELECT COUNT(*) FROM products"]} more text'
    result = je._extract_json_from_text(text)
    assert result is not None
    assert "queries" in result


def test_extract_json_mutation_preferred():
    text = '{"tool": "read", "path": "/x"} {"tool": "write", "path": "/y", "content": "z"}'
    result = je._extract_json_from_text(text)
    assert result is not None
    assert result.get("tool") == "write"


def test_extract_json_returns_none_for_no_json():
    result = je._extract_json_from_text("no json here at all")
    assert result is None
