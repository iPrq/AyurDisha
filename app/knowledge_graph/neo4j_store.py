"""Neo4j-backed knowledge graph store.

Every node carries the shared ``:Entity`` label plus its specific label (``:Herb``,
``:Formulation``...), a unique ``key`` and lower-cased ``aliases_lc`` for lookups.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from neo4j import Driver, GraphDatabase

from graph.models import BotanicalCandidate
from knowledge_graph.schema import (
    MEDICINE_LABELS,
    NODE_LABELS,
    REL_TYPES,
    TRUSTED_ORIGINS,
    GraphBatch,
    GraphEdge,
    GraphNode,
    GraphStats,
    GraphView,
    VocabularyTerm,
    normalize,
)
from knowledge_graph.store import DEFAULT_CONFIDENCE, LABEL_PRIORITY, ORIGIN_RANK, rank_nodes, traverse

logger = logging.getLogger(__name__)

_RESERVED = {"key", "name", "label", "aliases", "aliases_lc"}
_BATCH = 500

_MERGE_NODES = """
UNWIND $rows AS row
MERGE (n:Entity {key: row.key})
ON CREATE SET n.name = row.name, n.label = row.label, n.aliases = []
WITH n, row, coalesce(n.origin_rank, 99) > $rank AS upgrade
SET n:`%s`
SET n += row.props
SET n.name = CASE WHEN upgrade THEN row.name ELSE n.name END,
    n.origin = CASE WHEN upgrade THEN $origin ELSE n.origin END,
    n.origin_rank = CASE WHEN upgrade THEN $rank ELSE n.origin_rank END
SET n.aliases = reduce(acc = coalesce(n.aliases, []), a IN row.aliases |
    CASE WHEN a IN acc THEN acc ELSE acc + a END)
SET n.aliases_lc = [a IN n.aliases | toLower(a)] + toLower(n.name)
"""

_MERGE_EDGES = """
UNWIND $rows AS row
MATCH (a:Entity {key: row.source})
MATCH (b:Entity {key: row.target})
MERGE (a)-[r:`%s`]->(b)
WITH r, row, coalesce(r.origin_rank, 99) > $rank AS upgrade
SET r += row.props
SET r.origin = CASE WHEN upgrade THEN $origin ELSE r.origin END,
    r.origin_rank = CASE WHEN upgrade THEN $rank ELSE r.origin_rank END
"""

_EXPAND = """
UNWIND $keys AS k
MATCH (n:Entity {key: k})
CALL (n) {
  MATCH (n)-[r]-(m:Entity)
  RETURN r, m
  ORDER BY coalesce($priority[m.label], 9), toLower(m.name)
  LIMIT $per_node
}
RETURN startNode(r).key AS source, endNode(r).key AS target, type(r) AS type,
       properties(r) AS rprops, m
