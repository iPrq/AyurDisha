"""Knowledge-graph interfaces for botanical / entity lookup."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from graph.models import BotanicalCandidate


@runtime_checkable
class BotanicalKnowledgeGraph(Protocol):
    """Lookup botanical entities. Real Neo4j client comes later."""

    def lookup(self, term: str) -> list[BotanicalCandidate]:
        """Return zero, one, or many candidates for ``term``.

        - Exactly one high-confidence match → caller may resolve.
        - Multiple candidates → ambiguous; caller must not pick silently.
        - Empty → unknown / unresolved.
        """
        ...
