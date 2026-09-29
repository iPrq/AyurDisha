"""Knowledge-graph factory: Neo4j-backed botanical lookup when configured, fixtures otherwise."""

from __future__ import annotations

from config import Settings, get_settings
from knowledge_graph.base import BotanicalKnowledgeGraph
from knowledge_graph.mock import get_mock_botanical_kg


def get_knowledge_graph(settings: Settings | None = None) -> BotanicalKnowledgeGraph:
    cfg = settings or get_settings()
    if cfg.kg_backend == "neo4j" and cfg.neo4j_uri:
        from knowledge_graph.service import GraphBotanicalKG, get_graph_store

        return GraphBotanicalKG(get_graph_store(cfg), get_mock_botanical_kg())
    return get_mock_botanical_kg()
