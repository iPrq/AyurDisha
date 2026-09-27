"""BM25 keyword index over the same canonical chunks stored in Qdrant."""

from __future__ import annotations

import json
import logging
import pickle
import platform
import re
from collections.abc import Callable
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import TYPE_CHECKING

from rank_bm25 import BM25Okapi

from retrieval.chunks import CanonicalChunk
from retrieval.qdrant_client_factory import INGEST_COMMAND, RetrievalConfigError

if TYPE_CHECKING:
    from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)

BM25_PICKLE = "bm25.pkl"
BM25_DOCUMENTS = "bm25_documents.json"
FORMAT_VERSION = 1

# Keeps legal clause references like "3(d)" as single tokens.
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:\([a-z]\))?")
_STOPWORDS = frozenset(
    "a an and are as at be by for from has have in is it its of on or that the "
    "this to was were which with".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOPWORDS]


def _runtime_fingerprint() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "rank_bm25": pkg_version("rank-bm25"),
    }


class BM25Store:
    """BM25Okapi + explicit position -> chunk ID mapping + canonical chunks."""

    def __init__(self, chunks: list[CanonicalChunk], bm25: BM25Okapi | None = None) -> None:
        ordered = sorted(chunks, key=lambda c: c.id)
        if len({c.id for c in ordered}) != len(ordered):
            raise ValueError("BM25 corpus contains duplicate chunk IDs")
        self.doc_ids: list[str] = [c.id for c in ordered]
        self.docs: dict[str, CanonicalChunk] = {c.id: c for c in ordered}
        if not ordered:
            raise RetrievalConfigError(
                f"BM25 corpus is empty. Run ingestion first: {INGEST_COMMAND}"
            )
        self.bm25 = bm25 or BM25Okapi([tokenize(c.index_text()) for c in ordered])

    def __len__(self) -> int:
        return len(self.doc_ids)

    def search(
        self,
        query: str,
        k: int,
        predicate: Callable[[CanonicalChunk], bool] | None = None,
    ) -> list[tuple[str, float]]:
        """Top-k (chunk_id, score) passing ``predicate``; ties broken by chunk ID."""
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self.bm25.get_scores(tokens)
        hits: list[tuple[str, float]] = []
        for pos, score in enumerate(scores):
            if score <= 0:
                continue
            chunk_id = self.doc_ids[pos]
            if predicate is not None and not predicate(self.docs[chunk_id]):
                continue
            hits.append((chunk_id, float(score)))
        hits.sort(key=lambda h: (-h[1], h[0]))
        return hits[:k]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, directory: Path | str) -> None:
        out = Path(directory)
        out.mkdir(parents=True, exist_ok=True)
        corpus = {
            "format_version": FORMAT_VERSION,
            "doc_ids": self.doc_ids,
            "chunks": [self.docs[i].to_payload() for i in self.doc_ids],
        }
        (out / BM25_DOCUMENTS).write_text(
            json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        with (out / BM25_PICKLE).open("wb") as fh:
            pickle.dump(
                {
                    "format_version": FORMAT_VERSION,
                    "runtime": _runtime_fingerprint(),
                    "doc_ids": self.doc_ids,
                    "bm25": self.bm25,
                },
                fh,
            )
        logger.info("Saved BM25 index (%d docs) to %s", len(self), out)

    @classmethod
    def load(cls, directory: Path | str) -> "BM25Store":
        """Load from ``directory``; rebuilds from JSON if the pickle is stale/missing."""
        root = Path(directory)
        docs_path = root / BM25_DOCUMENTS
        if not docs_path.exists():
            raise RetrievalConfigError(
                f"BM25 index not found at {docs_path}. Run ingestion first: {INGEST_COMMAND}"
            )
        corpus = json.loads(docs_path.read_text(encoding="utf-8"))
        chunks = [CanonicalChunk.from_payload(p) for p in corpus["chunks"]]

        bm25: BM25Okapi | None = None
        pkl_path = root / BM25_PICKLE
        if pkl_path.exists():
            try:
                with pkl_path.open("rb") as fh:
                    blob = pickle.load(fh)  # noqa: S301 - trusted, locally generated artifact
                if (
                    blob.get("format_version") == FORMAT_VERSION
                    and blob.get("runtime") == _runtime_fingerprint()
                    and blob.get("doc_ids") == sorted(c.id for c in chunks)
                ):
                    bm25 = blob["bm25"]
                else:
                    logger.info("BM25 pickle is stale for this runtime; rebuilding from JSON")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not load BM25 pickle (%s); rebuilding from JSON", exc)
        store = cls(chunks, bm25=bm25)
        logger.info("Loaded BM25 index with %d docs from %s", len(store), root)
        return store

    @classmethod
    def from_qdrant(
        cls, client: "QdrantClient", collection: str, batch_size: int = 256
    ) -> "BM25Store":
        """Rebuild BM25 from the collection's payloads (canonical corpus in Qdrant)."""
        chunks: list[CanonicalChunk] = []
        offset = None
        while True:
            points, offset = client.scroll(
                collection_name=collection,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            chunks.extend(CanonicalChunk.from_payload(p.payload or {}) for p in points)
            if offset is None:
                break
        store = cls(chunks)
        logger.info(
            "Built BM25 index from Qdrant collection '%s' (%d docs)", collection, len(store)
        )
        return store
