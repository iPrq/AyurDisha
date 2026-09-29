"""Seed the knowledge graph (Neo4j when NEO4J_URI is set) with curated + corpus entities.

Usage (from app/):  uv run python -m scripts.seed_knowledge_graph [--no-corpus]
"""

from __future__ import annotations

import argparse
import json
import logging

from config import get_settings
from knowledge_graph.service import get_graph_store, seed_state, seed_store


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-corpus", action="store_true", help="Only curated seed entities")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    store = get_graph_store(settings)
    if store.backend != "neo4j":
        logging.warning("NEO4J_URI not configured/reachable — seeding a throwaway in-memory graph.")
    seed_store(store, settings, corpus=not args.no_corpus)
    print(json.dumps({**store.stats().model_dump(), "seed": seed_state()}, indent=2))


if __name__ == "__main__":
    main()
