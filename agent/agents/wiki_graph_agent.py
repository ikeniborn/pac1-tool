from __future__ import annotations

import os

from agent.contracts import WikiContext, WikiFeedbackRequest, WikiReadRequest

_WIKI_ENABLED = os.getenv("WIKI_ENABLED", "1") == "1"
_GRAPH_ENABLED = os.getenv("WIKI_GRAPH_ENABLED", "1") == "1"
_GRAPH_TOP_K = int(os.getenv("WIKI_GRAPH_TOP_K", "5"))


class WikiGraphAgent:
    def __init__(
        self,
        wiki_enabled: bool | None = None,
        graph_enabled: bool | None = None,
    ) -> None:
        self._wiki = _WIKI_ENABLED if wiki_enabled is None else wiki_enabled
        self._graph = _GRAPH_ENABLED if graph_enabled is None else graph_enabled

    def read(self, request: WikiReadRequest) -> WikiContext:
        patterns_text = ""
        graph_section = ""
        injected_ids: list[str] = []

        if self._wiki:
            try:
                from agent.wiki import load_wiki_patterns
                patterns_text = load_wiki_patterns(request.task_type) or ""
            except Exception as exc:
                print(f"[wiki-agent] load_wiki_patterns failed ({exc})")

        if self._graph:
            try:
                from agent import wiki_graph
                g = wiki_graph.load_graph()
                if g.nodes:
                    graph_section, injected_ids = wiki_graph.retrieve_relevant_with_ids(
                        g, request.task_type, request.task_text, top_k=_GRAPH_TOP_K,
                    )
            except Exception as exc:
                print(f"[wiki-agent] graph retrieval failed ({exc})")

        return WikiContext(
            patterns_text=patterns_text,
            graph_section=graph_section,
            injected_node_ids=injected_ids,
        )

    def write_feedback(self, request: WikiFeedbackRequest) -> None:
        """Update wiki graph confidence based on execution score. Fail-open."""
        if not self._graph:
            return
        try:
            from agent import wiki_graph
            g = wiki_graph.load_graph()
            node_ids = request.wiki_context.injected_node_ids
            if not node_ids:
                return
            epsilon = float(os.getenv("WIKI_GRAPH_CONFIDENCE_EPSILON", "0.05"))
            if request.score >= 1.0:
                wiki_graph.bump_uses(g, node_ids)
            else:
                wiki_graph.degrade_confidence(g, node_ids, epsilon)
            wiki_graph.save_graph(g)
        except Exception as exc:
            print(f"[wiki-agent] write_feedback failed ({exc})")
