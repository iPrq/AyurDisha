"""LangGraph state for Section 3 & Patent Advisor."""

from __future__ import annotations

from typing import Annotated, TypedDict

from typing_extensions import NotRequired

from graph.models import (
    AbsApplicability,
    AbsFeeCalculation,
    AbsPurpose,
    AbsRateSelection,
    BotanicalResult,
    EntityType,
    IPRouteAnalysis,
    LegalComplianceAssessment,
    LegalScope,
    MarketFeasibilityAssessment,
    PatentabilityRiskIndicator,
    PriorArtResult,
    ResourceAccessibilityAssessment,
    ResourceSource,
    RetrievedSource,
    Section3Results,
    VerificationOutcome,
    VerificationResult,
)


def merge_unique(left: list[str] | None, right: list[str] | None) -> list[str]:
    """Order-preserving union — lets parallel branches each add escalation reasons."""
    out: list[str] = []
    for item in [*(left or []), *(right or [])]:
        if item and item not in out:
            out.append(item)
    return out


class PatentAdvisorState(TypedDict):
    """Shared state for the Patent Advisor LangGraph workflow.

    Nodes receive this state and return partial updates.
    List fields use last-write-wins (no append reducers in Phase 2).
    """

    # Request / input
    product: str
    ingredients: list[str]
    language: str
    jurisdiction: str
    legal_scope: LegalScope | str
    user_query: NotRequired[str]
    # Uploaded disclosure text (prompt context only, never evidence)
    document_text: NotRequired[str]

    # Parsed / normalized input (InputParser)
    botanical_input: NotRequired[str]
    parsed_notes: NotRequired[str]

    # Botanical Normalizer
    botanical: NotRequired[BotanicalResult]
    botanical_name: NotRequired[str]
    botanical_synonyms: NotRequired[list[str]]
    phytochemicals: NotRequired[list[str]]
    botanical_confidence: NotRequired[float]
    botanical_status: NotRequired[str]

    # Retrieval (jurisdiction / legal_scope filtered)
    retrieved_sources: NotRequired[list[RetrievedSource]]
    retrieval_insufficient: NotRequired[bool]

    # Section 3 + risk
    section3: NotRequired[Section3Results]
    patentability_risk: NotRequired[PatentabilityRiskIndicator]
    patentability_risk_score: NotRequired[float]

    # Prior art + IP pathways
    prior_art: NotRequired[PriorArtResult]
    ip_routes: NotRequired[IPRouteAnalysis]

    # Critic verifier
    verification: NotRequired[VerificationResult]
    verification_status: NotRequired[VerificationOutcome | str]
    escalation_reasons: NotRequired[list[str]]

    # Control / output
    retry_count: NotRequired[int]
    final_answer: NotRequired[str]
    error: NotRequired[str]


class ProductReviewState(TypedDict):
    """State for Product Review. Market / legal / resource nodes run in parallel,
    so each writes its own keys; ``escalation_reasons`` merges via reducer."""

    product: str
    ingredients: list[str]
    language: str
    jurisdiction: str
    legal_scope: LegalScope | str
    target_market: NotRequired[str]
    product_category: NotRequired[str]
    user_query: NotRequired[str]

    botanical_input: NotRequired[str]
    parsed_notes: NotRequired[str]

    botanicals: NotRequired[list[BotanicalResult]]
    botanical: NotRequired[BotanicalResult]
    botanical_name: NotRequired[str]
    botanical_status: NotRequired[str]

    market_sources: NotRequired[list[RetrievedSource]]
    legal_sources: NotRequired[list[RetrievedSource]]
    resource_sources: NotRequired[list[RetrievedSource]]
    market_feasibility: NotRequired[MarketFeasibilityAssessment]
    legal_compliance: NotRequired[LegalComplianceAssessment]
    resource_accessibility: NotRequired[ResourceAccessibilityAssessment]

    retrieved_sources: NotRequired[list[RetrievedSource]]
    retrieval_insufficient: NotRequired[bool]
    combined_summary: NotRequired[str]

    verification: NotRequired[VerificationResult]
    verification_status: NotRequired[VerificationOutcome | str]
    escalation_reasons: Annotated[list[str], merge_unique]

    retry_count: NotRequired[int]
    final_answer: NotRequired[str]
    error: NotRequired[str]


class NbaAbsState(TypedDict):
    """State for the NBA / ABS calculator workflow."""

    product: str
    ingredients: list[str]
    language: str
    jurisdiction: str
    legal_scope: NotRequired[LegalScope | str]
    purpose: AbsPurpose | str
    entity_type: EntityType | str
    resource_source: ResourceSource | str
    annual_turnover_inr: NotRequired[float]
    percentage_override: NotRequired[float]
    user_query: NotRequired[str]

    botanical_input: NotRequired[str]
    parsed_notes: NotRequired[str]

    botanicals: NotRequired[list[BotanicalResult]]
    botanical: NotRequired[BotanicalResult]
    botanical_name: NotRequired[str]
    botanical_status: NotRequired[str]

    applicability_sources: NotRequired[list[RetrievedSource]]
    rate_sources: NotRequired[list[RetrievedSource]]
    applicability: NotRequired[AbsApplicability]
    rate_selection: NotRequired[AbsRateSelection]
    calculation: NotRequired[AbsFeeCalculation]

    retrieved_sources: NotRequired[list[RetrievedSource]]
    retrieval_insufficient: NotRequired[bool]

    verification: NotRequired[VerificationResult]
    verification_status: NotRequired[VerificationOutcome | str]
    escalation_reasons: Annotated[list[str], merge_unique]

    retry_count: NotRequired[int]
    final_answer: NotRequired[str]
    error: NotRequired[str]
