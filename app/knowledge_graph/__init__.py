"""Knowledge-graph package (mock now; Neo4j later)."""

from knowledge_graph.base import BotanicalKnowledgeGraph
from knowledge_graph.factory import get_knowledge_graph
from knowledge_graph.mock import MockBotanicalKnowledgeGraph, get_mock_botanical_kg

__all__ = [
    "BotanicalKnowledgeGraph",
    "MockBotanicalKnowledgeGraph",
    "get_knowledge_graph",
    "get_mock_botanical_kg",
]
