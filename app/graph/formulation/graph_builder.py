"""Deterministic formulation-map construction from structured context + retrieved sources.

The LLM never proposes nodes here. Relations that assert facts are emitted as ``GraphClaim``s and
start as unverified; ``evidence.verify_graph`` promotes or downgrades them via the shared verifier.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from graph.formulation.context_retrieval import sources_by_branch
from graph.formulation.models import (
    FGEdge,
    FGEdgeType,
    FGNode,
    FGNodeType,
    FormulationContext,
    FormulationGraph,
    IdentityStatus,
    WhyItMatters,
)
from graph.models import EvidenceKind, RetrievedSource


class GraphClaim(BaseModel):
    id: str
    claim: str
    branch: str
    node_ids: list[str] = Field(default_factory=list)
    candidate_source_ids: list[str] = Field(default_factory=list)


BIO_RESOURCE_CLAIM = "Plants and plant parts are biological resources under the Biological Diversity Act, 2002."
REGULATORY_CLAIM = (
    "Manufacture of Ayurvedic drugs for sale in India requires a licence under the Drugs and Cosmetics Act, 1940."
)
ABS_CLAIM = (
    "Obtaining biological resources occurring in India for commercial utilization requires prior "
    "intimation or approval under the Biological Diversity Act."
)


def tk_claim(botanical: str) -> str:
    return f"{botanical} is described in Ayurvedic pharmacopoeial or classical formulary texts."


def prior_art_claim(botanical: str) -> str:
    return f"Patent documents disclose compositions containing {botanical}."


def _qty(q: float | None, unit: str | None) -> str | None:
    if q is None:
        return None
    return f"{int(q) if float(q).is_integer() else q} {unit or ''}".strip()


class _Builder:
    def __init__(self) -> None:
        self.nodes: dict[str, FGNode] = {}
        self.edges: list[FGEdge] = []
        self.claims: list[GraphClaim] = []

    def node(self, node: FGNode) -> FGNode:
        self.nodes[node.id] = node
        return node

    def edge(self, source: str, target: str, type_: FGEdgeType, status: IdentityStatus | None = None) -> None:
        if source in self.nodes and target in self.nodes:
            self.edges.append(
                FGEdge(id=f"{source}->{target}:{type_.value}", source=source, target=target, type=type_, status=status)
            )

    def claim(self, text: str, branch: str, node_ids: list[str], sources: list[RetrievedSource]) -> None:
        for existing in self.claims:
            if existing.claim == text:
                existing.node_ids = list(dict.fromkeys([*existing.node_ids, *node_ids]))
                return
        self.claims.append(
            GraphClaim(
                id=f"c{len(self.claims) + 1}",
                claim=text,
                branch=branch,
                node_ids=node_ids,
                candidate_source_ids=[s.id for s in sources],
            )
        )


def _identity_evidence_kind(ing) -> EvidenceKind | None:
    notes = (ing.identity_notes or "").lower()
    if ing.resolved_by_user:
        return None
    if "knowledge graph" in notes:
        return EvidenceKind.FACT_FROM_SOURCE
    return EvidenceKind.MODEL_INTERPRETATION


def build_graph(
    ctx: FormulationContext,
    pairs: list[tuple[str, RetrievedSource]],
    *,
    empty_branches: list[str] | None = None,
) -> tuple[FormulationGraph, list[GraphClaim]]:
    b = _Builder()
    by_branch = sources_by_branch(pairs)
    empty = set(empty_branches or [])
    chars = {c.key: c for c in ctx.formulation_characteristics}

    b.node(
        FGNode(
            id="formulation",
            type=FGNodeType.FORMULATION,
            label=ctx.name or "Untitled formulation",
            sublabel=f"Version {ctx.version}" + (" · confirmed" if ctx.confirmed else " · draft"),
            layer=0,
            status=IdentityStatus.CONFIRMED if ctx.confirmed else IdentityStatus.PROBABLE,
        )
    )
    comp = chars.get("composition_type")
    b.node(
        FGNode(
            id="composition",
            type=FGNodeType.COMPOSITION,
            label="Composition",
            sublabel=comp.value if comp else "No ingredients yet",
            layer=1,
            evidence_kind=EvidenceKind.CALCULATION,
            status=IdentityStatus.CONFIRMED if ctx.ingredients else IdentityStatus.INSUFFICIENT_EVIDENCE,
        )
    )
    b.edge("formulation", "composition", FGEdgeType.CONTAINS)

    if ctx.dosage_form:
        b.node(FGNode(id="dosage_form", type=FGNodeType.DOSAGE_FORM, label=ctx.dosage_form.title(),
                      sublabel="Dosage form", layer=1, status=IdentityStatus.CONFIRMED))
        b.edge("formulation", "dosage_form", FGEdgeType.CLASSIFIED_AS)
    if ctx.route:
        b.node(FGNode(id="route", type=FGNodeType.ROUTE, label=ctx.route.title(), sublabel="Route",
                      layer=1, status=IdentityStatus.CONFIRMED))
        b.edge("formulation", "route", FGEdgeType.RELEVANT_TO)
    if ctx.intended_use:
        b.node(FGNode(id="intended_use", type=FGNodeType.INTENDED_USE, label=ctx.intended_use,
                      sublabel="Intended use", layer=1, status=IdentityStatus.CONFIRMED))
        b.edge("formulation", "intended_use", FGEdgeType.USED_FOR)
    else:
        b.node(
            FGNode(
                id="intended_use_missing",
                type=FGNodeType.UNCERTAINTY,
                label="Intended use not stated",
                layer=1,
                status=IdentityStatus.INSUFFICIENT_EVIDENCE,
                why_it_matters=WhyItMatters(
                    interpretation=["Intended use and claims influence the regulatory category and advertising limits."],
                    uncertainty=["No intended use has been provided."],
                ),
            )
        )
        b.edge("formulation", "intended_use_missing", FGEdgeType.REQUIRES_REVIEW)

    bio_ids: list[str] = []
    resolved_names: list[str] = []
    for ing in ctx.ingredients:
        ing_id = f"ing:{ing.id}"
        b.node(
            FGNode(
                id=ing_id,
                type=FGNodeType.INGREDIENT,
                label=ing.user_term,
                sublabel=_qty(ing.quantity, ing.unit) or "quantity not stated",
                layer=2,
                status=ing.identity_status,
                ref=ing.id,
            )
        )
        b.edge("composition", ing_id, FGEdgeType.CONTAINS)
        if ing.botanical_name and ing.identity_status in (IdentityStatus.CONFIRMED, IdentityStatus.PROBABLE):
            resolved_names.append(ing.botanical_name)
            bot_id = f"bot:{ing.id}"
            kind = _identity_evidence_kind(ing)
            origin = (
                "selected by the user from normalizer candidates"
                if ing.resolved_by_user
                else ("resolved from the botanical knowledge graph" if kind == EvidenceKind.FACT_FROM_SOURCE
                      else "proposed by the botanical normalizer model")
            )
            b.node(
                FGNode(
                    id=bot_id,
                    type=FGNodeType.BOTANICAL_IDENTITY,
                    label=ing.botanical_name,
                    sublabel=", ".join(ing.synonyms[:3]) or "Botanical identity",
                    layer=3,
                    status=ing.identity_status,
                    evidence_kind=kind,
                    ref=ing.id,
                    why_it_matters=WhyItMatters(
                        facts=[f"“{ing.user_term}” was {origin} as {ing.botanical_name}."]
                        if kind == EvidenceKind.FACT_FROM_SOURCE else [],
                        interpretation=[
                            "Downstream retrieval uses this canonical name instead of the vernacular term."
                        ] + ([f"Identity {origin}."] if kind != EvidenceKind.FACT_FROM_SOURCE else []),
                        uncertainty=[] if ing.identity_status == IdentityStatus.CONFIRMED
                        else ["Identity confidence is below the confirmation threshold."],
                    ),
                )
            )
            b.edge(ing_id, bot_id, FGEdgeType.IDENTIFIED_AS, ing.identity_status)

            part_id = f"part:{ing.id}"
            b.node(
                FGNode(
                    id=part_id,
                    type=FGNodeType.PLANT_PART,
                    label=ing.plant_part.title() if ing.plant_part else "Plant part not stated",
                    sublabel="Plant part",
                    layer=4,
                    status=IdentityStatus.CONFIRMED if ing.plant_part else IdentityStatus.INSUFFICIENT_EVIDENCE,
                    ref=ing.id,
                    why_it_matters=None if ing.plant_part else WhyItMatters(
                        interpretation=["Plant part can change pharmacopoeial monographs and prior-art relevance."],
                        uncertainty=["Plant part was not provided and is not inferred."],
                    ),
                )
            )
            b.edge(part_id, bot_id, FGEdgeType.PART_OF)

            bio_id = f"bio:{ing.id}"
            bio_ids.append(bio_id)
            uncertainty = []
            if ctx.resource_source is None or ctx.resource_source.value == "unknown":
                uncertainty.append("Source (wild or cultivated) is not known.")
            if ctx.purpose is None:
                uncertainty.append("Purpose of use is not known.")
            b.node(
                FGNode(
                    id=bio_id,
                    type=FGNodeType.BIOLOGICAL_RESOURCE,
                    label="Biological resource",
                    sublabel=ing.botanical_name,
                    layer=4,
                    branch="abs",
                    status=IdentityStatus.PROBABLE,
                    ref=ing.id,
                    why_it_matters=WhyItMatters(
                        interpretation=[
                            "This ingredient has been identified as a biological resource. Its presence may "
                            "affect the biodiversity/ABS assessment depending on purpose, source and "
                            "applicable framework."
                        ],
                        uncertainty=uncertainty,
                    ),
                )
            )
            b.edge(bot_id, bio_id, FGEdgeType.CLASSIFIED_AS)
            b.claim(BIO_RESOURCE_CLAIM, "abs", [bio_id], by_branch.get("abs", []))
        else:
            unc_id = f"unc:{ing.id}"
            ambiguous = ing.identity_status == IdentityStatus.AMBIGUOUS
            cands = [c.botanical_name for c in ing.candidates]
            b.node(
                FGNode(
                    id=unc_id,
                    type=FGNodeType.UNCERTAINTY,
                    label="Ambiguous identity" if ambiguous else "Identity not resolved",
                    sublabel=", ".join(cands) if cands else (ing.identity_notes or None),
                    layer=3,
                    status=ing.identity_status,
                    ref=ing.id,
                    why_it_matters=WhyItMatters(
                        interpretation=[
                            "Retrieval, patent and ABS analysis need a single botanical identity; "
                            "this ingredient is excluded from them until resolved."
                        ],
                        uncertainty=[
                            f"“{ing.user_term}” matches multiple candidates: {', '.join(cands)}. "
                            "No candidate has been chosen."
                        ] if ambiguous else [ing.identity_notes or "No botanical identity found."],
                    ),
                )
            )
            b.edge(ing_id, unc_id, FGEdgeType.REQUIRES_REVIEW, ing.identity_status)

    b.node(
        FGNode(
            id="characteristics",
            type=FGNodeType.CHARACTERISTIC,
            label="Formulation characteristics",
            sublabel=" · ".join(c.value for c in ctx.formulation_characteristics[:2]) or None,
            layer=5,
            evidence_kind=EvidenceKind.CALCULATION,
            status=IdentityStatus.CONFIRMED if ctx.formulation_characteristics else IdentityStatus.INSUFFICIENT_EVIDENCE,
            why_it_matters=WhyItMatters(
                facts=[f"{c.label}: {c.value}" for c in ctx.formulation_characteristics],
            ),
        )
    )
    b.edge("composition", "characteristics", FGEdgeType.DERIVED_FROM)

    b.node(
        FGNode(
            id="classification",
            type=FGNodeType.CLASSIFICATION,
            label="Classification context",
            sublabel=" · ".join(x for x in [ctx.dosage_form, comp.value if comp else None] if x) or None,
            layer=6,
            evidence_kind=EvidenceKind.CALCULATION,
            status=IdentityStatus.CONFIRMED if ctx.dosage_form else IdentityStatus.INSUFFICIENT_EVIDENCE,
            why_it_matters=WhyItMatters(
                interpretation=[
                    "Dosage form, composition and intended use are the inputs the regulatory category depends on."
                ],
                uncertainty=["The regulatory category itself is not determined here — Product Review assesses it."],
            ),
        )
    )
    b.edge("characteristics", "classification", FGEdgeType.CLASSIFIED_AS)

    # Regulatory branch
    b.node(
        FGNode(
            id="regulatory",
            type=FGNodeType.REGULATORY,
            label="Regulatory context",
            sublabel="Product Review → Legal Compliance",
            layer=7,
            branch="regulatory",
            status=IdentityStatus.PROBABLE,
            why_it_matters=WhyItMatters(
                interpretation=["Licensing, GMP and claim limits may apply depending on the product category."],
                uncertainty=["No regulatory sources retrieved."] if "regulatory" in empty else [],
            ),
        )
    )
    b.edge("classification", "regulatory", FGEdgeType.MAY_TRIGGER)
    b.claim(REGULATORY_CLAIM, "regulatory", ["regulatory"], by_branch.get("regulatory", []))

    # Patent branch: characteristics -> TK -> Section 3 -> prior art -> IP routes
    b.node(
        FGNode(
            id="traditional_knowledge",
            type=FGNodeType.TRADITIONAL_KNOWLEDGE,
            label="Traditional knowledge",
            sublabel="Pharmacopoeia / formulary texts",
            layer=7,
            branch="patent",
            status=IdentityStatus.PROBABLE if resolved_names else IdentityStatus.INSUFFICIENT_EVIDENCE,
            why_it_matters=WhyItMatters(
                interpretation=[
                    "Documented traditional use of the ingredients may be relevant to Section 3(p) "
                    "(traditional knowledge) in Patent Advisor's analysis."
                ],
                uncertainty=["No traditional-knowledge sources retrieved."] if "traditional_knowledge" in empty else [],
            ),
        )
    )
    b.edge("characteristics", "traditional_knowledge", FGEdgeType.RELEVANT_TO)
    for name in resolved_names:
        b.claim(tk_claim(name), "traditional_knowledge", ["traditional_knowledge"],
                by_branch.get("traditional_knowledge", []))

    b.node(
        FGNode(
            id="section3",
            type=FGNodeType.PATENT,
            label="Section 3 (Patents Act)",
            sublabel="Not determined here — Patent Advisor",
            layer=8,
            branch="patent",
            status=None,
            why_it_matters=WhyItMatters(
                interpretation=["Section 3 exclusions (e.g. 3(d), 3(e), 3(p)) are evaluated by Patent Advisor against statute text."],
                uncertainty=["No Section 3 determination has been made for this formulation."],
            ),
        )
    )
    b.edge("traditional_knowledge", "section3", FGEdgeType.MAY_TRIGGER)

    patent_sources = by_branch.get("patent", [])
    juris = sorted({(s.jurisdiction or "?").upper() for s in patent_sources})
    b.node(
        FGNode(
            id="prior_art",
            type=FGNodeType.PRIOR_ART,
            label="Prior art",
            sublabel=" · ".join(juris) if juris else "No patent documents retrieved",
            layer=9,
            branch="patent",
            status=IdentityStatus.PROBABLE if patent_sources else IdentityStatus.INSUFFICIENT_EVIDENCE,
            why_it_matters=WhyItMatters(
                interpretation=["Similar disclosures are relevant to novelty; similarity is not a legal conclusion."],
                uncertainty=["No patent documents retrieved."] if not patent_sources else [],
            ),
        )
    )
    b.edge("section3", "prior_art", FGEdgeType.RELEVANT_TO)
    for name in resolved_names:
        b.claim(prior_art_claim(name), "patent", ["prior_art"], patent_sources)

    b.node(
        FGNode(id="ip_routes", type=FGNodeType.PATENT, label="IP routes", sublabel="Patent Advisor",
               layer=10, branch="patent", status=None)
    )
    b.edge("prior_art", "ip_routes", FGEdgeType.LEADS_TO)

    # ABS branch
    abs_uncertainty = []
    if ctx.purpose is None:
        abs_uncertainty.append("Purpose of use is unknown — required for ABS applicability.")
    if ctx.entity_type is None:
        abs_uncertainty.append("Entity type (Indian / foreign) is unknown.")
    b.node(
        FGNode(
            id="abs",
            type=FGNodeType.ABS,
            label="ABS / Biodiversity",
            sublabel="NBA / ABS calculator",
            layer=7,
            branch="abs",
            status=IdentityStatus.PROBABLE if bio_ids else IdentityStatus.INSUFFICIENT_EVIDENCE,
            why_it_matters=WhyItMatters(
                interpretation=["ABS applicability depends on purpose, entity type and resource source; the calculator decides from sources."],
                uncertainty=abs_uncertainty,
            ),
        )
    )
    for bio_id in bio_ids:
        b.edge(bio_id, "abs", FGEdgeType.MAY_TRIGGER)
    if bio_ids:
        b.claim(ABS_CLAIM, "abs", ["abs"], by_branch.get("abs", []))

    # Next actions
    actions = [
        ("action:review", "Review Product", "RUN_PRODUCT_REVIEW", "regulatory"),
        ("action:patent", "Analyze Patent", "RUN_PATENT_ADVISOR", "ip_routes"),
        ("action:abs", "Check ABS", "RUN_ABS", "abs"),
    ]
    for node_id, label, action_type, parent in actions:
        b.node(FGNode(id=node_id, type=FGNodeType.ACTION, label=label, layer=12, branch="action", ref=action_type))
        b.edge(parent, node_id, FGEdgeType.LEADS_TO)
    for ing in ctx.ingredients:
        if ing.identity_status == IdentityStatus.AMBIGUOUS:
            node_id = f"action:resolve:{ing.id}"
            b.node(FGNode(id=node_id, type=FGNodeType.ACTION, label=f"Resolve {ing.user_term}", layer=12,
                          branch="action", ref="RESOLVE_ENTITY", status=IdentityStatus.AMBIGUOUS))
            b.edge(f"unc:{ing.id}", node_id, FGEdgeType.LEADS_TO)

    graph = FormulationGraph(
        formulation_id=ctx.formulation_id,
        version=ctx.version,
        nodes=list(b.nodes.values()),
        edges=b.edges,
    )
    return graph, b.claims
