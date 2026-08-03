"""In-process VectorStore backend: no external database, used for unit/integration
tests (see `nova-testkit`) and as a dependency-free default for local development
before Postgres/pgvector is running.

Unlike `backends.pgvector.PgVectorStore`, which never owns the rows it writes into
(it updates a vector column on a row an engine's own repository already created),
this backend owns its records outright -- `upsert` here is a true create-or-update.
That asymmetry is deliberate and documented in the package README: the two backends
operate in genuinely different environments, not the same contract implemented
sloppily in one of them.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from nova_vectorstore_sdk.interface import VectorMatch, VectorQuery, VectorRecord, VectorStoreHealth


@dataclass
class _Collection:
    records: dict[str, VectorRecord] = field(default_factory=dict)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"Vector dimension mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class InMemoryVectorStore:
    """Reference `VectorStore` implementation with no external dependencies."""

    def __init__(self) -> None:
        self._connected = False
        self._collections: dict[str, _Collection] = {}

    async def connect(self) -> None:
        self._connected = True

    async def close(self) -> None:
        self._connected = False
        self._collections.clear()

    def _collection(self, name: str) -> _Collection:
        return self._collections.setdefault(name, _Collection())

    async def upsert(self, collection: str, record: VectorRecord) -> None:
        self._require_connected()
        self._collection(collection).records[record.id] = record

    async def upsert_batch(self, collection: str, records: list[VectorRecord]) -> None:
        self._require_connected()
        bucket = self._collection(collection)
        for record in records:
            bucket.records[record.id] = record

    async def search(self, collection: str, query: VectorQuery) -> list[VectorMatch]:
        self._require_connected()
        bucket = self._collection(collection)
        matches: list[VectorMatch] = []
        for record in bucket.records.values():
            if not _matches_filters(record.metadata, query.filters):
                continue
            score = _cosine_similarity(query.vector, record.vector)
            if query.min_score is not None and score < query.min_score:
                continue
            matches.append(VectorMatch(id=record.id, score=score, metadata=record.metadata))
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[: query.top_k]

    async def delete(self, collection: str, id: str) -> None:
        self._require_connected()
        self._collection(collection).records.pop(id, None)

    async def health(self) -> VectorStoreHealth:
        start = time.perf_counter()
        connected = self._connected
        latency_ms = (time.perf_counter() - start) * 1000
        return VectorStoreHealth(connected=connected, backend="in_memory", latency_ms=latency_ms)

    def _require_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("InMemoryVectorStore.connect() must be called before use.")


def _matches_filters(metadata: dict[str, object], filters: dict[str, object]) -> bool:
    return all(metadata.get(key) == value for key, value in filters.items())
