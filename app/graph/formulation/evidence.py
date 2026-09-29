"""Verify formulation-map claims with the shared critic verifier and attach traceable evidence.

A relation only becomes an authoritative graph fact when the verifier marks it supported AND cites
at least one retrieved source that was a candidate for that claim.
"""

from __future__ import annotations

import logging
from typing import Any

from config import Settings
from graph.formulation.context_retrieval import unique_sources
from graph.formulation.graph_builder import GraphClaim
from graph.formulation.models import (
    EvidenceItem,
    FGEdge,
    FGEdgeType,
    FGNode,
    FGNodeType,
    FormulationGraph,
    IdentityStatus,
    WhyItMatters,
)
from graph.models import ClaimSupportStatus, EvidenceKind, RetrievedSource
from graph.shared.verifier import verify_claims

logger = logging.getLogger(__name__)

_SUPPORTED = {ClaimSupportStatus.SUPPORTED, ClaimSupportStatus.PARTIALLY_SUPPORTED}


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split()).rstrip(".")


def verify_graph(
    graph: FormulationGraph,
    claims: list[GraphClaim],
    pairs: list[tuple[str, RetrievedSource]],
    *,
    settings: Settings | None = None,
    llm: Any | None = None,
) -> FormulationGraph:
    nodes = {n.id: n for n in graph.nodes}
    branch_of: dict[str, str] = {}
    for branch, src in pairs:
        branch_of.setdefault(src.id, branch)
    candidate_ids = {i for c in claims for i in c.candidate_source_ids}
    sources = [s for s in unique_sources(pairs) if s.id in candidate_ids]

    verdicts: dict[str, tuple[ClaimSupportStatus, list[str]]] = {}
    verification = None
    verifier_ran = False
    if claims and (llm is not None or not sources):
        try:
            verification = verify_claims(
                [c.claim for c in claims], sources, settings=settings, llm=llm
            )
            verifier_ran = True
            by_text = {_norm(v.claim): v for v in verification.claims}
            stripped = {_norm(s) for s in verification.stripped_unsupported_claims}
            for c in claims:
                v = by_text.get(_norm(c.claim))
                if v is None or _norm(c.claim) in stripped:
                    verdicts[c.id] = (ClaimSupportStatus.UNSUPPORTED, [])
                    continue
                ids = [i for i in v.evidence_source_ids if i in c.candidate_source_ids]
                verdicts[c.id] = (v.status, ids)
        except Exception:  # noqa: BLE001 - verifier outage leaves claims unverified, never supported
            logger.warning("formulation verifier failed; claims left unverified", exc_info=True)

    node_support: dict[str, list[ClaimSupportStatus]] = {}
    source_support: dict[str, list[tuple[str, ClaimSupportStatus]]] = {}
    for c in claims:
        status, ids = verdicts.get(c.id, (None, []))
        traceable = status in _SUPPORTED and bool(ids)
        for node_id in c.node_ids:
            node = nodes.get(node_id)
            if node is None:
                continue
            node.why_it_matters = node.why_it_matters or WhyItMatters()
            if traceable:
                node_support.setdefault(node_id, []).append(status)
                node.evidence_ids = list(dict.fromkeys([*node.evidence_ids, *ids]))
                if c.claim not in node.why_it_matters.facts:
                    node.why_it_matters.facts.append(c.claim)
            else:
                node_support.setdefault(node_id, []).append(ClaimSupportStatus.UNSUPPORTED)
                reason = (
                    "not verified (verifier unavailable)"
                    if not verifier_ran
                    else "not supported by retrieved sources"
                )
                note = f"Unverified — {reason}: {c.claim}"
                if note not in node.why_it_matters.uncertainty:
                    node.why_it_matters.uncertainty.append(note)
        if traceable:
            for sid in ids:
                source_support.setdefault(sid, []).append((c.claim, status))

    for node_id, statuses in node_support.items():
        node = nodes[node_id]
        supported = [s for s in statuses if s in _SUPPORTED]
        if not supported:
            node.status = IdentityStatus.INSUFFICIENT_EVIDENCE
            node.evidence_kind = EvidenceKind.UNCERTAINTY
        elif len(supported) == len(statuses) and all(s == ClaimSupportStatus.SUPPORTED for s in supported):
            node.status = IdentityStatus.CONFIRMED
            node.evidence_kind = EvidenceKind.FACT_FROM_SOURCE
        else:
            node.status = IdentityStatus.PROBABLE
            node.evidence_kind = EvidenceKind.FACT_FROM_SOURCE

    evidence: list[EvidenceItem] = []
    for src in unique_sources(pairs):
        support = source_support.get(src.id, [])
        if support:
            vstatus = (
                "SUPPORTED"
                if any(s == ClaimSupportStatus.SUPPORTED for _, s in support)
                else "PARTIALLY_SUPPORTED"
            )
        else:
            vstatus = "UNSUPPORTED" if verifier_ran and src.id in candidate_ids else "NOT_VERIFIED"
        evidence.append(
            EvidenceItem(
                source=src,
                branch=branch_of.get(src.id, "unknown"),
                supports=[claim for claim, _ in support],
                verifier_status=vstatus,
            )
        )

    new_nodes: list[FGNode] = []
    new_edges: list[FGEdge] = []
    for item in evidence:
        if not item.supports:
            continue
        ev_id = f"ev:{item.source.id}"
        new_nodes.append(
            FGNode(
                id=ev_id,
                type=FGNodeType.EVIDENCE,
                label=item.source.title[:80],
                sublabel=" · ".join(
                    x for x in [item.source.source_type, (item.source.jurisdiction or "").upper()] if x
                ),
                layer=11,
                branch="evidence",
                status=IdentityStatus.CONFIRMED if item.verifier_status == "SUPPORTED" else IdentityStatus.PROBABLE,
                evidence_ids=[item.source.id],
                evidence_kind=EvidenceKind.FACT_FROM_SOURCE,
                ref=item.source.id,
            )
        )
        for node in graph.nodes:
            if item.source.id in node.evidence_ids:
                new_edges.append(
                    FGEdge(
                        id=f"{node.id}->{ev_id}:supported_by",
                        source=node.id,
                        target=ev_id,
                        type=FGEdgeType.SUPPORTED_BY,
                        evidence_ids=[item.source.id],
                    )
                )

    graph.nodes = [*graph.nodes, *new_nodes]
    graph.edges = [*graph.edges, *new_edges]
    graph.evidence = evidence
    graph.verification = verification
    return graph
