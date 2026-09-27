"""Pytest fixtures — scripted LLM so tests never call NVIDIA NIM."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_APP_ROOT = Path(__file__).resolve().parents[1]
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from graph.models import (  # noqa: E402
    ClaimSupportStatus,
    ClaimVerification,
    EvidenceKind,
    IPRouteAnalysis,
    IPRouteSuggestion,
    IPRouteType,
    LegalScope,
    PriorArtFinding,
    PriorArtResult,
    Section3Clause,
    Section3ProvisionResult,
    Section3Results,
    VerificationOutcome,
    VerificationResult,
)


def _prompt_source_ids(user: str) -> list[str]:
    import re

    return re.findall(r"^source_id=(\S+)$", user, flags=re.MULTILINE)


def _scripted_new_features(name: str, user: str) -> Any | None:
    """Product Review / NBA-ABS responses that cite ids actually present in the prompt."""
    from graph.models import (
        AbsApplicability,
        AbsApplicabilityStatus,
        AbsRateSelection,
        CompetitorProduct,
        DimensionRating,
        LegalComplianceAssessment,
        MarketFeasibilityAssessment,
        ResourceAccessibilityAssessment,
        ResourceAvailability,
        ReviewFinding,
    )

    ids = _prompt_source_ids(user)
    first = ids[:1]

    if name == "MarketFeasibilityAssessment":
        return MarketFeasibilityAssessment(
            rating=DimensionRating.MODERATE,
            summary="Existing single-herb products indicate an established category.",
            target_category="Ayurvedic capsules",
            competitors=[
                CompetitorProduct(name="Listed competitor", evidence_source_ids=first),
                CompetitorProduct(name="Uncited brand", evidence_source_ids=[]),
            ],
            findings=[
                ReviewFinding(summary="Products sold via pharmacies.", evidence_source_ids=first)
            ],
        )
    if name == "LegalComplianceAssessment":
        scope = (
            LegalScope.INTERNATIONAL
            if "legal_scope=international" in user
            else LegalScope.DOMESTIC
        )
        return LegalComplianceAssessment(
            rating=DimensionRating.MODERATE,
            summary="Manufacturing licence and GMP requirements apply.",
            regulatory_category="Ayurvedic proprietary medicine",
            requirements=[
                ReviewFinding(summary="State manufacturing licence.", evidence_source_ids=first)
            ],
            legal_scope=scope,
        )
    if name == "ResourceAccessibilityAssessment":
        return ResourceAccessibilityAssessment(
            rating=DimensionRating.FAVORABLE,
            summary="Plant is reported as cultivated.",
            resources=[
                ResourceAvailability(
                    ingredient="Ashwagandha",
                    botanical_name="Withania somnifera",
                    cultivation="Cultivated in several states.",
                    evidence_source_ids=first,
                )
            ],
        )
    if name == "AbsApplicability":
        cite = ["fixture-in-abs-bd-act"] if "fixture-in-abs-bd-act" in ids else first
        return AbsApplicability(
            status=AbsApplicabilityStatus.APPLICABLE,
            authority="State Biodiversity Board",
            summary="Commercial utilization by an Indian entity requires prior intimation.",
            reasons=[ReviewFinding(summary="Prior intimation to SBB.", evidence_source_ids=cite)],
        )
    if name == "AbsRateSelection":
        return AbsRateSelection(
            percentage=0.2,
            basis="annual gross ex-factory sale",
            tier_description="above Rs 1 crore and up to Rs 3 crore",
            source_id="fixture-in-abs-rates" if "fixture-in-abs-rates" in ids else None,
            quoted_text="above Rs 1 crore and up to Rs 3 crore: 0.2 per cent",
            rationale="Turnover falls in the Rs 1-3 crore slab.",
        )
    return None


class ScriptedLLM:
    """Callable stand-in: (schema, system, user) -> Pydantic model.

    ``overrides`` maps schema name -> model instance (or callable(user) -> model).
    """

    def __init__(self, overrides: dict[str, Any] | None = None) -> None:
        self.overrides = dict(overrides or {})
        self.calls: list[str] = []

    def __call__(self, schema: type, system: str, user: str) -> Any:
        name = schema.__name__
        self.calls.append(name)
        if name in self.overrides:
            value = self.overrides[name]
            return value(user) if callable(value) else value
        scripted = _scripted_new_features(name, user)
        if scripted is not None:
            return scripted
        if name == "Section3Results":
            if "legal_scope=international" in user or "legal_scope=international" in system:
                return Section3Results(
                    provisions=[],
                    summary="Comparative sources only; no domestic Section 3 triggers applied.",
                    jurisdiction="india",
                    legal_scope=LegalScope.INTERNATIONAL,
                    insufficient_evidence=False,
                )
            return Section3Results(
                provisions=[
                    Section3ProvisionResult(
                        clause=Section3Clause.D,
                        triggered=True,
                        reason="Retrieved sources discuss 3(d) known substance / efficacy themes.",
                        evidence_source_ids=["fixture-in-s3d"],
                        evidence_kind=EvidenceKind.FACT_FROM_SOURCE,
                    ),
                    Section3ProvisionResult(
                        clause=Section3Clause.E,
                        triggered=True,
                        reason="Retrieved sources discuss 3(e) mere admixture themes.",
                        evidence_source_ids=["fixture-in-s3e"],
                        evidence_kind=EvidenceKind.FACT_FROM_SOURCE,
                    ),
                    Section3ProvisionResult(
                        clause=Section3Clause.P,
                        triggered=True,
                        reason="Retrieved sources discuss 3(p) traditional knowledge themes.",
                        evidence_source_ids=["fixture-in-s3p"],
                        evidence_kind=EvidenceKind.FACT_FROM_SOURCE,
                    ),
                ],
                summary="Section 3 provisions with retrieved support: 3(d), 3(e), 3(p).",
                jurisdiction="india",
                legal_scope=LegalScope.DOMESTIC,
                insufficient_evidence=False,
            )
        if name == "PriorArtResult":
            return PriorArtResult(
                findings=[
                    PriorArtFinding(
                        summary="Fixture prior-art note discusses Withania formulations.",
                        evidence_source_ids=["fixture-in-prior-art"],
                        evidence_kind=EvidenceKind.FACT_FROM_SOURCE,
                    )
                ],
                summary="Prior-art related findings from retrieved sources.",
                insufficient_evidence=False,
                legal_scope=LegalScope.DOMESTIC,
            )
        if name == "IPRouteAnalysis":
            return IPRouteAnalysis(
                suggestions=[
                    IPRouteSuggestion(
                        route=IPRouteType.PATENT,
                        appropriate=False,
                        rationale="Section 3 themes triggered; elevated patent risk.",
                        evidence_source_ids=["fixture-in-ip-routes"],
                    ),
                    IPRouteSuggestion(
                        route=IPRouteType.TRADEMARK,
                        appropriate=True,
                        rationale="Trademark may protect brand identity.",
                        evidence_source_ids=["fixture-in-ip-routes"],
                    ),
                    IPRouteSuggestion(
                        route=IPRouteType.DESIGN,
                        appropriate=False,
                        rationale="Insufficient design evidence.",
                        evidence_source_ids=[],
                    ),
                    IPRouteSuggestion(
                        route=IPRouteType.TRADE_SECRET,
                        appropriate=True,
                        rationale="Trade secret may suit process know-how.",
                        evidence_source_ids=["fixture-in-ip-routes"],
                    ),
                ],
                summary="IP pathway suggestions grounded in retrieved guidance.",
                insufficient_evidence=False,
                legal_scope=LegalScope.DOMESTIC,
            )
        if name == "VerificationResult":
            return VerificationResult(
                outcome=VerificationOutcome.PASS,
                claims=[
                    ClaimVerification(
                        claim="supported claim",
                        status=ClaimSupportStatus.SUPPORTED,
                        evidence_source_ids=["fixture-in-s3d"],
                    )
                ],
                stripped_unsupported_claims=[],
                escalation_reasons=[],
            )
        if name == "BotanicalResult":
            from graph.models import BotanicalResult, BotanicalStatus

            return BotanicalResult(
                status=BotanicalStatus.UNRESOLVED,
                input_term="unknown",
                confidence=0.0,
                notes="scripted unresolved",
            )
        raise AssertionError(f"No scripted response for schema {name}")


@pytest.fixture
def scripted_llm() -> ScriptedLLM:
    return ScriptedLLM()


# ---------------------------------------------------------------------------
# Retrieval fixtures — offline (no NVIDIA, no Qdrant Cloud)
# ---------------------------------------------------------------------------

INGEST_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "ingest_raw"


class FakeEmbeddings:
    """Deterministic hashed bag-of-words vectors (stands in for NVIDIAEmbeddings)."""

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim
        self.query_calls = 0
        self.document_calls = 0

    def _embed(self, text: str) -> list[float]:
        import hashlib
        import math

        from retrieval.bm25_index import tokenize

        vec = [0.0] * self.dim
        for tok in tokenize(text):
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls += 1
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        self.query_calls += 1
        return self._embed(text)


@pytest.fixture
def fake_embeddings() -> FakeEmbeddings:
    return FakeEmbeddings()


@pytest.fixture
def ingest_fixture_dir() -> Path:
    return INGEST_FIXTURE_DIR


@pytest.fixture
def indexed_qdrant(tmp_path, fake_embeddings):
    """In-memory Qdrant populated from the ingestion fixtures via build_index()."""
    from qdrant_client import QdrantClient

    from ingest.build_index import build_index

    client = QdrantClient(location=":memory:")
    processed = tmp_path / "processed"
    chunks = build_index(
        client=client,
        embeddings=fake_embeddings,
        collection="test_legal",
        raw_dir=INGEST_FIXTURE_DIR,
        processed_dir=processed,
        recreate=True,
    )
    try:
        yield {
            "client": client,
            "collection": "test_legal",
            "chunks": chunks,
            "processed_dir": processed,
            "embeddings": fake_embeddings,
        }
    finally:
        client.close()
