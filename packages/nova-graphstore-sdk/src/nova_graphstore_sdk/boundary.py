"""Runtime enforcement of an engine's declared node-label / relationship-type
allow-lists.

docs/design/phase-1/04-cross-engine-integration.md §4: Knowledge Engine and World
Model Engine share one physical Neo4j instance through disjoint label namespaces
(`:Concept`/`:Technology`/... vs. `:WorldProject`/`:File`/...). `BoundGraphStore`
wraps any `GraphStore` implementation and makes that separation a runtime guarantee,
not just a naming convention -- mirroring `nova_eventbus_sdk.boundary.BoundEventBus`
applied to the graph instead of the bus.

`delete_node` is intentionally not label-checked here: its signature (`node_id`
only, per ADR-007's interface) carries no label, and checking would require an extra
round-trip lookup. The actual isolation guarantee for delete comes from UUID
namespace separation -- each engine mints its own node ids and never learns another
engine's ids through any code path (docs/design/phase-1/04 §4), so it never has a
foreign id to pass here in the first place. Every *write* and *read* path, where
cross-engine contamination could actually be introduced, is checked below.
"""

from __future__ import annotations

from typing import Any

from nova_graphstore_sdk.interface import GraphQuery, GraphResult, GraphStoreHealth, TraversalSpec


class LabelNotAllowedError(PermissionError):
    """Raised when an engine attempts to touch a label or relationship type outside
    its declared allow-list."""


class BoundGraphStore:
    """A `GraphStore` wrapper that only permits declared labels/relationship types
    through.

    `allowed_labels`/`allowed_relationship_types` are exact-match sets (unlike
    `BoundEventBus`'s glob patterns -- label/relationship-type vocabularies are
    small, enumerable, and rarely wildcard-shaped in practice).
    """

    def __init__(
        self,
        store: Any,
        *,
        engine_name: str,
        allowed_labels: frozenset[str],
        allowed_relationship_types: frozenset[str],
    ) -> None:
        self._store = store
        self._engine_name = engine_name
        self._allowed_labels = allowed_labels
        self._allowed_relationship_types = allowed_relationship_types

    async def connect(self) -> None:
        await self._store.connect()

    async def close(self) -> None:
        await self._store.close()

    async def upsert_node(self, label: str, node_id: str, properties: dict[str, Any]) -> None:
        self._require_label(label)
        await self._store.upsert_node(label, node_id, properties)

    async def upsert_relationship(
        self,
        from_id: str,
        rel_type: str,
        to_id: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        self._require_relationship_type(rel_type)
        await self._store.upsert_relationship(from_id, rel_type, to_id, properties)

    async def query(self, query: GraphQuery) -> GraphResult:
        self._require_label(query.label)
        return await self._store.query(query)

    async def traverse(self, start_id: str, spec: TraversalSpec) -> GraphResult:
        for label in spec.target_labels:
            self._require_label(label)
        for rel_type in spec.relationship_types:
            self._require_relationship_type(rel_type)
        return await self._store.traverse(start_id, spec)

    async def delete_node(self, node_id: str) -> None:
        await self._store.delete_node(node_id)

    async def health(self) -> GraphStoreHealth:
        return await self._store.health()

    def _require_label(self, label: str) -> None:
        if label not in self._allowed_labels:
            raise LabelNotAllowedError(
                f"{self._engine_name!r} is not permitted to touch label {label!r}. "
                f"Allowed labels: {sorted(self._allowed_labels)}."
            )

    def _require_relationship_type(self, rel_type: str) -> None:
        if rel_type not in self._allowed_relationship_types:
            raise LabelNotAllowedError(
                f"{self._engine_name!r} is not permitted to use relationship type "
                f"{rel_type!r}. Allowed types: {sorted(self._allowed_relationship_types)}."
            )
