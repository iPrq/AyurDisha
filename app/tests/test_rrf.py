"""Reciprocal Rank Fusion."""

from __future__ import annotations

import pytest

from retrieval.qdrant_hybrid import reciprocal_rank_fusion


def test_rrf_scores():
    fused = dict(reciprocal_rank_fusion([["a", "b"], ["b", "c"]], k=60))
    assert fused["a"] == pytest.approx(1 / 61)
    assert fused["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert fused["c"] == pytest.approx(1 / 62)


def test_rrf_both_rankings_contribute_and_order():
    fused = reciprocal_rank_fusion([["a", "b"], ["b", "c"]], k=60)
    assert [d for d, _ in fused] == ["b", "a", "c"]


def test_rrf_deduplicates():
    fused = reciprocal_rank_fusion([["a", "a", "b"], ["a"]], k=60)
    ids = [d for d, _ in fused]
    assert ids == ["a", "b"]
    assert dict(fused)["a"] == pytest.approx(2 / 61)


def test_rrf_ties_are_deterministic():
    first = reciprocal_rank_fusion([["z", "y"], ["y", "z"]], k=60)
    second = reciprocal_rank_fusion([["y", "z"], ["z", "y"]], k=60)
    assert [d for d, _ in first] == [d for d, _ in second] == ["y", "z"]


def test_rrf_empty():
    assert reciprocal_rank_fusion([[], []]) == []
