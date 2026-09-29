"""API tests for POST /api/v1/patent-advisor (scripted LLM, no paid API)."""

from __future__ import annotations

from fastapi.testclient import TestClient

import api.patent_advisor as patent_api
from graph.patent_advisor_graph import build_patent_advisor_graph
from main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_patent_advisor_domestic(scripted_llm):
    patent_api._graph = build_patent_advisor_graph(llm=scripted_llm)
    try:
        resp = client.post(
            "/api/v1/patent-advisor",
            json={
                "product": "Ashwagandha capsule",
                "ingredients": ["Ashwagandha"],
                "language": "en",
                "jurisdiction": "india",
                "legal_scope": "domestic",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["botanical"]["botanical_name"] == "Withania somnifera"
        assert data["legal_scope"] == "domestic"
        assert data["section3"] is not None
        assert data["patentability_risk"] is not None
        assert data["patentability_risk"]["label"] == "decision_support_risk_indicator"
        grant = data["grant_likelihood"]
        assert grant is not None
        assert grant["label"] == "llm_estimated_grant_probability"
        assert 0.0 <= grant["probability"] <= 1.0
        assert data["retrieved_sources"]
        assert data["final_answer"]
        assert "not legal advice" in data["disclaimer"].lower()
    finally:
        patent_api._graph = None


def test_patent_advisor_international(scripted_llm):
    patent_api._graph = build_patent_advisor_graph(llm=scripted_llm)
    try:
        resp = client.post(
            "/api/v1/patent-advisor",
            json={
                "product": "Ashwagandha capsule",
                "ingredients": ["Ashwagandha"],
                "language": "en",
                "jurisdiction": "india",
                "legal_scope": "international",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["legal_scope"] == "international"
        assert data["retrieved_sources"]
        assert all(s["legal_scope"] == "international" for s in data["retrieved_sources"])
    finally:
        patent_api._graph = None


def test_patent_advisor_validation_error():
    resp = client.post("/api/v1/patent-advisor", json={})
    assert resp.status_code == 422
