"""Knowledge-graph data model shared by the Neo4j and in-memory stores."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

# Node labels (whitelisted — Cypher labels cannot be parameterized).
HERB = "Herb"
COMPOUND = "Compound"
FORMULATION = "Formulation"
PRODUCT = "Product"
DOCUMENT = "Document"
PATENT = "Patent"
SOURCE = "Source"
NAME = "Name"  # vernacular term a user typed (possibly ambiguous)
INGREDIENT = "Ingredient"  # classical ingredient without a resolved botanical name
CATEGORY = "Category"

NODE_LABELS = frozenset(
    {HERB, COMPOUND, FORMULATION, PRODUCT, DOCUMENT, PATENT, SOURCE, NAME, INGREDIENT, CATEGORY}
)

# Relationship types.
CONTAINS = "CONTAINS"  # Herb -> Compound
INGREDIENT_OF = "INGREDIENT_OF"  # Herb | Formulation -> Formulation | Product
MENTIONED_IN = "MENTIONED_IN"  # Herb | Formulation -> Document | Patent | Source
CITES = "CITES"  # Product -> Source
MAY_REFER_TO = "MAY_REFER_TO"  # Name -> Herb (vernacular / ambiguous term)
COMPETES_WITH = "COMPETES_WITH"  # Product -> Product
IN_CATEGORY = "IN_CATEGORY"  # Formulation -> Category

REL_TYPES = frozenset(
    {CONTAINS, INGREDIENT_OF, MENTIONED_IN, CITES, MAY_REFER_TO, COMPETES_WITH, IN_CATEGORY}
)

# Provenance of a node / relationship; only these back botanical lookup.
TRUSTED_ORIGINS = ("curated", "corpus")

# Entities a user would click on as "medicines".
MEDICINE_LABELS = (HERB, FORMULATION, INGREDIENT, COMPOUND)

PropValue = str | int | float | bool | list[str] | None


def normalize(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def node_key(label: str, name: str) -> str:
    return f"{label}:{normalize(name)}"


def clean_props(props: dict[str, Any]) -> dict[str, PropValue]:
    """Neo4j properties must be primitives or homogeneous lists."""
    out: dict[str, PropValue] = {}
    for k, v in props.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            out[k] = v
        elif isinstance(v, (list, tuple, set)):
            out[k] = [str(x) for x in v if x is not None and str(x).strip()]
        else:
            out[k] = str(v)
    return out


class GraphNode(BaseModel):
    key: str
    label: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    props: dict[str, PropValue] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str
    props: dict[str, PropValue] = Field(default_factory=dict)


@dataclass
class GraphBatch:
    """Upsert unit: nodes are merged by key, aliases are unioned."""

    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: dict[tuple[str, str, str], GraphEdge] = field(default_factory=dict)

    def add_node(
        self,
        label: str,
        name: str,
        *,
        ident: str | None = None,
        aliases: list[str] | None = None,
        **props: Any,
    ) -> str:
        """``ident`` overrides ``name`` for the key (e.g. source ids, patent numbers)."""
        if label not in NODE_LABELS:
            raise ValueError(f"Unknown node label {label!r}")
        key = node_key(label, ident or name)
        node = self.nodes.get(key)
        if node is None:
            node = GraphNode(key=key, label=label, name=name.strip())
            self.nodes[key] = node
        merged = dict.fromkeys([*node.aliases, *(aliases or [])])
        node.aliases = [a.strip() for a in merged if a and a.strip()]
        node.props.update(clean_props(props))
        return key

    def add_edge(self, source: str, target: str, rel: str, **props: Any) -> None:
        if rel not in REL_TYPES:
            raise ValueError(f"Unknown relationship {rel!r}")
        if source == target:
            return
        edge_id = (source, target, rel)
        edge = self.edges.get(edge_id)
        if edge is None:
            edge = GraphEdge(source=source, target=target, type=rel)
            self.edges[edge_id] = edge
        edge.props.update(clean_props(props))

    def merge(self, other: GraphBatch) -> None:
        for key, node in other.nodes.items():
            existing = self.nodes.get(key)
            if existing is None:
                self.nodes[key] = node.model_copy(deep=True)
            else:
                existing.aliases = list(dict.fromkeys([*existing.aliases, *node.aliases]))
                existing.props.update(node.props)
        for edge in other.edges.values():
            self.add_edge(edge.source, edge.target, edge.type, **edge.props)


class GraphView(BaseModel):
    """API payload: a subgraph centred on one entity."""

    center: str | None = None
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    truncated: bool = False


class VocabularyTerm(BaseModel):
    term: str
    key: str
    label: str


class GraphStats(BaseModel):
    backend: str
    nodes: dict[str, int] = Field(default_factory=dict)
    relationships: int = 0


def alias_pattern(terms: list[str]) -> re.Pattern[str] | None:
    """Word-boundary regex matching any term (longest first), case-insensitive."""
    cleaned = sorted({t.strip() for t in terms if t and len(t.strip()) >= 3}, key=len, reverse=True)
    if not cleaned:
        return None
    body = "|".join(re.escape(t) for t in cleaned)
    return re.compile(rf"(?<![\w-])(?:{body})(?![\w-])", re.IGNORECASE)
