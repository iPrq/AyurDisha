"""In-memory botanical KG fixtures (not a live Neo4j connection)."""

from __future__ import annotations

from graph.models import BotanicalCandidate


# Fixture entities — clearly test data, not a live taxonomic database.
_ASHWAGANDHA = BotanicalCandidate(
    botanical_name="Withania somnifera",
    synonyms=[
        "Ashwagandha",
        "Withania somnifera",
        "Indian ginseng",
        "Winter cherry",
    ],
    phytochemicals=["withanolides", "withaferin A", "alkaloids"],
    confidence=0.95,
)

_TURMERIC = BotanicalCandidate(
    botanical_name="Curcuma longa",
    synonyms=["Turmeric", "Curcuma longa", "Haldi"],
    phytochemicals=["curcumin", "demethoxycurcumin"],
    confidence=0.93,
)

# Ambiguous vernacular used only in tests / demos.
_AMBIGUOUS_GINSENG_CANDIDATES = [
    BotanicalCandidate(
        botanical_name="Panax ginseng",
        synonyms=["ginseng", "Korean ginseng", "Panax ginseng"],
        phytochemicals=["ginsenosides"],
        confidence=0.55,
    ),
    BotanicalCandidate(
        botanical_name="Withania somnifera",
        synonyms=["ginseng", "Indian ginseng", "Ashwagandha"],
        phytochemicals=["withanolides"],
        confidence=0.50,
    ),
    BotanicalCandidate(
        botanical_name="Eleutherococcus senticosus",
        synonyms=["ginseng", "Siberian ginseng", "eleuthero"],
        phytochemicals=["eleutherosides"],
        confidence=0.48,
    ),
]

# Canonical lookup keys → candidates (single or multi).
_LOOKUP: dict[str, list[BotanicalCandidate]] = {
    "ashwagandha": [_ASHWAGANDHA],
    "withania somnifera": [_ASHWAGANDHA],
    "indian ginseng": [_ASHWAGANDHA],
    "winter cherry": [_ASHWAGANDHA],
    "turmeric": [_TURMERIC],
    "curcuma longa": [_TURMERIC],
    "haldi": [_TURMERIC],
    # Ambiguous fixture term — never resolve silently.
    "ginseng": list(_AMBIGUOUS_GINSENG_CANDIDATES),
    "ambiguous_herb": list(_AMBIGUOUS_GINSENG_CANDIDATES),
}


def _normalize_term(term: str) -> str:
    return " ".join(term.strip().lower().split())


class MockBotanicalKnowledgeGraph:
    """Fixture-backed botanical lookup. Not connected to Neo4j."""

    def __init__(self, extra: dict[str, list[BotanicalCandidate]] | None = None) -> None:
        self._data = dict(_LOOKUP)
        if extra:
            for key, value in extra.items():
                self._data[_normalize_term(key)] = value

    def lookup(self, term: str) -> list[BotanicalCandidate]:
        if not term or not term.strip():
            return []
        return list(self._data.get(_normalize_term(term), []))


def get_mock_botanical_kg() -> MockBotanicalKnowledgeGraph:
    """Factory for the default mock KG."""
    return MockBotanicalKnowledgeGraph()
