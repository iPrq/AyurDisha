"""Tests for Botanical Normalizer + mock KG (no paid API)."""

from __future__ import annotations

from graph.models import BotanicalResult, BotanicalStatus
from graph.shared.botanical import botanical_normalizer_node, normalize_botanical
from knowledge_graph.mock import MockBotanicalKnowledgeGraph, get_mock_botanical_kg


def test_mock_kg_ashwagandha_resolves_to_withania():
    kg = get_mock_botanical_kg()
    hits = kg.lookup("Ashwagandha")
    assert len(hits) == 1
    assert hits[0].botanical_name == "Withania somnifera"
    assert "withanolides" in hits[0].phytochemicals


def test_normalize_ashwagandha_resolved():
    result = normalize_botanical("Ashwagandha")
    assert result.status == BotanicalStatus.RESOLVED
    assert result.botanical_name == "Withania somnifera"
    assert result.confidence >= 0.7
    assert "Ashwagandha" in result.synonyms
    assert result.candidates == []


def test_normalize_scientific_name():
    result = normalize_botanical("Withania somnifera")
    assert result.status == BotanicalStatus.RESOLVED
    assert result.botanical_name == "Withania somnifera"


def test_normalize_ambiguous_ginseng_does_not_pick():
    result = normalize_botanical("ginseng")
    assert result.status == BotanicalStatus.AMBIGUOUS
    assert result.botanical_name is None
    assert len(result.candidates) >= 2
    names = {c.botanical_name for c in result.candidates}
    assert "Panax ginseng" in names
    assert "Withania somnifera" in names


def test_normalize_ambiguous_fixture_term():
    result = normalize_botanical("ambiguous_herb")
    assert result.status == BotanicalStatus.AMBIGUOUS
    assert result.botanical_name is None


def test_normalize_unknown_without_llm_unresolved():
    result = normalize_botanical("CompletelyUnknownPlantXYZ")
    assert result.status == BotanicalStatus.UNRESOLVED
    assert result.botanical_name is None
    assert result.confidence == 0.0


def test_normalize_unknown_with_injectable_llm():
    def fake_llm(schema, system, user):
        return BotanicalResult(
            status=BotanicalStatus.RESOLVED,
            input_term="CompletelyUnknownPlantXYZ",
            botanical_name="Fakeus plantus",
            synonyms=["CompletelyUnknownPlantXYZ"],
            phytochemicals=[],
            confidence=0.8,
            notes="injected mock llm",
        )

    result = normalize_botanical("CompletelyUnknownPlantXYZ", llm=fake_llm)
    assert result.status == BotanicalStatus.RESOLVED
    assert result.botanical_name == "Fakeus plantus"


def test_node_writes_state_from_ingredients():
    state = {
        "product": "Stress tonic",
        "ingredients": ["Ashwagandha"],
        "language": "en",
        "jurisdiction": "india",
        "legal_scope": "domestic",
    }
    update = botanical_normalizer_node(state)  # type: ignore[arg-type]
    assert update["botanical_name"] == "Withania somnifera"
    assert update["botanical_status"] == BotanicalStatus.RESOLVED.value
    assert update["botanical"].status == BotanicalStatus.RESOLVED
    assert "withanolides" in update["phytochemicals"]


def test_node_ambiguous_sets_human_review():
    state = {
        "product": "Ginseng blend",
        "ingredients": ["ginseng"],
        "language": "en",
        "jurisdiction": "india",
        "legal_scope": "domestic",
    }
    update = botanical_normalizer_node(state)  # type: ignore[arg-type]
    assert update["botanical_status"] == BotanicalStatus.AMBIGUOUS.value
    assert "botanical_name" not in update
    assert "ambiguous_botanical" in update["escalation_reasons"]
    assert update["verification_status"] == "HUMAN_REVIEW_REQUIRED"


def test_custom_kg_injection():
    from graph.models import BotanicalCandidate

    kg = MockBotanicalKnowledgeGraph(
        extra={
            "neem": [
                BotanicalCandidate(
                    botanical_name="Azadirachta indica",
                    synonyms=["Neem"],
                    phytochemicals=["azadirachtin"],
                    confidence=0.9,
                )
            ]
        }
    )
    result = normalize_botanical("Neem", kg=kg)
    assert result.status == BotanicalStatus.RESOLVED
    assert result.botanical_name == "Azadirachta indica"
