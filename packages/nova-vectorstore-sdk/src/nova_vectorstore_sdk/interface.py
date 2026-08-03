"""The `VectorStore` interface -- introduced alongside ADR-009/010
(docs/architecture/00-overview-and-decisions.md) as part of the Phase 1 design
package (docs/design/phase-1/00-shared-foundations.md).

Memory Engine and Knowledge Engine both need nearest-neighbor search over embeddings
they generate (via `nova-embeddings-sdk`) and store in their own Postgres schema
(docs/architecture/07-database-architecture.md §3). `VectorStore` is the one
interface either engine depends on -- never a raw asyncpg/psycopg query against a
`VECTOR(...)` column, and never a direct import of a vector database client.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class VectorRecord(BaseModel):
    """One embedded row, ready to upsert.

    `metadata` carries whatever additional columns the owning collection has
    whitelisted for this purpose (docs/design/phase-1/01-memory-engine.md §10's
    `embedding_model` column is the canonical example: every `upsert` that fills in
    an embedding also stamps the model that produced it).
    """

    id: str
    vector: list[float]
    metadata: dict[str, Any] = Field(default_factory=dict)


class VectorMatch(BaseModel):
    """One search result: the stored record's id, similarity score, and metadata."""

    id: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class VectorQuery(BaseModel):
    """A nearest-neighbor search request.

    `filters` is an equality-only filter map applied to whitelisted metadata columns
    (e.g. `{"user_id": "...", "memory_type": "long_term"}`) -- every engine using this
    interface scopes every query by at least `user_id` per
    docs/design/phase-1/00-shared-foundations.md's tenancy convention. `min_score`
    (0.0-1.0, cosine similarity) drops low-relevance matches; `None` means no floor.
    """

    vector: list[float]
    top_k: int = 10
    filters: dict[str, Any] = Field(default_factory=dict)
    min_score: float | None = None


class VectorStoreHealth(BaseModel):
    """Point-in-time health snapshot for a `VectorStore` connection."""

    connected: bool
    backend: str
    latency_ms: float | None = None
    error: str | None = None


@runtime_checkable
class VectorStore(Protocol):
    """The only interface any NOVA code may depend on for vector similarity search.

    `collection` names a logical namespace registered with the backend at
    construction time (in the pgvector backend, one configured table -- see
    `nova_vectorstore_sdk.backends.pgvector.PgVectorCollection`; the in-memory
    backend creates collections on first use). Concrete backends implement this
    Protocol; selecting one is a configuration decision
    (`nova_vectorstore_sdk.factory.get_vector_store`), never an import decision -- no
    engine ever imports `asyncpg`, `pgvector`, or any other vector database client
    directly.
    """

    async def connect(self) -> None:
        """Establish the underlying connection. Idempotent."""
        ...

    async def close(self) -> None:
        """Tear down the underlying connection. Idempotent."""
        ...

    async def upsert(self, collection: str, record: VectorRecord) -> None:
        """Write `record`'s vector (and whitelisted metadata) into `collection`."""
        ...

    async def upsert_batch(self, collection: str, records: list[VectorRecord]) -> None:
        """Batch form of `upsert`, used by embedding workers (docs/design/phase-1/
        01-memory-engine.md §10) to avoid one round-trip per row."""
        ...

    async def search(self, collection: str, query: VectorQuery) -> list[VectorMatch]:
        """Return up to `query.top_k` nearest neighbors in `collection`, ranked by
        descending cosine similarity."""
        ...

    async def delete(self, collection: str, id: str) -> None:
        """Remove `id`'s vector from `collection`'s search index."""
        ...

    async def health(self) -> VectorStoreHealth:
        """Report the current connection health."""
        ...
