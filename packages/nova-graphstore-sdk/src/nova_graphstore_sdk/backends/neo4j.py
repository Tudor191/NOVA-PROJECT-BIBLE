"""Neo4j `GraphStore` backend -- the default implementation (ADR-007).

Cypher has no way to parameterize a label or relationship type (only property
values), so this adapter inlines them -- after validating every one against a
strict identifier allow-list (`_validate_identifier`), since `GraphQuery`/
`TraversalSpec` values ultimately originate from application code (engine domain
logic), not raw user input, but should never become a Cypher injection vector even
so.

This module lazily imports `neo4j` inside each method (not at module scope) so that
importing `nova_graphstore_sdk` never requires a Neo4j server to be reachable,
mirroring `nova_eventbus_sdk.backends.nats`.
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING, Any

from nova_graphstore_sdk.interface import (
    FilterOp,
    GraphNode,
    GraphPath,
    GraphQuery,
    GraphRelationship,
    GraphResult,
    GraphStoreHealth,
    TraversalDirection,
    TraversalSpec,
)

if TYPE_CHECKING:
    from neo4j import AsyncDriver

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_CYPHER_OPS: dict[FilterOp, str] = {
    "eq": "=",
    "neq": "<>",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "in": "IN",
    "contains": "CONTAINS",
}


def _validate_identifier(name: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid Cypher label/relationship-type identifier: {name!r}")
    return name


class Neo4jGraphStore:
    """`GraphStore` implementation backed by Neo4j."""

    def __init__(self, uri: str, user: str, password: str, *, database: str = "neo4j") -> None:
        self._uri = uri
        self._user = user
        self._password = password
        self._database = database
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        from neo4j import AsyncGraphDatabase

        self._driver = AsyncGraphDatabase.driver(self._uri, auth=(self._user, self._password))

    async def close(self) -> None:
        if self._driver is not None:
            await self._driver.close()
            self._driver = None

    async def upsert_node(self, label: str, node_id: str, properties: dict[str, Any]) -> None:
        driver = self._require_connected()
        label = _validate_identifier(label)
        cypher = f"MERGE (n:{label} {{id: $node_id}}) SET n += $properties"
        async with driver.session(database=self._database) as session:
            await session.run(cypher, node_id=node_id, properties=properties)

    async def upsert_relationship(
        self,
        from_id: str,
        rel_type: str,
        to_id: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        driver = self._require_connected()
        rel_type = _validate_identifier(rel_type)
        cypher = (
            "MATCH (a {id: $from_id}), (b {id: $to_id}) "
            f"MERGE (a)-[r:{rel_type}]->(b) SET r += $properties"
        )
        async with driver.session(database=self._database) as session:
            await session.run(cypher, from_id=from_id, to_id=to_id, properties=properties or {})

    async def query(self, query: GraphQuery) -> GraphResult:
        driver = self._require_connected()
        label = _validate_identifier(query.label)
        conditions = []
        params: dict[str, Any] = {}
        for i, f in enumerate(query.filters):
            param_name = f"p{i}"
            op = _CYPHER_OPS[f.op]
            conditions.append(f"n.{_validate_identifier(f.property)} {op} ${param_name}")
            params[param_name] = f.value
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        cypher = (
            f"MATCH (n:{label}) {where_clause} "
            f"WITH n LIMIT $limit "
            f"OPTIONAL MATCH (n)-[r]-(m) "
            f"RETURN n, r, m"
        )
        params["limit"] = query.limit
        nodes: dict[str, GraphNode] = {}
        rels: dict[tuple[str, str, str], GraphRelationship] = {}
        async with driver.session(database=self._database) as session:
            result = await session.run(cypher, **params)
            async for record in result:
                n = _to_graph_node(record["n"])
                nodes[n.id] = n
                if record["r"] is not None and record["m"] is not None:
                    m = _to_graph_node(record["m"])
                    nodes[m.id] = m
                    r = _to_graph_relationship(record["r"])
                    rels[(r.from_id, r.type, r.to_id)] = r
        return GraphResult(nodes=list(nodes.values()), relationships=list(rels.values()))

    async def traverse(self, start_id: str, spec: TraversalSpec) -> GraphResult:
        driver = self._require_connected()
        rel_pattern = ""
        if spec.relationship_types:
            types = "|".join(_validate_identifier(t) for t in spec.relationship_types)
            rel_pattern = f":{types}"
        arrow_left = "<-" if spec.direction is TraversalDirection.INCOMING else "-"
        arrow_right = "->" if spec.direction is TraversalDirection.OUTGOING else "-"
        where_clause = ""
        params: dict[str, Any] = {"start_id": start_id, "limit": spec.limit}
        if spec.target_labels:
            where_clause = "WHERE any(l IN labels(end) WHERE l IN $target_labels)"
            params["target_labels"] = list(spec.target_labels)
        cypher = (
            f"MATCH path = (start {{id: $start_id}}){arrow_left}"
            f"[r{rel_pattern}*1..{spec.max_hops}]{arrow_right}(end) "
            f"{where_clause} "
            f"RETURN path LIMIT $limit"
        )
        paths: list[GraphPath] = []
        nodes: dict[str, GraphNode] = {}
        rels: dict[tuple[str, str, str], GraphRelationship] = {}
        async with driver.session(database=self._database) as session:
            result = await session.run(cypher, **params)
            async for record in result:
                path = record["path"]
                graph_nodes = [_to_graph_node(n) for n in path.nodes]
                graph_rels = [_to_graph_relationship(r) for r in path.relationships]
                paths.append(GraphPath(nodes=graph_nodes, relationships=graph_rels))
                # graph_nodes[0] is always `start`, per the MATCH pattern above --
                # excluded here so `result.nodes` means "reached", not "visited
                # including start" (each GraphPath in `paths` still has it).
                for n in graph_nodes[1:]:
                    nodes[n.id] = n
                for r in graph_rels:
                    rels[(r.from_id, r.type, r.to_id)] = r
        return GraphResult(
            nodes=list(nodes.values()), relationships=list(rels.values()), paths=paths
        )

    async def delete_node(self, node_id: str) -> None:
        driver = self._require_connected()
        cypher = "MATCH (n {id: $node_id}) DETACH DELETE n"
        async with driver.session(database=self._database) as session:
            await session.run(cypher, node_id=node_id)

    async def health(self) -> GraphStoreHealth:
        if self._driver is None:
            return GraphStoreHealth(connected=False, backend="neo4j")
        start = time.perf_counter()
        try:
            async with self._driver.session(database=self._database) as session:
                await session.run("RETURN 1")
            latency_ms = (time.perf_counter() - start) * 1000
            return GraphStoreHealth(connected=True, backend="neo4j", latency_ms=latency_ms)
        except Exception as exc:  # noqa: BLE001 -- health checks must never raise
            return GraphStoreHealth(connected=False, backend="neo4j", error=str(exc))

    def _require_connected(self) -> AsyncDriver:
        if self._driver is None:
            raise RuntimeError("Neo4jGraphStore.connect() must be called before use.")
        return self._driver


def _to_graph_node(node: Any) -> GraphNode:
    properties = dict(node)
    node_id = str(properties.pop("id", None) or node.element_id)
    return GraphNode(id=node_id, labels=tuple(sorted(node.labels)), properties=properties)


def _to_graph_relationship(rel: Any) -> GraphRelationship:
    properties = dict(rel)
    from_id = str(dict(rel.start_node).get("id", rel.start_node.element_id))
    to_id = str(dict(rel.end_node).get("id", rel.end_node.element_id))
    return GraphRelationship(from_id=from_id, to_id=to_id, type=rel.type, properties=properties)
