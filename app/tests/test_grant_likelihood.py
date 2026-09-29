"""Tests for the LLM grant-likelihood estimate (scripted LLM)."""

from __future__ import annotations

import pytest

from graph.models import GrantLikelihoodEstimate, RetrievedSource
from graph.patent_advisor.grant_likelihood import estimate_grant_likelihood
from tests.conftest import ScriptedLLM

SOURCES = [
    RetrievedSource(id="src-a", title="A", text="Section 3(d) guidance."),
    RetrievedSource(id="src-b", title="B", text="Traditional knowledge 3(p)."),
]


def test_no_sources_skips_llm_call():
    result = estimate_grant_likelihood([], llm=None)
    assert result.insufficient_evidence
    assert result.probability is None
    assert result.label == "llm_estimated_grant_probability"


def test_filters_invalid_source_ids():
    llm = ScriptedLLM(
        {
            "GrantLikelihoodEstimate": GrantLikelihoodEstimate(
                probability=0.4,
                confidence="medium",
                evidence_source_ids=["src-a", "made-up-id"],
            )
        }
    )
    result = estimate_grant_likelihood(SOURCES, llm=llm)
    assert llm.calls == ["GrantLikelihoodEstimate"]
    assert result.evidence_source_ids == ["src-a"]
    assert result.probability == pytest.approx(0.4)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(-0.5, 0.0), (62, 0.62), (250, 1.0), (0.8, 0.8)],
)
def test_clamps_probability(raw, expected):
    llm = ScriptedLLM(
        {"GrantLikelihoodEstimate": {"probability": raw, "confidence": "HIGH"}}
    )
    result = estimate_grant_likelihood(SOURCES, llm=llm)
    assert result.probability == pytest.approx(expected)
    assert result.confidence == "high"
