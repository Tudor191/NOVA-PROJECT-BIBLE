# nova-vectorstore-sdk

The `VectorStore` interface, introduced by the Phase 1 design package
(`docs/design/phase-1/00-shared-foundations.md`) alongside ADR-009/010
(`docs/architecture/00-overview-and-decisions.md`). **No engine may import a vector
database client directly** -- only this package.

- `interface.py` -- the `VectorStore` Protocol every caller depends on
  (`upsert`/`upsert_batch`/`search`/`delete`/`health`).
- `factory.py` -- `get_vector_store()`, resolving the `VECTOR_STORE_BACKEND`
  environment variable (`pgvector` by default) to a concrete backend.
- `backends/in_memory.py` -- dependency-free backend for tests and local dev. Owns
  its records outright (`upsert` is a true create-or-update).
- `backends/pgvector.py` -- the default production backend. Every `VECTOR(768)`
  column (ADR-010) lives on a table an engine's own Alembic migrations own (e.g.
  `memory.memory_record.embedding`) -- this backend never creates or drops rows, it
  only reads/writes the vector (and whitelisted metadata) columns of rows that
  already exist. `upsert` on a row that doesn't exist raises
  `CollectionRecordNotFoundError` rather than silently inserting a partial row.

This asymmetry between the two backends is deliberate, not an inconsistency: they
operate in genuinely different environments. `in_memory` is a self-contained store;
`pgvector` is a thin, safety-checked adapter over rows another schema owns.

## Usage

```python
from nova_vectorstore_sdk import get_vector_store, VectorRecord, VectorQuery
from nova_vectorstore_sdk.backends.pgvector import PgVectorCollection, PgVectorStore

store = PgVectorStore(
    dsn="postgresql://nova:nova_dev_password@localhost:5432/nova",
    collections={
        "memories": PgVectorCollection(
            table="memory.memory_record",
            vector_column="embedding",
            metadata_columns=("embedding_model", "user_id", "memory_type"),
        ),
    },
)
await store.connect()

await store.upsert(
    "memories",
    VectorRecord(id=str(memory_id), vector=embedding, metadata={"embedding_model": "nomic-embed-text"}),
)

matches = await store.search(
    "memories",
    VectorQuery(vector=query_embedding, top_k=10, filters={"user_id": str(user_id)}),
)
```

For tests, use `get_vector_store("in_memory")` or depend on `nova-testkit`'s fixture
once added.

## Adding a new backend

1. Create `backends/<name>.py` implementing every method on `VectorStore`.
2. Register it in `factory.py`: `register_backend("<name>")(_build_<name>)`.
3. Add the shared contract test suite (docs/architecture/16 §4) against the new
   backend to prove behavioral equivalence with `pgvector`.

No other package needs to change.
