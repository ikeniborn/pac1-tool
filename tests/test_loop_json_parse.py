"""Tests for CC-tier JSON parse pre-stripping (FIX-397)."""


def _strip_to_json_object(text: str) -> str:
    """Extract substring from first '{' to last balanced '}' — mirrors FIX-397 logic."""
    start = text.find("{")
    if start == -1:
        return text
    depth = 0
    in_string = False
    escape_next = False
    end = start
    for i, ch in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    return text[start:end + 1]


def test_strip_trailing_text():
    """JSON object followed by explanation text is trimmed correctly."""
    raw = '{"tool": "read", "path": "/foo"}\nSome trailing explanation here.'
    result = _strip_to_json_object(raw)
    assert result == '{"tool": "read", "path": "/foo"}'


def test_strip_nested_object():
    """Nested objects are handled correctly."""
    raw = '{"a": {"b": 1}}\nextra'
    result = _strip_to_json_object(raw)
    assert result == '{"a": {"b": 1}}'


def test_no_trailing_text():
    """Clean JSON is returned unchanged."""
    raw = '{"tool": "write"}'
    assert _strip_to_json_object(raw) == raw


def test_preamble_text_stripped():
    """Text before { is stripped too."""
    raw = 'Here is the result: {"x": 1} done.'
    result = _strip_to_json_object(raw)
    assert result == '{"x": 1}'


def test_json_parse_with_trailing_text():
    """JSON parse fails with trailing text, succeeds after stripping — simulates FIX-397 effect."""
    import json

    # Simulate what trailing text would break — a valid JSON that becomes invalid
    # when trailing text is appended
    trailing_raw = (
        '{"current_state":"searching contacts","plan_remaining_steps_brief":["write outbox"],'
        '"done_operations":[],"task_completed":false,'
        '"function":{"tool":"search","pattern":"maya","root":"/contacts","limit":10}}'
        "\nI chose search because the contact may not exist."
    )

    # Without stripping — should fail JSON parse
    try:
        json.loads(trailing_raw)
        parse_failed = False
    except (json.JSONDecodeError, ValueError):
        parse_failed = True
    assert parse_failed, "Expected parse to fail on trailing text"

    # With stripping — should succeed
    clean = _strip_to_json_object(trailing_raw)
    parsed = json.loads(clean)
    assert parsed is not None
    assert parsed.get("task_completed") is False
