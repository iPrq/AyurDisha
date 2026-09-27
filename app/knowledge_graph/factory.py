"""Knowledge-graph factory (mock only for now; Neo4j later)."""

from __future__ import annotations

from config import Settings
from knowledge_graph.base import BotanicalKnowledgeGraph
from knowledge_graph.mock import get_mock_botanical_kg


def get_knowledge_graph(settings: Settings | None = None) -> BotanicalKnowledgeGraph:
    return get_mock_botanical_kg()
