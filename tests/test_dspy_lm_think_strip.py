"""FIX-402: DispatchLM.forward() strips <think>...</think> before DSPy field parser."""
from unittest.mock import patch


def _make_lm():
    from agent.dspy_lm import DispatchLM
    return DispatchLM(model="qwen3.5:cloud", cfg={}, max_tokens=100)


def _forward(lm, completion: str) -> str:
    """Call forward() with a mocked call_llm_raw and return the response content."""
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user"},
    ]
    with patch("agent.dspy_lm.call_llm_raw", return_value=completion):
        resp = lm.forward(messages=messages)
    return resp.choices[0].message.content


def test_think_block_stripped():
    lm = _make_lm()
    result = _forward(lm, '<think>internal reasoning</think>\n{"addendum": "use read first"}')
    assert "<think>" not in result
    assert "addendum" in result


def test_multiline_think_stripped():
    lm = _make_lm()
    result = _forward(lm, "<think>\nline1\nline2\n</think>\n{\"field\": \"value\"}")
    assert "<think>" not in result
    assert "field" in result


def test_no_think_unchanged():
    lm = _make_lm()
    result = _forward(lm, '{"field": "value"}')
    assert result == '{"field": "value"}'


def test_think_only_response_becomes_empty():
    lm = _make_lm()
    result = _forward(lm, "<think>only reasoning, no output</think>")
    assert "<think>" not in result
