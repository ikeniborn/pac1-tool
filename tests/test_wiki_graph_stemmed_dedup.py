# tests/test_wiki_graph_stemmed_dedup.py
"""Block G: error-ingest dedup must catch near-paraphrases via stemming."""


def test_paraphrase_dedup_simple_plural(tmp_path, monkeypatch):
    """'invoice attachment fails' ≈ 'invoices attachments failed' → dedup."""
    monkeypatch.setattr("agent.wiki_graph._GRAPH_PATH", tmp_path / "graph.json")
    from agent import wiki_graph as wg
    g = wg.Graph()
    wg.merge_updates(g, {"antipatterns": [
        {"text": "invoice attachment fails on multipart upload", "tags": ["queue"]}
    ]})
    nodes_before = len(g.nodes)
    wg.merge_updates(g, {"antipatterns": [
        {"text": "invoices attachments failed during multipart uploads", "tags": ["queue"]}
    ]})
    assert len(g.nodes) == nodes_before, "paraphrase should dedup"


def test_paraphrase_dedup_passive_voice(tmp_path, monkeypatch):
    monkeypatch.setattr("agent.wiki_graph._GRAPH_PATH", tmp_path / "graph.json")
    from agent import wiki_graph as wg
    g = wg.Graph()
    wg.merge_updates(g, {"antipatterns": [
        {"text": "agent skips contact lookup before write", "tags": ["email"]}
    ]})
    n0 = len(g.nodes)
    wg.merge_updates(g, {"antipatterns": [
        {"text": "agent skipped contacts lookup before writing", "tags": ["email"]}
    ]})
    assert len(g.nodes) == n0


def test_truly_different_antipatterns_kept(tmp_path, monkeypatch):
    """Different antipatterns must NOT collapse into one."""
    monkeypatch.setattr("agent.wiki_graph._GRAPH_PATH", tmp_path / "graph.json")
    from agent import wiki_graph as wg
    g = wg.Graph()
    wg.merge_updates(g, {"antipatterns": [
        {"text": "agent forgets to read contact before email write", "tags": ["email"]}
    ]})
    wg.merge_updates(g, {"antipatterns": [
        {"text": "OTP token submitted before user issued one", "tags": ["queue"]}
    ]})
    assert len(g.nodes) == 2
