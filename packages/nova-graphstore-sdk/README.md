# nova-graphstore-sdk

The `GraphStore` interface (ADR-007, docs/architecture/00-overview-and-decisions.md),
worked out in full per docs/architecture/07-database-architecture.md §4 and the
Phase 1 design package. **No engine may import a graph database client directly**
-- only this package.

- `interface.py` -- the `GraphStore` Protocol every caller depends on, plus the
  backend-agnostic `GraphQuery`/`TraversalSpec` builder types (never raw Cypher).
- `factory.py` -- `get_graph_store()`, resolving the `GRAPH_STORE_BACKEND`
  environment variable (`neo4j` by default) to a concrete backend.
- `boundary.py` -- `BoundGraphStore`, which wraps any backend and enforces an
  engine's declared node-label / relationship-type allow-lists at runtime --
  Knowledge Engine and World Model Engine share one physical Neo4j instance through
  disjoint label namespaces (docs/design/phase-1/04-cross-engine-integration.md §4),
  and this is what makes that separation a runtime guarantee instead of just a
  naming convention.
- `backends/in_memory.py` -- dependency-free backend for tests and local dev
  (breadth-first search instead of a query planner; sufficient to verify the
  `GraphStore` contract itself).
- `backends/neo4j.py` -- the default production backend.

## Adding a new backend (e.g. Memgraph, ArangoDB, Amazon Neptune)

1. Create `backends/<name>.py` implementing every method on `GraphStore`, translating
   `GraphQuery`/`TraversalSpec` to the target's native query language.
2. Register it in `factory.py`: `register_backend("<name>")(_build_<name>)`.
3. Add the shared contract test suite (docs/architecture/16 §4) against the new
   backend to prove behavioral equivalence with `neo4j`.

No other package needs to change -- this is what ADR-007 exists to guarantee.

## Usage

```python
from nova_graphstore_sdk import get_graph_store, BoundGraphStore, GraphQuery, PropertyFilter

store = get_graph_store()  # reads GRAPH_STORE_BACKEND, defaults to "neo4j"
await store.connect()

bound = BoundGraphStore(
    store,
    engine_name="knowledge-engine",
    allowed_labels=frozenset({"Concept", "Technology", "Framework", "Person", "Project"}),
    allowed_relationship_types=frozenset({"USES", "DEPENDS_ON", "RELATED_TO", "CREATED_BY"}),
)

await bound.upsert_node("Concept", str(node_id), {"name": "Python", "confidence": 0.95})
result = await bound.query(
    GraphQuery(label="Concept", filters=[PropertyFilter(property="name", op="eq", value="Python")])
)
```
