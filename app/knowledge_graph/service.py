"""Knowledge-graph lifecycle: store selection, seeding, and recording pipeline results."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from config import Settings, get_settings
from graph.models import BotanicalCandidate
from knowledge_graph.base import BotanicalKnowledgeGraph
from knowledge_graph.builders import build_corpus_batch, build_response_batch, build_seed_batch
from knowledge_graph.schema import FORMULATION, HERB, normalize
from knowledge_graph.store import GraphStore, InMemoryGraphStore

logger = logging.getLogger(__name__)

_store: GraphStore | None = None
_store_lock = threading.Lock()
_seed_lock = threading.Lock()
_seed_state: dict[str, Any] = {"status": "idle", "error": None}


def get_graph_store(settings: Settings | None = None) -> GraphStore:
    """Neo4j when configured and reachable, otherwise the in-memory fallback."""
    global _store
    if _store is not None:
        return _store
    with _store_lock:
        if _store is not None:
            return _store
        cfg = settings or get_settings()
        if cfg.kg_backend == "neo4j" and cfg.neo4j_uri:
            try:
                from knowledge_graph.neo4j_store import Neo4jGraphStore

                _store = Neo4jGraphStore(
                    cfg.neo4j_uri,
                    cfg.neo4j_user,
                    cfg.neo4j_password or "",
                    database=cfg.neo4j_database,
                )
                logger.info("Knowledge graph: Neo4j at %s", cfg.neo4j_uri)
                return _store
            except Exception as exc:  # noqa: BLE001
                logger.warning("Neo4j unavailable (%s); using in-memory knowledge graph", exc)
        _store = InMemoryGraphStore()
        logger.info("Knowledge graph: in-memory")
        return _store


def seed_state() -> dict[str, Any]:
    return dict(_seed_state)


def seed_store(store: GraphStore, settings: Settings | None = None, *, corpus: bool = True) -> None:
    cfg = settings or get_settings()
    with _seed_lock:
        _seed_state.update(status="running", error=None)
        try:
            seed = build_seed_batch()
            store.merge_batch(seed, origin="curated")
            corpus_dir = Path(cfg.kg_corpus_dir)
            if corpus and corpus_dir.is_dir():
                store.merge_batch(build_corpus_batch(corpus_dir, seed), origin="corpus")
            _seed_state.update(status="done")
            logger.info("Knowledge graph seeded: %s", store.stats().model_dump())
        except Exception as exc:  # noqa: BLE001
            _seed_state.update(status="failed", error=str(exc))
            logger.exception("Knowledge graph seeding failed")


def seed_in_background(settings: Settings | None = None) -> None:
    cfg = settings or get_settings()
    if not cfg.kg_auto_seed:
        return

    def _run() -> None:
        store = get_graph_store(cfg)
        if store.is_empty():
            seed_store(store, cfg)
        else:
            _seed_state.update(status="done")

    threading.Thread(target=_run, name="kg-seed", daemon=True).start()


def record_response(response: Any, *, feature: str, settings: Settings | None = None) -> None:
    """Upsert a pipeline response into the graph; never raises (runs as a background task)."""
    cfg = settings or get_settings()
    if not cfg.kg_record_responses:
        return
    try:
        store = get_graph_store(cfg)
        vocabulary: dict[str, set[str]] = {}
        for term in store.vocabulary((HERB, FORMULATION)):
            vocabulary.setdefault(normalize(term.term), set()).add(term.key)
        batch = build_response_batch(response, feature=feature, vocabulary=vocabulary)
        store.merge_batch(batch, origin="pipeline")
    except Exception:  # noqa: BLE001
        logger.exception("Failed to record %s response in knowledge graph", feature)


class GraphBotanicalKG:
    """BotanicalKnowledgeGraph backed by the graph store, falling back to fixtures."""

    def __init__(self, store: GraphStore, fallback: BotanicalKnowledgeGraph) -> None:
        self._store = store
        self._fallback = fallback

    def lookup(self, term: str) -> list[BotanicalCandidate]:
        try:
            hits = self._store.lookup_botanical(term)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Knowledge graph lookup failed for %r: %s", term, exc)
            hits = []
        return hits or self._fallback.lookup(term)
