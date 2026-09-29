"""Graph store interface, shared traversal logic and an in-memory implementation."""

from __future__ import annotations

import threading
from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import Protocol

from graph.models import BotanicalCandidate
from knowledge_graph.schema import (
    COMPOUND,
    CONTAINS,
    FORMULATION,
    HERB,
    INGREDIENT,
    MAY_REFER_TO,
    MEDICINE_LABELS,
    NAME,
    TRUSTED_ORIGINS,
    GraphBatch,
    GraphEdge,
    GraphNode,
    GraphStats,
    GraphView,
    VocabularyTerm,
    normalize,
)

ORIGIN_RANK = {"curated": 0, "corpus": 1, "pipeline": 2}
LABEL_PRIORITY = {HERB: 0, FORMULATION: 1, INGREDIENT: 2, COMPOUND: 3, NAME: 4}
DEFAULT_CONFIDENCE = 0.85

Expand = Callable[[list[str], int], list[tuple[GraphEdge, GraphNode]]]


class GraphStore(Protocol):
    backend: str

    def merge_batch(self, batch: GraphBatch, *, origin: str) -> None: ...
    def resolve(self, query: str) -> GraphNode | None: ...
    def neighborhood(self, query: str, *, depth: int = 1, limit: int = 150) -> GraphView | None: ...
    def search(self, query: str, *, limit: int = 20) -> list[GraphNode]: ...
    def vocabulary(self, labels: Iterable[str] = MEDICINE_LABELS) -> list[VocabularyTerm]: ...
    def lookup_botanical(self, term: str) -> list[BotanicalCandidate]: ...
    def stats(self) -> GraphStats: ...
    def is_empty(self) -> bool: ...


def rank_nodes(nodes: Iterable[GraphNode]) -> list[GraphNode]:
    return sorted(nodes, key=lambda n: (LABEL_PRIORITY.get(n.label, 9), n.name.lower()))


def traverse(
    center: GraphNode,
    expand: Expand,
    *,
    depth: int,
    limit: int,
    fanout: int = 25,
) -> GraphView:
    """BFS from ``center``; first hop takes up to ``limit`` neighbours, later hops ``fanout`` each."""
    nodes: dict[str, GraphNode] = {center.key: center}
    edges: dict[tuple[str, str, str], GraphEdge] = {}
    frontier = [center.key]
    truncated = False

    for hop in range(depth):
        if not frontier:
            break
        per_node = limit if hop == 0 else fanout
        next_frontier: list[str] = []
        for edge, node in expand(frontier, per_node + 1):
            if node.key not in nodes:
                if len(nodes) >= limit:
                    truncated = True
                    continue
                nodes[node.key] = node
                next_frontier.append(node.key)
            edges[(edge.source, edge.target, edge.type)] = edge
        frontier = next_frontier

    kept = [e for e in edges.values() if e.source in nodes and e.target in nodes]
    return GraphView(center=center.key, nodes=list(nodes.values()), edges=kept, truncated=truncated)


def _better_origin(current: str | None, incoming: str) -> bool:
    return current is None or ORIGIN_RANK.get(incoming, 9) < ORIGIN_RANK.get(current, 9)


