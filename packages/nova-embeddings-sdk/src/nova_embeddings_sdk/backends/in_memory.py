"""Deterministic in-process `EmbeddingProvider` backend: no external model, used for
unit/integration tests (see `nova-testkit`) and as a dependency-free default for
local development before Ollama is running.

Embeddings are derived from a seeded hash of the input text, not a real model --
identical text always produces the identical vector (useful for asserting
"duplicate detection found this pair" in tests, per docs/design/phase-1/
01-memory-engine.md §6), and different text produces different vectors, but the
vectors carry no real semantic meaning. Never use this backend to evaluate
retrieval quality.
"""

from __future__ import annotations

import hashlib
import time

from nova_embeddings_sdk.interface import Embedding, EmbeddingProviderHealth

DEFAULT_DIMENSIONS = 768  # matches ADR-010's nomic-embed-text standardization


class InMemoryEmbeddingProvider:
    """Reference `EmbeddingProvider` implementation with no external dependencies."""

    def __init__(
        self, *, dimensions: int = DEFAULT_DIMENSIONS, model: str = "fake-deterministic"
    ) -> None:
        self._dimensions = dimensions
        self._model = model

    async def embed(self, text: str) -> Embedding:
        return Embedding(
            vector=_deterministic_vector(text, self._dimensions),
            model=self._model,
            dimensions=self._dimensions,
        )

    async def embed_batch(self, texts: list[str]) -> list[Embedding]:
        return [await self.embed(text) for text in texts]

    async def health(self) -> EmbeddingProviderHealth:
        start = time.perf_counter()
        latency_ms = (time.perf_counter() - start) * 1000
        return EmbeddingProviderHealth(
            available=True, backend="in_memory", model=self._model, latency_ms=latency_ms
        )


def _deterministic_vector(text: str, dimensions: int) -> list[float]:
    vector: list[float] = []
    counter = 0
    while len(vector) < dimensions:
        digest = hashlib.sha256(f"{text}:{counter}".encode()).digest()
        for i in range(0, len(digest), 4):
            if len(vector) >= dimensions:
                break
            chunk = digest[i : i + 4]
            as_int = int.from_bytes(chunk, "big")
            vector.append((as_int / 0xFFFFFFFF) * 2 - 1)  # normalize to [-1, 1]
        counter += 1
    return vector
