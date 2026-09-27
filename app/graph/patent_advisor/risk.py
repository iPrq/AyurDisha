"""Deterministic Section 3 patentability risk indicator."""

from __future__ import annotations

from config import Settings, get_settings
from graph.models import (
    PatentabilityRiskIndicator,
    Section3Clause,
    Section3ProvisionResult,
    Section3Results,
)


def calculate_patentability_risk(
    section3: Section3Results,
    *,
    settings: Settings | None = None,
) -> PatentabilityRiskIndicator:
    """Rule-based risk = sum of weights for triggered 3(d)/3(e)/3(p).

    Each clause counts at most once. Triggered clauses without a configured weight
    add nothing (no weights are invented) and are listed in
    ``unweighted_triggered_clauses``.

    This is decision-support only — not a probability of patent approval.
    """
    cfg = settings or get_settings()
    weights = {
        Section3Clause.D: cfg.section3_weight_d,
        Section3Clause.E: cfg.section3_weight_e,
        Section3Clause.P: cfg.section3_weight_p,
    }

    score = 0.0
    triggered: list[Section3Clause] = []
    unweighted: list[Section3Clause] = []
    for provision in section3.provisions:
        clause = provision.clause
        if isinstance(clause, str):
            clause = Section3Clause(clause)
        if provision.triggered and clause not in triggered:
            triggered.append(clause)
            if clause in weights:
                score += weights[clause]
            else:
                unweighted.append(clause)

    # Cap at 1.0 in case weights are misconfigured above 1 combined
    score = min(1.0, max(0.0, score))

    return PatentabilityRiskIndicator(
        score=score,
        triggered_clauses=triggered,
        unweighted_triggered_clauses=unweighted,
        weight_d=cfg.section3_weight_d,
        weight_e=cfg.section3_weight_e,
        weight_p=cfg.section3_weight_p,
    )


def provisions_by_clause(
    provisions: list[Section3ProvisionResult],
) -> dict[Section3Clause, Section3ProvisionResult]:
    out: dict[Section3Clause, Section3ProvisionResult] = {}
    for p in provisions:
        clause = p.clause if isinstance(p.clause, Section3Clause) else Section3Clause(p.clause)
        out[clause] = p
    return out
