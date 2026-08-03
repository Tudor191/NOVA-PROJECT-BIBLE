"""The `GraphStore` interface -- ADR-007 (docs/architecture/00-overview-and-decisions.md),
full contract worked out here per docs/architecture/07-database-architecture.md §4 and
docs/design/phase-1/02-knowledge-engine.md / 03-world-model-engine.md.

`knowledge-engine` and `world-model-engine` both depend only on this Protocol, never
on a graph database driver directly. `GraphQuery` and `TraversalSpec` are
backend-agnostic builder types (label filters, relationship-type filters, depth
bounds, property predicates) -- not raw Cypher -- specifically so the interface
cannot be silently defeated by a caller embedding a Neo4j-specific query string. The
default `Neo4jGraphStore` adapter translates these builders to Cypher; an
alternative adapter (Memgraph, ArangoDB, Amazon Neptune) would translate the same
builders to its own query language.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

PropertyValue = str | int | float | bool | None


class GraphNode(BaseModel):
    """One node, as returned by `query`/`traverse`."""

    id: str
    labels: tuple[str, ...]
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphRelationship(BaseModel):
    """One relationship, as returned by `query`/`traverse`."""

    from_id: str
    to_id: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphPath(BaseModel):
    """One traversal path: an ordered walk of nodes connected by relationships."""

    nodes: list[GraphNode]
    relationships: list[GraphRelationship]


class GraphResult(BaseModel):
    """The result of a `query` or `traverse` call.

    `nodes`/`relationships` are the deduplicated set of everything touched; `paths`
    is populated by `traverse` (one entry per distinct path found) and left empty by
    `query`, which has no notion of a path.
    """

    nodes: list[GraphNode] = Field(default_factory=list)
    relationships: list[GraphRelationship] = Field(default_factory=list)
    paths: list[GraphPath] = Field(default_factory=list)


FilterOp = Literal["eq", "neq", "gt", "gte", "lt", "lte", "in", "contains"]


class PropertyFilter(BaseModel):
    """One predicate in a `GraphQuery`, translated to the backend's native filter
    syntax (a Cypher `WHERE` clause, for the Neo4j adapter)."""

    property: str
    op: FilterOp
    value: PropertyValue | list[PropertyValue]


class GraphQuery(BaseModel):
    """Backend-agnostic node lookup: find nodes with `label` matching `filters`."""

    label: str
    filters: list[PropertyFilter] = Field(default_factory=list)
    limit: int = 100


class TraversalDirection(StrEnum):
    OUTGOING = "outgoing"
    INCOMING = "incoming"
    BOTH = "both"


class TraversalSpec(BaseModel):
    """Backend-agnostic bounded graph traversal from a start node.

    Empty `relationship_types`/`target_labels` mean "any" -- unbounded traversal
    (`max_hops` with no cap) is deliberately not expressible here; every caller must
    pick a bound, per docs/design/phase-1/02-knowledge-engine.md §7's "unbounded
    traversal is a correctness bug, not a feature" note.
    """

    relationship_types: tuple[str, ...] = ()
    direction: TraversalDirection = TraversalDirection.BOTH
    max_hops: int = Field(default=2, ge=1, le=10)
    target_labels: tuple[str, ...] = ()
    limit: int = 100


class GraphStoreHealth(BaseModel):
    """Point-in-time health snapshot for a `GraphStore` connection."""

    connected: bool
    backend: str
    latency_ms: float | None = None
    error: str | None = None


@runtime_checkable
class GraphStore(Protocol):
    """The only interface any NOVA code may depend on to talk to the graph database.

    Concrete backends (Neo4j by default; see `nova_graphstore_sdk.backends`)
    implement this Protocol. Selecting a backend is a configuration decision
    (`nova_graphstore_sdk.factory.get_graph_store`), never an import decision -- no
    engine ever imports `neo4j` directly.
    """

    async def connect(self) -> None:
        """Establish the underlying connection. Idempotent."""
        ...

    async def close(self) -> None:
        """Tear down the underlying connection. Idempotent."""
        ...

    async def upsert_node(self, label: str, node_id: str, properties: dict[str, Any]) -> None:
        """Create `node_id` with `label` if it does not exist, else merge
        `properties` into the existing node (Cypher `MERGE` semantics)."""
        ...

    async def upsert_relationship(
        self,
        from_id: str,
        rel_type: str,
        to_id: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Create a `rel_type` relationship from `from_id` to `to_id` if it does not
        exist, else merge `properties` into the existing relationship. Both nodes
        must already exist."""
        ...

    async def query(self, query: GraphQuery) -> GraphResult:
        """Return nodes matching `query`, with their directly attached relationships."""
        ...

    async def traverse(self, start_id: str, spec: TraversalSpec) -> GraphResult:
        """Return every node/path reachable from `start_id` within `spec`'s bounds."""
        ...

    async def delete_node(self, node_id: str) -> None:
        """Delete `node_id` and every relationship attached to it."""
        ...

    async def health(self) -> GraphStoreHealth:
        """Report the current connection health."""
        ...
