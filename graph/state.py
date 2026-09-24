"""LangGraph state for Section 3 & Patent Advisor."""

from __future__ import annotations

from typing import TypedDict

from typing_extensions import NotRequired

from graph.models import (
    BotanicalResult,
    IPRouteAnalysis,
    LegalScope,
    PatentabilityRiskIndicator,
    PriorArtResult,
    RetrievedSource,
    Section3Results,
    VerificationOutcome,
    VerificationResult,
)


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