class InMemoryGraphStore:
    """Process-local fallback used when NEO4J_URI is not configured."""

    backend = "memory"

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[tuple[str, str, str], GraphEdge] = {}
        self._adj: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
        self._lock = threading.RLock()

    def merge_batch(self, batch: GraphBatch, *, origin: str) -> None:
        with self._lock:
            for key, node in batch.nodes.items():
                existing = self._nodes.get(key)
                if existing is None:
                    existing = node.model_copy(deep=True)
                    existing.props["origin"] = origin
                    self._nodes[key] = existing
                    continue
                if _better_origin(existing.props.get("origin"), origin):  # type: ignore[arg-type]
                    existing.props["origin"] = origin
                    existing.name = node.name
                existing.aliases = list(dict.fromkeys([*existing.aliases, *node.aliases]))
                existing.props.update({k: v for k, v in node.props.items() if k != "origin"})

            for eid, edge in batch.edges.items():
                if edge.source not in self._nodes or edge.target not in self._nodes:
                    continue
                existing_edge = self._edges.get(eid)
                if existing_edge is None:
                    existing_edge = edge.model_copy(deep=True)
                    existing_edge.props["origin"] = origin
                    self._edges[eid] = existing_edge
                    self._adj[edge.source].add(eid)
                    self._adj[edge.target].add(eid)
                    continue
                if _better_origin(existing_edge.props.get("origin"), origin):  # type: ignore[arg-type]
                    existing_edge.props["origin"] = origin
                existing_edge.props.update({k: v for k, v in edge.props.items() if k != "origin"})

    def _matches(self, term: str) -> list[GraphNode]:
        return [
            n
            for n in self._nodes.values()
            if normalize(n.name) == term or term in {normalize(a) for a in n.aliases}
        ]

    def resolve(self, query: str) -> GraphNode | None:
        with self._lock:
            if query in self._nodes:
                return self._nodes[query]
            ranked = rank_nodes(self._matches(normalize(query)))
            return ranked[0] if ranked else None

    def _expand(self, keys: list[str], per_node: int) -> list[tuple[GraphEdge, GraphNode]]:
        out: list[tuple[GraphEdge, GraphNode]] = []
        for key in keys:
            pairs = []
            for eid in self._adj.get(key, ()):
                edge = self._edges[eid]
                other = edge.target if edge.source == key else edge.source
                pairs.append((edge, self._nodes[other]))
            pairs.sort(key=lambda p: (LABEL_PRIORITY.get(p[1].label, 9), p[1].name.lower()))
            out.extend(pairs[:per_node])
        return out

    def neighborhood(self, query: str, *, depth: int = 1, limit: int = 150) -> GraphView | None:
        with self._lock:
            center = self.resolve(query)
            if center is None:
                return None
            return traverse(center, self._expand, depth=depth, limit=limit)

    def search(self, query: str, *, limit: int = 20) -> list[GraphNode]:
        term = normalize(query)
        if not term:
            return []
        with self._lock:
            hits = [
                n
                for n in self._nodes.values()
                if term in n.name.lower() or any(term in a.lower() for a in n.aliases)
            ]
        return rank_nodes(hits)[:limit]

    def vocabulary(self, labels: Iterable[str] = MEDICINE_LABELS) -> list[VocabularyTerm]:
        wanted = set(labels)
        with self._lock:
            return [
                VocabularyTerm(term=t, key=n.key, label=n.label)
                for n in self._nodes.values()
                if n.label in wanted
                for t in dict.fromkeys([n.name, *n.aliases])
            ]

    def _candidate(self, herb: GraphNode) -> BotanicalCandidate:
        compounds = [
            self._nodes[e.target].name
            for eid in self._adj.get(herb.key, ())
            if (e := self._edges[eid]).type == CONTAINS
            and e.source == herb.key
            and e.props.get("origin") in TRUSTED_ORIGINS
        ]
        confidence = herb.props.get("confidence")
        return BotanicalCandidate(
            botanical_name=herb.name,
            synonyms=list(dict.fromkeys([herb.name, *herb.aliases])),
            phytochemicals=sorted(compounds),
            confidence=float(confidence) if isinstance(confidence, (int, float)) else DEFAULT_CONFIDENCE,
        )

    def lookup_botanical(self, term: str) -> list[BotanicalCandidate]:
        t = normalize(term)
        if not t:
            return []
        with self._lock:
            referred = [
                self._nodes[e.target]
                for n in self._matches(t)
                if n.label == NAME
                for eid in self._adj.get(n.key, ())
                if (e := self._edges[eid]).type == MAY_REFER_TO
                and e.source == n.key
                and e.props.get("origin") in TRUSTED_ORIGINS
            ]
            herbs = referred or [
                n
                for n in self._matches(t)
                if n.label == HERB and n.props.get("origin") in TRUSTED_ORIGINS
            ]
            return [self._candidate(h) for h in herbs]

    def stats(self) -> GraphStats:
        with self._lock:
            counts: dict[str, int] = defaultdict(int)
            for n in self._nodes.values():
                counts[n.label] += 1
            return GraphStats(backend=self.backend, nodes=dict(counts), relationships=len(self._edges))

    def is_empty(self) -> bool:
        return not self._nodes
