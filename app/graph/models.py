"""Pydantic models and enums for Patent Advisor (and shared services)."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared enums
# ---------------------------------------------------------------------------


class LegalScope(str, Enum):
    """Domestic vs international legal analysis switch."""

    DOMESTIC = "domestic"
    INTERNATIONAL = "international"


class BotanicalStatus(str, Enum):
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    UNRESOLVED = "UNRESOLVED"


class ClaimSupportStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"


class VerificationOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


class Section3Clause(str, Enum):
    """Indian Patents Act Section 3 provisions of primary interest."""

    D = "3(d)"
    E = "3(e)"
    P = "3(p)"


class IPRouteType(str, Enum):
    PATENT = "Patent"
    TRADEMARK = "Trademark"
    DESIGN = "Design"
    TRADE_SECRET = "Trade Secret"


class EvidenceKind(str, Enum):
    """How a statement should be labeled in outputs."""

    FACT_FROM_SOURCE = "FACT_FROM_SOURCE"
    MODEL_INTERPRETATION = "MODEL_INTERPRETATION"
    CALCULATION = "CALCULATION"
    UNCERTAINTY = "UNCERTAINTY"


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


class RetrievedSource(BaseModel):
    """Single retrieved evidence item with full citation metadata."""

    id: str
    title: str
    text: str
    section: str | None = None
    source_type: str = Field(
        default="legal",
        description="e.g. statute, guidance, patent, comparative_ip, fixture",
    )
    source_url: str | None = None
    effective_date: str | None = None
    retrieval_score: float = 0.0
    jurisdiction: str | None = Field(
        default=None,
        description="Primary jurisdiction tag, e.g. india, uspto, wipo",
    )
    legal_scope: LegalScope | None = Field(
        default=None,
        description="Whether this source is domestic or international/comparative",
    )
    is_fixture: bool = Field(
        default=False,
        description="True for test fixtures — never treat as live government data",
    )


# ---------------------------------------------------------------------------
# Botanical normalizer
# ---------------------------------------------------------------------------


class BotanicalCandidate(BaseModel):
    botanical_name: str
    synonyms: list[str] = Field(default_factory=list)
    phytochemicals: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class BotanicalResult(BaseModel):
    status: BotanicalStatus
    input_term: str
    botanical_name: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    phytochemicals: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    candidates: list[BotanicalCandidate] = Field(
        default_factory=list,
        description="Populated on AMBIGUOUS — do not silently pick one",
    )
    notes: str | None = None


# ---------------------------------------------------------------------------
# Section 3 / patentability risk
# ---------------------------------------------------------------------------


class Section3ProvisionResult(BaseModel):
    clause: Section3Clause
    triggered: bool = False
    reason: str = ""
    evidence_source_ids: list[str] = Field(default_factory=list)
    evidence_kind: EvidenceKind = EvidenceKind.MODEL_INTERPRETATION


class Section3Results(BaseModel):
    provisions: list[Section3ProvisionResult] = Field(default_factory=list)
    summary: str = ""
    jurisdiction: str = "india"
    legal_scope: LegalScope = LegalScope.DOMESTIC
    insufficient_evidence: bool = False


class PatentabilityRiskIndicator(BaseModel):
    """Rule-based decision-support score — not probability of patent approval."""

    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Weighted sum of triggered Section 3 provisions",
    )
    triggered_clauses: list[Section3Clause] = Field(default_factory=list)
    weight_d: float = 0.35
    weight_e: float = 0.30
    weight_p: float = 0.35
    label: Literal["decision_support_risk_indicator"] = "decision_support_risk_indicator"
    disclaimer: str = (
        "Patentability risk indicator is rule-based decision support, "
        "not a probability of patent approval or legal advice."
    )


# ---------------------------------------------------------------------------
# Prior art / IP routes
# ---------------------------------------------------------------------------


class PriorArtFinding(BaseModel):
    summary: str
    evidence_source_ids: list[str] = Field(default_factory=list)
    evidence_kind: EvidenceKind = EvidenceKind.FACT_FROM_SOURCE
    relevance: str | None = None


class PriorArtResult(BaseModel):
    findings: list[PriorArtFinding] = Field(default_factory=list)
    summary: str = ""
    insufficient_evidence: bool = False
    legal_scope: LegalScope = LegalScope.DOMESTIC


class IPRouteSuggestion(BaseModel):
    route: IPRouteType
    appropriate: bool = False
    rationale: str = ""
    evidence_source_ids: list[str] = Field(default_factory=list)
    evidence_kind: EvidenceKind = EvidenceKind.MODEL_INTERPRETATION


class IPRouteAnalysis(BaseModel):
    suggestions: list[IPRouteSuggestion] = Field(default_factory=list)
    summary: str = ""
    insufficient_evidence: bool = False
    legal_scope: LegalScope = LegalScope.DOMESTIC


# ---------------------------------------------------------------------------
# Critic verifier
# ---------------------------------------------------------------------------


class ClaimVerification(BaseModel):
    claim: str
    status: ClaimSupportStatus
    evidence_source_ids: list[str] = Field(default_factory=list)
    notes: str | None = None


class VerificationResult(BaseModel):
    outcome: VerificationOutcome
    claims: list[ClaimVerification] = Field(default_factory=list)
    stripped_unsupported_claims: list[str] = Field(default_factory=list)
    escalation_reasons: list[str] = Field(default_factory=list)
    notes: str | None = None


# ---------------------------------------------------------------------------
# API-shaped request / response (wire models for Phase 6)
# ---------------------------------------------------------------------------


class PatentAdvisorRequest(BaseModel):
    product: str
    ingredients: list[str] = Field(default_factory=list)
    language: str = "en"
    jurisdiction: str = "india"
    legal_scope: LegalScope = LegalScope.DOMESTIC
    user_query: str | None = Field(
        default=None,
        description="Optional free-text query; product/ingredients remain primary",
    )


class PatentAdvisorResponse(BaseModel):
    product: str
    ingredients: list[str]
    language: str
    jurisdiction: str
    legal_scope: LegalScope
    botanical: BotanicalResult | None = None
    section3: Section3Results | None = None
    patentability_risk: PatentabilityRiskIndicator | None = None
    prior_art: PriorArtResult | None = None
    ip_routes: IPRouteAnalysis | None = None
    verification: VerificationResult | None = None
    retrieved_sources: list[RetrievedSource] = Field(default_factory=list)
    final_answer: str | None = None
    disclaimer: str = (
        "AyurDisha provides decision support only and is not legal advice. "
        "Unsupported claims are rejected or escalated; never invent statutes or foreign law."
    )
