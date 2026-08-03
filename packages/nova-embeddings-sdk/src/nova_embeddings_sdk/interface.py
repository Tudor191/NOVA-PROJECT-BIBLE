"""The `EmbeddingProvider` interface -- ADR-009 (docs/architecture/00-overview-and-decisions.md).

Memory Engine and Knowledge Engine both need vector embeddings for semantic search
starting in Phase 1, before the AI Model Orchestration Engine (a Phase 2
deliverable) exists to route model calls generally. `EmbeddingProvider` is the one
interface either engine depends on -- never a direct call to Ollama's HTTP API or
any other embedding backend. When the AI Model Orchestration Engine ships, it
becomes a second `EmbeddingProvider` implementation, swapped in via configuration
(docs/design/phase-1/00-shared-foundations.md).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class Embedding(BaseModel):
    """One computed embedding, tagged with the model that produced it.

    `model` is stamped onto every embedded row (as `embedding_model`, per
    docs/design/phase-1/01-memory-engine.md §10) so a future change to ADR-010's
    system-wide model choice is a background re-embedding job, not a schema
    migration or a silent correctness bug from mixing incompatible vector spaces.
    """

    vector: list[float]
    model: str
    dimensions: int


class EmbeddingProviderHealth(BaseModel):
    """Point-in-time health snapshot for an `EmbeddingProvider`."""

    available: bool
    backend: str
    model: str
    latency_ms: float | None = None
    error: str | None = None


@runtime_checkable
class EmbeddingProvider(Protocol):
    """The only interface any NOVA code may depend on to generate embeddings.

    Concrete backends (Ollama by default; see `nova_embeddings_sdk.backends`)
    implement this Protocol. Selecting a backend is a configuration decision
    (`nova_embeddings_sdk.factory.get_embedding_provider`), never an import
    decision -- no engine ever imports an embedding client library directly.
    """

    async def embed(self, text: str) -> Embedding:
        """Embed a single string."""
        ...

    async def embed_batch(self, texts: list[str]) -> list[Embedding]:
        """Embed multiple strings. Preferred over repeated `embed()` calls for
        anything beyond a handful of texts (docs/design/phase-1/01-memory-engine.md
        §10's `embedding_worker` always calls this, never `embed()` in a loop)."""
        ...

    async def health(self) -> EmbeddingProviderHealth:
        """Report the current backend health."""
        ...
