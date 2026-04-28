"""FIX-403: _split_markdown_and_deltas handles non-trailing fence, bare markers, json5."""
from unittest.mock import patch


def _split(response: str) -> tuple:
    with patch("agent.wiki._GRAPH_AUTOBUILD", True):
        from agent.wiki import _split_markdown_and_deltas
        return _split_markdown_and_deltas(response)


def test_fence_at_end_baseline():
    """Existing behaviour: fenced block at end."""
    resp = 'Some markdown text.\n```json\n{"graph_deltas": {"new_insights": []}}\n```'
    markdown, deltas = _split(resp)
    assert "graph_deltas" not in markdown
    assert deltas == {"new_insights": []}


def test_fence_in_middle():
    """FIX-403: fenced block in the middle of response (not at end)."""
    resp = (
        'Intro text.\n'
        '```json\n{"graph_deltas": {"new_rules": [{"text": "use list first"}]}}\n```\n'
        'Trailing paragraph.'
    )
    markdown, deltas = _split(resp)
    assert isinstance(deltas, dict)
    assert "new_rules" in deltas


def test_fence_json5_trailing_comma():
    """FIX-403: json5 fallback for trailing comma inside fenced block."""
    resp = '```json\n{"graph_deltas": {"new_insights": [],},}\n```'
    markdown, deltas = _split(resp)
    assert isinstance(deltas, dict)


def test_bare_graph_deltas_marker():
    """FIX-403: no fence, just graph_deltas: {...} in text."""
    resp = 'Some synthesis.\ngraph_deltas: {"new_insights": [{"text": "tip"}]}'
    markdown, deltas = _split(resp)
    assert isinstance(deltas, dict)
    assert "new_insights" in deltas


def test_invalid_json_fail_open():
    """Malformed JSON → fail-open: returns original response and empty dict."""
    resp = '```json\n{totally invalid{{{\n```'
    markdown, deltas = _split(resp)
    assert deltas == {}
    assert markdown == resp


def test_no_fence_fail_open():
    """No fence at all → fail-open."""
    resp = "Just plain text, no JSON block."
    markdown, deltas = _split(resp)
    assert deltas == {}
    assert markdown == resp