"""

_LOOKUP_NAME = """
MATCH (n:Name) WHERE $t IN n.aliases_lc
MATCH (n)-[r:MAY_REFER_TO]->(h:Herb) WHERE r.origin IN $trusted
RETURN DISTINCT h
"""

_LOOKUP_HERB = """
MATCH (h:Herb) WHERE $t IN h.aliases_lc AND h.origin IN $trusted
RETURN h
"""

_COMPOUNDS = """
UNWIND $keys AS k
MATCH (h:Herb {key: k})-[r:CONTAINS]->(c:Compound) WHERE r.origin IN $trusted
RETURN k AS key, collect(DISTINCT c.name) AS compounds
"""


def _to_node(record: Any) -> GraphNode:
    props = dict(record)
    return GraphNode(
        key=props["key"],
        label=props.get("label") or "",
        name=props.get("name") or props["key"],
        aliases=list(props.get("aliases") or []),
        props={k: v for k, v in props.items() if k not in _RESERVED and k != "origin_rank"},
    )


def _chunks(rows: list[dict[str, Any]]) -> Iterable[list[dict[str, Any]]]:
    for i in range(0, len(rows), _BATCH):
        yield rows[i : i + _BATCH]


class Neo4jGraphStore:
    backend = "neo4j"

    def __init__(self, uri: str, user: str, password: str, *, database: str | None = None) -> None:
        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))
        self._database = database
        self._driver.verify_connectivity()
        self._ensure_schema()

    def close(self) -> None:
        self._driver.close()

    def _run(self, query: str, **params: Any) -> list[Any]:
        records, _, _ = self._driver.execute_query(
            query, params, database_=self._database
        )
        return records

    def _ensure_schema(self) -> None:
        self._run("CREATE CONSTRAINT entity_key IF NOT EXISTS FOR (n:Entity) REQUIRE n.key IS UNIQUE")
        self._run("CREATE INDEX entity_label IF NOT EXISTS FOR (n:Entity) ON (n.label)")

    def merge_batch(self, batch: GraphBatch, *, origin: str) -> None:
        rank = ORIGIN_RANK.get(origin, 9)
        by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for node in batch.nodes.values():
            if node.label not in NODE_LABELS:
                continue
            by_label[node.label].append({
                "key": node.key,
                "name": node.name,
                "label": node.label,
                "aliases": node.aliases,
                "props": {k: v for k, v in node.props.items() if k not in _RESERVED},
            })
        for label, rows in by_label.items():
            for chunk in _chunks(rows):
                self._run(_MERGE_NODES % label, rows=chunk, origin=origin, rank=rank)

        by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for edge in batch.edges.values():
            if edge.type in REL_TYPES:
                by_type[edge.type].append(
                    {"source": edge.source, "target": edge.target, "props": edge.props}
                )
        for rel, rows in by_type.items():
            for chunk in _chunks(rows):
                self._run(_MERGE_EDGES % rel, rows=chunk, origin=origin, rank=rank)

    def resolve(self, query: str) -> GraphNode | None:
        records = self._run(
            "MATCH (n:Entity) WHERE n.key = $q OR $t IN n.aliases_lc RETURN n LIMIT 25",
            q=query,
            t=normalize(query),
        )
        exact = [_to_node(r["n"]) for r in records if r["n"]["key"] == query]
        ranked = exact or rank_nodes(_to_node(r["n"]) for r in records)
        return ranked[0] if ranked else None

    def _expand(self, keys: list[str], per_node: int) -> list[tuple[GraphEdge, GraphNode]]:
        records = self._run(_EXPAND, keys=keys, per_node=per_node, priority=LABEL_PRIORITY)
        return [
            (
                GraphEdge(
                    source=r["source"],
                    target=r["target"],
                    type=r["type"],
                    props={k: v for k, v in dict(r["rprops"]).items() if k != "origin_rank"},
                ),
                _to_node(r["m"]),
            )
            for r in records
        ]

    def neighborhood(self, query: str, *, depth: int = 1, limit: int = 150) -> GraphView | None:
        center = self.resolve(query)
        if center is None:
            return None
        return traverse(center, self._expand, depth=depth, limit=limit)

    def search(self, query: str, *, limit: int = 20) -> list[GraphNode]:
        term = normalize(query)
        if not term:
            return []
        records = self._run(
            "MATCH (n:Entity) WHERE any(a IN n.aliases_lc WHERE a CONTAINS $t) "
            "RETURN n LIMIT $limit",
            t=term,
            limit=limit * 3,
        )
        return rank_nodes(_to_node(r["n"]) for r in records)[:limit]

    def vocabulary(self, labels: Iterable[str] = MEDICINE_LABELS) -> list[VocabularyTerm]:
        records = self._run(
            "MATCH (n:Entity) WHERE n.label IN $labels "
            "RETURN n.key AS key, n.label AS label, n.name AS name, n.aliases AS aliases",
            labels=list(labels),
        )
        return [
            VocabularyTerm(term=t, key=r["key"], label=r["label"])
            for r in records
            for t in dict.fromkeys([r["name"], *(r["aliases"] or [])])
        ]

    def lookup_botanical(self, term: str) -> list[BotanicalCandidate]:
        t = normalize(term)
        if not t:
            return []
        trusted = list(TRUSTED_ORIGINS)
        herbs = [_to_node(r["h"]) for r in self._run(_LOOKUP_NAME, t=t, trusted=trusted)]
        if not herbs:
            herbs = [_to_node(r["h"]) for r in self._run(_LOOKUP_HERB, t=t, trusted=trusted)]
        if not herbs:
            return []
        compounds = {
            r["key"]: sorted(r["compounds"])
            for r in self._run(_COMPOUNDS, keys=[h.key for h in herbs], trusted=trusted)
        }
        out = []
        for h in herbs:
            confidence = h.props.get("confidence")
            out.append(BotanicalCandidate(
                botanical_name=h.name,
                synonyms=list(dict.fromkeys([h.name, *h.aliases])),
                phytochemicals=compounds.get(h.key, []),
                confidence=float(confidence) if isinstance(confidence, (int, float)) else DEFAULT_CONFIDENCE,
            ))
        return out

    def stats(self) -> GraphStats:
        nodes = {
            r["label"]: r["n"]
            for r in self._run("MATCH (n:Entity) RETURN n.label AS label, count(*) AS n")
        }
        rels = self._run("MATCH (:Entity)-[r]->(:Entity) RETURN count(r) AS n")
        return GraphStats(backend=self.backend, nodes=nodes, relationships=rels[0]["n"] if rels else 0)

    def is_empty(self) -> bool:
        return not self._run("MATCH (n:Entity) RETURN n.key LIMIT 1")
