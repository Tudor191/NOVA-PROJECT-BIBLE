"""Ollama `EmbeddingProvider` backend -- the default implementation (ADR-009),
serving ADR-010's standardized `nomic-embed-text` (768 dimensions) model locally,
zero-budget, per Bible Part 7.

This module lazily imports `httpx` inside each method (not at module scope) so that
importing `nova_embeddings_sdk` never requires an Ollama server to be reachable,
mirroring `nova_eventbus_sdk.backends.nats`.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from nova_embeddings_sdk.interface import Embedding, EmbeddingProviderHealth

if TYPE_CHECKING:
    import httpx

DEFAULT_MODEL = "nomic-embed-text"  # ADR-010
DEFAULT_DIMENSIONS = 768  # ADR-010


class OllamaEmbeddingProvider:
    """`EmbeddingProvider` implementation backed by a local Ollama server."""

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434",
        model: str = DEFAULT_MODEL,
        dimensions: int = DEFAULT_DIMENSIONS,
        timeout_s: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._dimensions = dimensions
        self._timeout_s = timeout_s
        self._client: httpx.AsyncClient | None = None

    def _ensure_client(self) -> httpx.AsyncClient:
        # No `await` between the None-check and assignment below, so this is safe
        # under concurrent asyncio tasks (cooperative scheduling: no yield point to
        # interleave on) despite not using a lock.
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout_s)
        return self._client

    async def embed(self, text: str) -> Embedding:
        client = self._ensure_client()
        response = await client.post(
            "/api/embeddings", json={"model": self._model, "prompt": text}
        )
        response.raise_for_status()
        vector = response.json()["embedding"]
        return Embedding(vector=vector, model=self._model, dimensions=len(vector))

    async def embed_batch(self, texts: list[str]) -> list[Embedding]:
        import asyncio

        return list(await asyncio.gather(*(self.embed(text) for text in texts)))

    async def health(self) -> EmbeddingProviderHealth:
        start = time.perf_counter()
        try:
            client = self._ensure_client()
            response = await client.get("/api/tags")
            response.raise_for_status()
            latency_ms = (time.perf_counter() - start) * 1000
            return EmbeddingProviderHealth(
                available=True, backend="ollama", model=self._model, latency_ms=latency_ms
            )
        except Exception as exc:  # noqa: BLE001 -- health checks must never raise
            return EmbeddingProviderHealth(
                available=False, backend="ollama", model=self._model, error=str(exc)
            )
