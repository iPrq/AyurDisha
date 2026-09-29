"""Knowledge graph: seed / response builders, in-memory store, botanical lookup, API."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from graph.models import (
    BotanicalCandidate,
    BotanicalResult,
    BotanicalStatus,
    LegalScope,
    ProductReviewResponse,
    RetrievedSource,
)
from knowledge_graph import service
from knowledge_graph.builders import build_response_batch, build_seed_batch, parse_classical_formulary
from knowledge_graph.mock import get_mock_botanical_kg
from knowledge_graph.schema import FORMULATION, HERB, INGREDIENT, SOURCE, node_key
from knowledge_graph.service import GraphBotanicalKG
from knowledge_graph.store import InMemoryGraphStore

_BKK_SAMPLE = """Triphala Churna (Churna)

Category: Digestive System
Main ingredients: Haritaki, Bibhitaki, Amalaki
Ingredients: Haritaki (Terminalia chebula), Bibhitaki (Terminalia bellirica), Amalaki (Emblica officinalis) in equal parts.
Reference: Bhavaprakasha
Indications: Mild laxative (Anulomana).
Dosage: 3-6 grams

Arjunarishta (Arishta)

Category: Cardiovascular System
Main ingredients: Arjuna, Draksha
Ingredients: Arjuna (Terminalia arjuna) bark, Draksha and Dhataki.
Reference: Bhaishajya Ratnavali
Indications: Cardiac tonic.
"""


def _seeded_store() -> InMemoryGraphStore:
    store = InMemoryGraphStore()
    store.merge_batch(build_seed_batch(), origin="curated")
    return store


def test_seed_lookup_matches_fixture_semantics() -> None:
    store = _seeded_store()
    [turmeric] = store.lookup_botanical("Haldi")
    assert turmeric.botanical_name == "Curcuma longa"
    assert "curcumin" in turmeric.phytochemicals
    assert turmeric.confidence >= 0.9
    ginseng = {c.botanical_name for c in store.lookup_botanical("ginseng")}
    assert ginseng == {"Panax ginseng", "Withania somnifera", "Eleutherococcus senticosus"}
    assert store.lookup_botanical("unknown herb") == []


def test_classical_formulary_links_existing_and_new_entities() -> None:
    seed = build_seed_batch()
    batch = parse_classical_formulary(_BKK_SAMPLE, seed, doc_title="BKK")
    triphala = node_key(FORMULATION, "Triphala")
    edges = {(e.source, e.target) for e in batch.edges.values()}
    assert (node_key(HERB, "Phyllanthus emblica"), triphala) in edges
    assert (node_key(HERB, "Terminalia arjuna"), node_key(FORMULATION, "Arjunarishta")) in edges
    assert (node_key(INGREDIENT, "Draksha"), node_key(FORMULATION, "Arjunarishta")) in edges


def test_pipeline_origin_never_downgrades_curated() -> None:
    store = _seeded_store()
    response = ProductReviewResponse(
        product="Calm Caps",
        ingredients=["Ashwagandha"],
        language="en",
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
        botanicals=[
            BotanicalResult(
                status=BotanicalStatus.RESOLVED,
                input_term="Ashwagandha",
                botanical_name="Withania somnifera",
                synonyms=["Ashwagandha"],
                phytochemicals=["withanolides"],
                confidence=0.9,
            ),
            BotanicalResult(
                status=BotanicalStatus.AMBIGUOUS,
                input_term="Brahmi-like herb",
                candidates=[BotanicalCandidate(botanical_name="Bacopa monnieri", confidence=0.5)],
            ),
        ],
        retrieved_sources=[
            RetrievedSource(id="s1", title="API monograph", text="Withania somnifera root is used in Triphala blends."),
            RetrievedSource(id="s2", title="Unrelated", text="Section 3(d) of the Patents Act."),
        ],
    )
    vocab = {"triphala": {node_key(FORMULATION, "Triphala")}}
    store.merge_batch(build_response_batch(response, feature="product_review", vocabulary=vocab), origin="pipeline")

    herb = store.resolve("Withania somnifera")
    assert herb is not None and herb.props["origin"] == "curated"
    view = store.neighborhood(node_key(SOURCE, "s1"))
    assert view is not None
    linked = {n.key for n in view.nodes}
    assert node_key(HERB, "Withania somnifera") in linked
    assert node_key(FORMULATION, "Triphala") in linked
    s2 = store.neighborhood(node_key(SOURCE, "s2"))
    assert s2 is not None and {n.label for n in s2.nodes} == {"Source", "Product"}


def test_graph_botanical_kg_falls_back_to_fixtures() -> None:
    kg = GraphBotanicalKG(InMemoryGraphStore(), get_mock_botanical_kg())
    [hit] = kg.lookup("Ashwagandha")
    assert hit.botanical_name == "Withania somnifera"


def test_kg_api(monkeypatch) -> None:
    from api.knowledge_graph import router

    monkeypatch.setattr(service, "_store", _seeded_store())
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    res = client.get("/api/v1/kg/entity", params={"q": "Amla", "depth": 2})
    assert res.status_code == 200
    body = res.json()
    assert body["center"] == node_key(HERB, "Phyllanthus emblica")
    labels = {n["label"] for n in body["nodes"]}
    assert {"Herb", "Formulation", "Compound"} <= labels

    assert client.get("/api/v1/kg/entity", params={"q": "nothing-here"}).status_code == 404
    terms = {t["term"] for t in client.get("/api/v1/kg/vocabulary").json()}
    assert {"Tulsi", "Triphala", "curcumin"} <= terms
    assert client.get("/api/v1/kg/search", params={"q": "gugg"}).json()[0]["label"] == "Herb"
