"""Acts other than the Patents Act get prefixed section labels (e.g. "BDA 3(a)")
so they are never mistaken for Patents Act Section 3 clauses."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from config import Settings
from graph.models import SUPPORTED_SECTION3_CLAUSES, LegalScope, RetrievedSource
from graph.patent_advisor.retrieval import legal_patent_retrieval_node
from graph.patent_advisor.section3 import _clause_label
from ingest.chunking import chunk_documents
from ingest.documents import DocumentMeta, load_raw_documents


def _meta(**kw):
    base = dict(doc_id="x", title="T", source_type="statute", jurisdiction="india", legal_scope="domestic")
    return DocumentMeta(**{**base, **kw})


def test_prefix_is_optional_and_validated():
    assert _meta().section_label_prefix is None
    assert _meta(section_label_prefix="BDA").section_label_prefix == "BDA"
    for bad in ["bda", "B", "BD A", "3BD", "TOOLONGPREFIX"]:
        with pytest.raises(ValidationError):
            _meta(section_label_prefix=bad)


def _chunks(tmp_path, prefix):
    (tmp_path / "a.txt").write_text("3. H.—pre\n(a) clause a.\n(b) clause b.", encoding="utf-8")
    meta = {"doc_id": "other_act", "title": "Other Act", "source_type": "statute",
            "jurisdiction": "india", "legal_scope": "domestic"}
    if prefix:
        meta["section_label_prefix"] = prefix
    (tmp_path / "a.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return {c.id: c for c in chunk_documents(load_raw_documents(tmp_path))}


def test_prefixed_labels_and_unchanged_ids(tmp_path):
    chunks = _chunks(tmp_path, "BDA")
    assert chunks["other_act_3_a"].section == "BDA 3(a)"
    assert chunks["other_act_3"].section == "BDA 3"
    assert "Section BDA 3(a)" in chunks["other_act_3_a"].title


def test_no_prefix_keeps_existing_labels(tmp_path):
    assert _chunks(tmp_path, None)["other_act_3_a"].section == "3(a)"


def test_prefixed_label_is_not_a_patents_act_clause_label():
    src = lambda sec: RetrievedSource(id="s", title="t", text="x", section=sec)  # noqa: E731
    assert _clause_label(src("BDA 3(a)")) is None
    assert _clause_label(src("3(a)")) == "3(a)"


def test_focused_retrieval_excludes_prefixed_section3_labels():
    def _src(sid, section):
        return RetrievedSource(id=sid, title=sid, text="t", section=section, source_type="statute",
                               jurisdiction="india", legal_scope=LegalScope.DOMESTIC)

    class Fixed:
        def retrieve(self, query, *, source_types=None, **kw):
            return [_src("pa", "3(a)"), _src("bda", "BDA 3(a)")] if source_types else []

    state = {"product": "p", "ingredients": [], "language": "en",
             "jurisdiction": "india", "legal_scope": "domestic"}
    ids = [s.id for s in legal_patent_retrieval_node(state, retriever=Fixed(), settings=Settings())["retrieved_sources"]]
    assert ids == ["pa"]


CORPUS = Path(__file__).resolve().parents[1] / "data" / "raw" / "corpus"
needs_corpus = pytest.mark.skipif(
    not (CORPUS / "hf_biological_diversity_act_2002.meta.json").exists(),
    reason="real corpus not built (run scripts/build_corpus_docs.py)",
)


@needs_corpus
def test_real_corpus_only_patents_act_has_bare_section3_labels():
    chunks = chunk_documents(load_raw_documents(CORPUS))
    bare = [c.id for c in chunks if re.fullmatch(r"3(\([a-z]\))?", c.section or "")]
    assert bare and all(cid.startswith("hf_patents_act_1970_s3") for cid in bare)


@needs_corpus
def test_real_corpus_focused_retrieval_returns_exactly_patents_section3(tmp_path):
    from qdrant_client import QdrantClient

    from ingest.build_index import build_index
    from retrieval.bm25_index import BM25Store
    from retrieval.qdrant_hybrid import QdrantHybridRetriever
    from tests.conftest import FakeEmbeddings

    emb = FakeEmbeddings()
    client = QdrantClient(location=":memory:")  # in-memory only; no real index touched
    try:
        build_index(client=client, embeddings=emb, collection="real", raw_dir=CORPUS,
                    processed_dir=tmp_path / "processed", recreate=True)
        retriever = QdrantHybridRetriever(client, "real", emb, BM25Store.load(tmp_path / "processed"))
        state = {"product": "Ashwagandha capsule", "ingredients": ["Ashwagandha"], "language": "en",
                 "jurisdiction": "india", "legal_scope": "domestic", "botanical_name": "Withania somnifera"}
        update = legal_patent_retrieval_node(state, retriever=retriever, settings=Settings())
        sources = update["retrieved_sources"]
        s3 = {s.section for s in sources if re.fullmatch(r"3(\([a-z]\))?", s.section or "")}
        assert s3 >= set(SUPPORTED_SECTION3_CLAUSES)
        assert "3(g)" not in s3
        assert not any((s.section or "").startswith(("BDA 3", "DCA 3")) and s.section in SUPPORTED_SECTION3_CLAUSES
                       for s in sources)
        assert all(s.legal_scope == LegalScope.DOMESTIC for s in sources)  # US patents stay out
    finally:
        client.close()
