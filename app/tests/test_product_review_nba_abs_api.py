"""API tests for POST /api/v1/product-review and /api/v1/nba-abs (no paid API)."""

from __future__ import annotations

from fastapi.testclient import TestClient

import api.nba_abs as nba_abs_api
import api.product_review as product_review_api
from graph.nba_abs_graph import build_nba_abs_graph
from graph.product_review_graph import build_product_review_graph
from main import app
from websearch.mock import MockWebSearcher

client = TestClient(app)


def test_product_review_endpoint(scripted_llm):
    product_review_api._graph = build_product_review_graph(
        llm=scripted_llm, searcher=MockWebSearcher()
    )
    try:
        resp = client.post(
            "/api/v1/product-review",
            json={"product": "Ashwagandha capsule", "ingredients": ["Ashwagandha"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        for dim in ("market_feasibility", "legal_compliance", "resource_accessibility"):
            assert data[dim]["rating"] in {
                "FAVORABLE",
                "MODERATE",
                "CHALLENGING",
                "INSUFFICIENT_EVIDENCE",
            }
        assert data["botanicals"][0]["botanical_name"] == "Withania somnifera"
        assert data["retrieved_sources"]
        assert data["combined_summary"]
        assert "not legal" in data["disclaimer"].lower()
    finally:
        product_review_api._graph = None


def test_nba_abs_endpoint(scripted_llm):
    nba_abs_api._graph = build_nba_abs_graph(llm=scripted_llm)
    try:
        resp = client.post(
            "/api/v1/nba-abs",
            json={
                "product": "Ashwagandha capsule",
                "ingredients": ["Ashwagandha"],
                "annual_turnover_inr": 20000000,
                "entity_type": "indian",
                "resource_source": "wild",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["calculation"]["fee_inr"] == 40000.0
        assert data["calculation"]["formula"] == "fee = turnover * percentage / 100"
        assert data["calculation"]["evidence_kind"] == "CALCULATION"
        assert data["applicability"]["status"] == "APPLICABLE"
    finally:
        nba_abs_api._graph = None


def test_validation_errors():
    assert client.post("/api/v1/product-review", json={}).status_code == 422
    assert (
        client.post(
            "/api/v1/nba-abs", json={"product": "x", "annual_turnover_inr": -5}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/nba-abs", json={"product": "x", "percentage_override": 150}
        ).status_code
        == 422
    )
