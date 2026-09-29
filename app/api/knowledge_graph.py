"""Knowledge-graph explorer API (Neo4j, or in-memory fallback)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from knowledge_graph.schema import GraphNode, GraphView, VocabularyTerm
from knowledge_graph.service import get_graph_store, seed_state, seed_store

router = APIRouter(prefix="/api/v1/kg", tags=["knowledge-graph"])


@router.get("/entity", response_model=GraphView)
def entity(
    q: str = Query(..., min_length=1, description="Entity key or name / alias, e.g. 'Ashwagandha'"),
    depth: int = Query(1, ge=1, le=3),
    limit: int = Query(120, ge=10, le=500),
) -> GraphView:
    """Subgraph around one entity (herb, formulation, compound, source...)."""
    view = get_graph_store().neighborhood(q.strip(), depth=depth, limit=limit)
    if view is None:
        raise HTTPException(status_code=404, detail=f"No knowledge-graph entity matches {q!r}.")
    return view


@router.get("/search", response_model=list[GraphNode])
def search(q: str = Query(..., min_length=2), limit: int = Query(20, ge=1, le=100)) -> list[GraphNode]:
    return get_graph_store().search(q, limit=limit)


@router.get("/vocabulary", response_model=list[VocabularyTerm])
def vocabulary() -> list[VocabularyTerm]:
    """Names and aliases of herbs, formulations and compounds (for highlighting in text)."""
    return get_graph_store().vocabulary()


@router.get("/stats")
def stats() -> dict[str, Any]:
    return {**get_graph_store().stats().model_dump(), "seed": seed_state()}


@router.post("/seed")
def seed(background_tasks: BackgroundTasks, corpus: bool = True) -> dict[str, Any]:
    """(Re)seed curated entities and corpus mentions; merges, never deletes."""
    background_tasks.add_task(seed_store, get_graph_store(), corpus=corpus)
    return {"status": "scheduled"}
