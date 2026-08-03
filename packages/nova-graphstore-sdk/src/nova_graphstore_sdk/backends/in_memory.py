"""In-process GraphStore backend: no external database, used for unit/integration
tests (see `nova-testkit`) and as a dependency-free default for local development
before Neo4j is running.

Implements `query`/`traverse` with a plain breadth-first search rather than a query
planner -- sufficient to verify the `GraphStore` contract itself; behavioral
equivalence with the Neo4j adapter under real query patterns is verified by the
shared contract-test suite (docs/architecture/16-testing-strategy.md §4) run against
both backends, not by this implementation's internals.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from nova_graphstore_sdk.interface import (
    GraphNode,
    GraphPath,
    GraphQuery,
    GraphRelationship,
    GraphResult,
    GraphStoreHealth,
    PropertyFilter,
    TraversalDirection,
    TraversalSpec,
)


@dataclass
class _Node:
    id: str
    labels: set[str]
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class _Relationship:
    from_id: str
    type: str
    to_id: str
    properties: dict[str, Any] = field(default_factory=dict)


def _matches_filter(properties: dict[str, Any], f: PropertyFilter) -> bool:
    value = properties.get(f.property)
    if f.op == "eq":
        return bool(value == f.value)
    if f.op == "neq":
        return bool(value != f.value)
    if f.op == "gt":
        return value is not None and f.value is not None and value > f.value
    if f.op == "gte":
        return value is not None and f.value is not None and value >= f.value
    if f.op == "lt":
        return value is not None and f.value is not None and value < f.value
    if f.op == "lte":
        return value is not None and f.value is not None and value <= f.value
    if f.op == "in":
        return value in f.value if isinstance(f.value, list) else False
    if f.op == "contains":
        return isinstance(value, str) and isinstance(f.value, str) and f.value in value
    raise ValueError(f"Unknown filter op: {f.op!r}")  # pragma: no cover -- exhaustive above


class InMemoryGraphStore:
    """Reference `GraphStore` implementation with no external dependencies."""

    def __init__(self) -> None:
        self._connected = False
        self._nodes: dict[str, _Node] = {}
        self._relationships: list[_Relationship] = []

    async def connect(self) -> None:
        self._connected = True

    async def close(self) -> None:
        self._connected = False
        self._nodes.clear()
        self._relationships.clear()

    async def upsert_node(self, label: str, node_id: str, properties: dict[str, Any]) -> None:
        self._require_connected()
        existing = self._nodes.get(node_id)
        if existing is None:
            self._nodes[node_id] = _Node(id=node_id, labels={label}, properties=dict(properties))
        else:
            existing.labels.add(label)
            existing.properties.update(properties)

    async def upsert_relationship(
        self,
        from_id: str,
        rel_type: str,
        to_id: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        self._require_connected()
        for rel in self._relationships:
            if rel.from_id == from_id and rel.type == rel_type and rel.to_id == to_id:
                rel.properties.update(properties or {})
                return
        self._relationships.append(
            _Relationship(
                from_id=from_id, type=rel_type, to_id=to_id, properties=dict(properties or {})
            )
        )

    async def query(self, query: GraphQuery) -> GraphResult:
        self._require_connected()
        matched = [
            node
            for node in self._nodes.values()
            if query.label in node.labels
            and all(_matches_filter(node.properties, f) for f in query.filters)
        ][: query.limit]
        node_ids = {n.id for n in matched}
        rels = [
            r for r in self._relationships if r.from_id in node_ids or r.to_id in node_ids
        ]
        return GraphResult(
            nodes=[self._to_graph_node(n) for n in matched],
            relationships=[self._to_graph_rel(r) for r in rels],
        )

    async def traverse(self, start_id: str, spec: TraversalSpec) -> GraphResult:
        self._require_connected()
        if start_id not in self._nodes:
            return GraphResult()

        paths: list[GraphPath] = []
        seen_nodes: dict[str, GraphNode] = {}
        seen_rels: dict[tuple[str, str, str], GraphRelationship] = {}

        # Each queue entry: (current_node_id, path_node_ids, path_rels)
        queue: deque[tuple[str, list[str], list[_Relationship]]] = deque()
        queue.append((start_id, [start_id], []))

        while queue and len(paths) < spec.limit:
            current_id, path_ids, path_rels = queue.popleft()
            depth = len(path_rels)
            if depth > 0:
                current_node = self._nodes[current_id]
                if not spec.target_labels or current_node.labels & set(spec.target_labels):
                    path = self._build_path(path_ids, path_rels)
                    paths.append(path)
                    # path.nodes[0] is always `start_id` -- excluded here so
                    # `result.nodes` means "reached", not "visited including start".
                    for n in path.nodes[1:]:
                        seen_nodes[n.id] = n
                    for r in path.relationships:
                        seen_rels[(r.from_id, r.type, r.to_id)] = r

            if depth >= spec.max_hops:
                continue

            for rel in self._relationships:
                neighbor_id: str | None = None
                if (
                    spec.direction in (TraversalDirection.OUTGOING, TraversalDirection.BOTH)
                    and rel.from_id == current_id
                ):
                    neighbor_id = rel.to_id
                if (
                    neighbor_id is None
                    and spec.direction in (TraversalDirection.INCOMING, TraversalDirection.BOTH)
                    and rel.to_id == current_id
                ):
                    neighbor_id = rel.from_id
                if neighbor_id is None:
                    continue
                if spec.relationship_types and rel.type not in spec.relationship_types:
                    continue
                if neighbor_id in path_ids:
                    continue  # no revisiting a node within the same path (avoid cycles)
                queue.append((neighbor_id, [*path_ids, neighbor_id], [*path_rels, rel]))

        return GraphResult(
            nodes=list(seen_nodes.values()),
            relationships=list(seen_rels.values()),
            paths=paths,
        )

    async def delete_node(self, node_id: str) -> None:
        self._require_connected()
        self._nodes.pop(node_id, None)
        self._relationships = [
            r for r in self._relationships if r.from_id != node_id and r.to_id != node_id
        ]

    async def health(self) -> GraphStoreHealth:
        start = time.perf_counter()
        connected = self._connected
        latency_ms = (time.perf_counter() - start) * 1000
        return GraphStoreHealth(connected=connected, backend="in_memory", latency_ms=latency_ms)

    def _build_path(self, node_ids: list[str], rels: list[_Relationship]) -> GraphPath:
        return GraphPath(
            nodes=[self._to_graph_node(self._nodes[nid]) for nid in node_ids],
            relationships=[self._to_graph_rel(r) for r in rels],
        )

    @staticmethod
    def _to_graph_node(node: _Node) -> GraphNode:
        return GraphNode(
            id=node.id, labels=tuple(sorted(node.labels)), properties=dict(node.properties)
        )

    @staticmethod
    def _to_graph_rel(rel: _Relationship) -> GraphRelationship:
        return GraphRelationship(
            from_id=rel.from_id, to_id=rel.to_id, type=rel.type, properties=dict(rel.properties)
        )

    def _require_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("InMemoryGraphStore.connect() must be called before use.")
