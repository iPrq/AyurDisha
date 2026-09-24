"""Tests for Critic Verifier (scripted LLM, no paid API)."""

from __future__ import annotations

from graph.models import (
    BotanicalResult,
    BotanicalStatus,
    ClaimSupportStatus,
    LegalScope,
    RetrievedSource,
    Section3Clause,
    Section3ProvisionResult,
    Section3Results,
    VerificationOutcome,
)
from graph.shared.verifier import critic_verifier_node, verify_claims


def _src(text: str, sid: str = "s1") -> RetrievedSource:
    return RetrievedSource(
        id=sid,
        title="fixture",
        text=text,
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
        is_fixture=True,
    )


def test_missing_sources_human_review():
    result = verify_claims(["Any claim"], [], llm=None)
    assert result.outcome == VerificationOutcome.HUMAN_REVIEW_REQUIRED
    assert "missing_evidence" in result.escalation_reasons


def test_verify_with_scripted_llm(scripted_llm):
    sources = [_src("Section 3(d) known substance efficacy.", "fixture-in-s3d")]
    result = verify_claims(
        ["Section 3(d) known substance"],
        sources,
        llm=scripted_llm,
    )
    assert result.outcome in {
        VerificationOutcome.PASS,
        VerificationOutcome.HUMAN_REVIEW_REQUIRED,
        VerificationOutcome.FAIL,
    }
    assert result.claims


def test_node_ambiguous_botanical_escalates(scripted_llm):
    state = {
        "product": "x",
        "ingredients": ["ginseng"],
        "language": "en",
        "jurisdiction": "india",
        "legal_scope": "domestic",
        "botanical": BotanicalResult(
            status=BotanicalStatus.AMBIGUOUS,
            input_term="ginseng",
            candidates=[],
        ),
        "retrieved_sources": [
            _src("Section 3(e) mere admixture.", "fixture-in-s3e")
        ],
        "section3": Section3Results(
            provisions=[
                Section3ProvisionResult(
                    clause=Section3Clause.E,
                    triggered=True,
                    reason="Section 3(e) mere admixture.",
                    evidence_source_ids=["fixture-in-s3e"],
                )
            ],
            summary="Section 3(e) mere admixture.",
        ),
        "final_answer": "Section 3(e) mere admixture.",
        "escalation_reasons": ["ambiguous_botanical"],
    }
    update = critic_verifier_node(state, llm=scripted_llm)  # type: ignore[arg-type]
    assert update["verification_status"] == VerificationOutcome.HUMAN_REVIEW_REQUIRED.value
    assert "ambiguous_botanical" in update["escalation_reasons"]
