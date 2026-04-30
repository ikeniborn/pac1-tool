from agent.task_types import knowledge_aspects, _DEFAULT_ASPECTS, REGISTRY


def test_default_aspects_structure():
    for a in _DEFAULT_ASPECTS:
        assert "id" in a
        assert "header" in a
        assert "prompt" in a


def test_knowledge_aspects_returns_list_for_known_type():
    aspects = knowledge_aspects("email")
    assert isinstance(aspects, list)
    assert len(aspects) >= 1
    assert all("id" in a and "prompt" in a for a in aspects)


def test_knowledge_aspects_falls_back_to_defaults_for_type_without_aspects():
    result = knowledge_aspects("default")
    assert result == _DEFAULT_ASPECTS


def test_knowledge_aspects_falls_back_for_unknown_type():
    result = knowledge_aspects("nonexistent_type_xyz")
    assert result == _DEFAULT_ASPECTS
