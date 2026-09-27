"""Build the Qdrant collection + BM25 artifacts from ``data/raw``.

Run from ``app/``:

    uv run python -m ingest.build_index --recreate
"""

from __future__ import annotations

import argparse
import logging
import sys
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

from config import Settings, get_settings
from ingest.chunking import chunk_documents
from ingest.documents import load_raw_documents
from retrieval.bm25_index import BM25Store
from retrieval.chunks import CanonicalChunk
from retrieval.embeddings import Embeddings, probe_embedding_dimension

if TYPE_CHECKING:
    from qdrant_client import QdrantClient

logger = logging.getLogger("ingest.build_index")

DEFAULT_RAW_DIR = "./data/raw"
INDEXED_PAYLOAD_FIELDS = ("jurisdiction", "legal_scope", "source_type")


def ensure_collection(
    client: "QdrantClient", collection: str, dim: int, *, recreate: bool
) -> None:
    from qdrant_client import models

    exists = client.collection_exists(collection)
    if exists and recreate:
        logger.info("Deleting existing collection '%s'", collection)
        client.delete_collection(collection)
        exists = False

    if exists:
        info = client.get_collection(collection)
        vectors = info.config.params.vectors
        size = getattr(vectors, "size", None)
        if size != dim:
            raise RuntimeError(
                f"Collection '{collection}' has vector size {size}, but the embedding "
                f"model produces {dim}. Re-run with --recreate."
            )
        logger.info("Reusing collection '%s' (dim=%d)", collection, dim)
    else:
        client.create_collection(
            collection_name=collection,
            vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
        )
        logger.info("Created collection '%s' (dim=%d, cosine)", collection, dim)

    with warnings.catch_warnings():
        # Embedded/local Qdrant ignores payload indexes; server/cloud uses them.
        warnings.filterwarnings("ignore", message="Payload indexes have no effect")
        for field in INDEXED_PAYLOAD_FIELDS:
            client.create_payload_index(
                collection_name=collection,
                field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )


def upload_chunks(
    client: "QdrantClient",
    collection: str,
    chunks: list[CanonicalChunk],
    embeddings: Embeddings,
    *,
    batch_size: int = 32,
) -> None:
    from qdrant_client import models

    total = len(chunks)
    for start in range(0, total, batch_size):
        batch = chunks[start : start + batch_size]
        vectors = embeddings.embed_documents([c.index_text() for c in batch])
        client.upsert(
            collection_name=collection,
            points=[
                models.PointStruct(id=c.point_id, vector=v, payload=c.to_payload())
                for c, v in zip(batch, vectors, strict=True)
            ],
            wait=True,
        )
        logger.info("Upserted %d/%d chunks", min(start + batch_size, total), total)


def build_index(
    *,
    client: "QdrantClient",
    embeddings: Embeddings,
    collection: str,
    raw_dir: Path | str = DEFAULT_RAW_DIR,
    processed_dir: Path | str = "./data/processed",
    recreate: bool = False,
    batch_size: int = 32,
) -> list[CanonicalChunk]:
    """Parse -> chunk -> embed -> upsert to Qdrant -> persist BM25. Returns chunks."""
    docs = load_raw_documents(raw_dir)
    chunks = chunk_documents(docs)
    if not chunks:
        raise RuntimeError(
            f"No chunks produced from {raw_dir}. Add documents with .meta.json sidecars."
        )
    logger.info("Produced %d chunks from %d documents", len(chunks), len(docs))

    dim = probe_embedding_dimension(embeddings)
    ensure_collection(client, collection, dim, recreate=recreate)
    upload_chunks(client, collection, chunks, embeddings, batch_size=batch_size)

    BM25Store(chunks).save(processed_dir)
    count = client.count(collection_name=collection, exact=True).count
    logger.info("Collection '%s' now holds %d points", collection, count)
    return chunks


def main(argv: list[str] | None = None, settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build AyurDisha Qdrant + BM25 index")
    parser.add_argument("--raw-dir", default=DEFAULT_RAW_DIR)
    parser.add_argument("--processed-dir", default=None, help="defaults to BM25_DIR")
    parser.add_argument("--collection", default=None, help="defaults to QDRANT_COLLECTION")
    parser.add_argument(
        "--recreate", action="store_true", help="drop and recreate the collection"
    )
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    from retrieval.embeddings import create_nvidia_embeddings
    from retrieval.qdrant_client_factory import (
        RetrievalConfigError,
        check_qdrant_connection,
        create_qdrant_client,
    )

    cfg = settings or get_settings()
    collection = args.collection or cfg.qdrant_collection
    try:
        embeddings = create_nvidia_embeddings(cfg)
        client = create_qdrant_client(cfg)
        check_qdrant_connection(client, cfg)
    except RetrievalConfigError as exc:
        logger.error("%s", exc)
        return 2

    logger.info("Ingesting into collection '%s' (mode=%s)", collection, cfg.qdrant_mode)
    build_index(
        client=client,
        embeddings=embeddings,
        collection=collection,
        raw_dir=args.raw_dir,
        processed_dir=args.processed_dir or cfg.bm25_dir,
        recreate=args.recreate,
        batch_size=args.batch_size,
    )
    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
