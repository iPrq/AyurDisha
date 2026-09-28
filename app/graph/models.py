"""Pydantic models and enums for Patent Advisor (and shared services)."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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
    """Indian Patents Act Section 3 clauses supported by the Section 3 analyzer.

    3(g) is intentionally NOT a member: it is never an active provision in
    AyurDisha (see ``UNSUPPORTED_SECTION3_CLAUSES``).
    """

    A = "3(a)"
    B = "3(b)"
    C = "3(c)"
    D = "3(d)"
    E = "3(e)"
    F = "3(f)"
    H = "3(h)"
    I = "3(i)"  # noqa: E741 - clause letter
    J = "3(j)"
    K = "3(k)"
    L = "3(l)"
    M = "3(m)"
    N = "3(n)"
    O = "3(o)"  # noqa: E741 - clause letter
    P = "3(p)"


# Single source of truth for the supported clause references, e.g. "3(a)".
SUPPORTED_SECTION3_CLAUSES: tuple[str, ...] = tuple(c.value for c in Section3Clause)

# Clause references deliberately excluded from analysis. 3(g) must never be
# treated as an active provision; it is recorded as rejected if a model returns it.
UNSUPPORTED_SECTION3_CLAUSES: frozenset[str] = frozenset({"3(g)"})

_SECTION3_REF_RE = re.compile(
    r"^\s*(?:section\s*)?3\s*\(\s*([a-z])\s*\)\s*$", re.IGNORECASE
)


def normalize_section3_clause_ref(value: object) -> object:
    """Normalize model-output variants ("3 (k)", "Section 3(k)", "3(K)") to "3(k)".

    Non-matching values are returned unchanged so validation can reject them.
    """
    if isinstance(value, Section3Clause):
        return value
    if isinstance(value, str):
        m = _SECTION3_REF_RE.match(value)
        if m:
            return f"3({m.group(1).lower()})"
        return value.strip()
    return value


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
    evidence_gap: bool = Field(
        default=False,
        description="True when a trigger was cleared because no valid retrieved evidence remained",
    )

    @field_validator("clause", mode="before")
    @classmethod
    def _normalize_clause(cls, v: Any) -> Any:
        return normalize_section3_clause_ref(v)


class Section3Results(BaseModel):
    provisions: list[Section3ProvisionResult] = Field(default_factory=list)
    summary: str = ""
    jurisdiction: str = "india"
    legal_scope: LegalScope = LegalScope.DOMESTIC
    insufficient_evidence: bool = False
    rejected_clauses: list[str] = Field(
        default_factory=list,
        description="Clause references returned by the model that are not supported (e.g. 3(g)); dropped",
    )
    evidence_gap_clauses: list[Section3Clause] = Field(
        default_factory=list,
        description="Clauses whose trigger was cleared for lack of valid retrieved evidence",
    )

    @model_validator(mode="before")
    @classmethod
    def _drop_unsupported_clauses(cls, data: Any) -> Any:
        """Reject unsupported clauses (3(g), 3(q), ...) safely instead of failing the request."""
        if not isinstance(data, dict) or not isinstance(data.get("provisions"), list):
            return data
        kept: list[Any] = []
        rejected = list(data.get("rejected_clauses") or [])
        for item in data["provisions"]:
            if isinstance(item, Section3ProvisionResult):
                kept.append(item)
                continue
            raw = item.get("clause") if isinstance(item, dict) else None
            ref = normalize_section3_clause_ref(raw)
            if isinstance(ref, Section3Clause) or ref in SUPPORTED_SECTION3_CLAUSES:
                kept.append(item)
            else:
                label = str(ref) if ref not in (None, "") else "<missing clause>"
                if label not in rejected:
                    rejected.append(label)
        return {**data, "provisions": kept, "rejected_clauses": rejected}


class PatentabilityRiskIndicator(BaseModel):
    """Rule-based decision-support score — not probability of patent approval."""

    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Weighted sum of triggered Section 3 provisions",
    )
    triggered_clauses: list[Section3Clause] = Field(default_factory=list)
    unweighted_triggered_clauses: list[Section3Clause] = Field(
        default_factory=list,
        description=(
            "Triggered clauses with no configured risk weight; they add nothing to "
            "score (no weights are invented) and need separate human consideration"
        ),
    )
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


# ---------------------------------------------------------------------------
# Product Review (Feature 1)
# ---------------------------------------------------------------------------


class DimensionRating(str, Enum):
    """Qualitative per-dimension rating — never collapsed into one combined score."""

    FAVORABLE = "FAVORABLE"
    MODERATE = "MODERATE"
    CHALLENGING = "CHALLENGING"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ReviewFinding(BaseModel):
    summary: str
    evidence_source_ids: list[str] = Field(default_factory=list)
    evidence_kind: EvidenceKind = EvidenceKind.FACT_FROM_SOURCE


class CompetitorProduct(BaseModel):
    name: str
    company: str | None = None
    notes: str | None = None
    evidence_source_ids: list[str] = Field(default_factory=list)


class MarketFeasibilityAssessment(BaseModel):
    rating: DimensionRating = DimensionRating.INSUFFICIENT_EVIDENCE
    summary: str = ""
    target_category: str | None = None
    target_market: str | None = None
    competitors: list[CompetitorProduct] = Field(default_factory=list)
    demand_indicators: list[ReviewFinding] = Field(default_factory=list)
    findings: list[ReviewFinding] = Field(default_factory=list)
    insufficient_evidence: bool = False


class LegalComplianceAssessment(BaseModel):
    rating: DimensionRating = DimensionRating.INSUFFICIENT_EVIDENCE
    summary: str = ""
    regulatory_category: str | None = Field(
        default=None,
        description="e.g. Ayurvedic proprietary medicine, health supplement (food)",
    )
    requirements: list[ReviewFinding] = Field(default_factory=list)
    restrictions: list[ReviewFinding] = Field(default_factory=list)
    insufficient_evidence: bool = False
    legal_scope: LegalScope = LegalScope.DOMESTIC


class ResourceAvailability(BaseModel):
    ingredient: str
    botanical_name: str | None = None
    availability: str = ""
    cultivation: str = ""
    sustainability_concerns: str = ""
    evidence_source_ids: list[str] = Field(default_factory=list)


class ResourceAccessibilityAssessment(BaseModel):
    rating: DimensionRating = DimensionRating.INSUFFICIENT_EVIDENCE
    summary: str = ""
    resources: list[ResourceAvailability] = Field(default_factory=list)
    findings: list[ReviewFinding] = Field(default_factory=list)
    insufficient_evidence: bool = False


class ProductReviewRequest(BaseModel):
    product: str
    ingredients: list[str] = Field(default_factory=list)
    language: str = "en"
    jurisdiction: str = "india"
    legal_scope: LegalScope = LegalScope.DOMESTIC
    target_market: str | None = Field(
        default=None, description="Defaults to the jurisdiction when omitted"
    )
    product_category: str | None = Field(
        default=None,
        description="Optional hint, e.g. 'Ayurvedic proprietary medicine' or 'health supplement'",
    )
    user_query: str | None = None


class ProductReviewResponse(BaseModel):
    product: str
    ingredients: list[str]
    language: str
    jurisdiction: str
    legal_scope: LegalScope
    target_market: str | None = None
    botanicals: list[BotanicalResult] = Field(default_factory=list)
    market_feasibility: MarketFeasibilityAssessment | None = None
    legal_compliance: LegalComplianceAssessment | None = None
    resource_accessibility: ResourceAccessibilityAssessment | None = None
    combined_summary: str | None = None
    verification: VerificationResult | None = None
    retrieved_sources: list[RetrievedSource] = Field(default_factory=list)
    final_answer: str | None = None
    disclaimer: str = (
        "AyurDisha provides decision support only and is not legal, regulatory, or "
        "investment advice. Market and resource evidence comes from retrieved/web "
        "sources and may be incomplete; unsupported claims are rejected or escalated."
    )


# ---------------------------------------------------------------------------
# NBA / ABS Calculator (Feature 3)
# ---------------------------------------------------------------------------


class AbsPurpose(str, Enum):
    COMMERCIAL_UTILIZATION = "commercial_utilization"
    RESEARCH = "research"
    BIO_SURVEY = "bio_survey"
    IPR = "ipr"


class EntityType(str, Enum):
    INDIAN = "indian"
    FOREIGN = "foreign"


class ResourceSource(str, Enum):
    WILD = "wild"
    CULTIVATED = "cultivated"
    UNKNOWN = "unknown"


class AbsApplicabilityStatus(str, Enum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNCERTAIN = "UNCERTAIN"


class AbsApplicability(BaseModel):
    status: AbsApplicabilityStatus = AbsApplicabilityStatus.UNCERTAIN
    authority: str | None = Field(
        default=None, description="e.g. NBA or State Biodiversity Board — from sources only"
    )
    summary: str = ""
    reasons: list[ReviewFinding] = Field(default_factory=list)
    exemptions_considered: list[ReviewFinding] = Field(default_factory=list)
    insufficient_evidence: bool = False


class AbsRateSelection(BaseModel):
    """LLM-selected rate; Python checks it appears verbatim in the cited source."""

    percentage: float | None = Field(default=None, ge=0.0, le=100.0)
    basis: str | None = Field(
        default=None, description="e.g. annual gross ex-factory sale price"
    )
    tier_description: str | None = None
    source_id: str | None = None
    quoted_text: str | None = None
    rationale: str = ""
    grounded: bool = Field(
        default=False,
        description="Set by Python: percentage found in cited source text",
    )
    insufficient_evidence: bool = False


class AbsFeeCalculation(BaseModel):
    annual_turnover_inr: float
    percentage: float
    fee_inr: float
    formula: str = "fee = turnover * percentage / 100"
    percentage_origin: Literal["source", "user_override"] = "source"
    source_id: str | None = None
    evidence_kind: EvidenceKind = EvidenceKind.CALCULATION


class NbaAbsRequest(BaseModel):
    product: str
    ingredients: list[str] = Field(default_factory=list)
    annual_turnover_inr: float | None = Field(
        default=None,
        ge=0.0,
        description="Annual gross ex-factory sale (INR) of the product using the resource",
    )
    purpose: AbsPurpose = AbsPurpose.COMMERCIAL_UTILIZATION
    entity_type: EntityType = EntityType.INDIAN
    resource_source: ResourceSource = ResourceSource.UNKNOWN
    percentage_override: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="User-supplied rate; bypasses source rate selection and is labeled as such",
    )
    language: str = "en"
    jurisdiction: str = "india"
    user_query: str | None = None


class NbaAbsResponse(BaseModel):
    product: str
    ingredients: list[str]
    jurisdiction: str
    purpose: AbsPurpose
    entity_type: EntityType
    resource_source: ResourceSource
    annual_turnover_inr: float | None = None
    botanicals: list[BotanicalResult] = Field(default_factory=list)
    applicability: AbsApplicability | None = None
    rate_selection: AbsRateSelection | None = None
    calculation: AbsFeeCalculation | None = None
    verification: VerificationResult | None = None
    retrieved_sources: list[RetrievedSource] = Field(default_factory=list)
    final_answer: str | None = None
    disclaimer: str = (
        "AyurDisha provides decision support only and is not legal advice. "
        "Fee arithmetic is deterministic; the applicable rate must be confirmed "
        "against the currently notified ABS regulations and the competent authority."
    )
