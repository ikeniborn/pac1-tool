import os


def test_read_returns_wiki_context_type():
    from agent.agents.wiki_graph_agent import WikiGraphAgent
    from agent.contracts import WikiContext, WikiReadRequest
    agent = WikiGraphAgent()
    req = WikiReadRequest(task_type="email", task_text="send email to alice")
    result = agent.read(req)
    assert isinstance(result, WikiContext)
    assert isinstance(result.patterns_text, str)
    assert isinstance(result.graph_section, str)
    assert isinstance(result.injected_node_ids, list)


def test_read_disabled_when_wiki_off(monkeypatch):
    monkeypatch.setenv("WIKI_ENABLED", "0")
    monkeypatch.setenv("WIKI_GRAPH_ENABLED", "0")
    from agent.agents.wiki_graph_agent import WikiGraphAgent
    from agent.contracts import WikiReadRequest
    agent = WikiGraphAgent(wiki_enabled=False, graph_enabled=False)
    result = agent.read(WikiReadRequest(task_type="email", task_text="x"))
    assert result.patterns_text == ""
    assert result.graph_section == ""
    assert result.injected_node_ids == []


def test_write_feedback_does_not_raise():
    from agent.agents.wiki_graph_agent import WikiGraphAgent
    from agent.contracts import ExecutionResult, WikiContext, WikiFeedbackRequest
    agent = WikiGraphAgent()
    req = WikiFeedbackRequest(
        task_type="email",
        task_text="send email",
        execution_result=ExecutionResult(
            status="completed",
            outcome="OUTCOME_OK",
            token_stats={},
            step_facts=[],
            injected_node_ids=[],
            rejection_count=0,
        ),
        wiki_context=WikiContext(
            patterns_text="",
            graph_section="",
            injected_node_ids=[],
        ),
        score=1.0,
    )
    agent.write_feedback(req)  # must not raise
