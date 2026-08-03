"""Backend selection for `VectorStore` -- one configuration value, never a code
change, mirroring `nova_eventbus_sdk.factory` (ADR-006) and applying the same
pattern to vector storage per docs/design/phase-1/00-shared-foundations.md.
"""

from __future__ import annotations

import os
from collections.abc import Callable

from nova_vectorstore_sdk.interface import VectorStore

_BackendFactory = Callable[[], VectorStore]

_BACKEND_FACTORIES: dict[str, _BackendFactory] = {}


def register_backend(name: str) -> Callable[[_BackendFactory], _BackendFactory]:
    """Register a factory function under `VECTOR_STORE_BACKEND=<name>`."""

    def _decorator(factory: _BackendFactory) -> _BackendFactory:
        _BACKEND_FACTORIES[name] = factory
        return factory

    return _decorator


def _build_in_memory() -> VectorStore:
    from nova_vectorstore_sdk.backends.in_memory import InMemoryVectorStore

    return InMemoryVectorStore()


def _build_pgvector() -> VectorStore:
    from nova_vectorstore_sdk.backends.pgvector import PgVectorStore

    dsn = os.environ.get("POSTGRES_DSN", "postgresql://nova:nova_dev_password@localhost:5432/nova")
    return PgVectorStore(dsn=dsn, collections={})


register_backend("in_memory")(_build_in_memory)
register_backend("pgvector")(_build_pgvector)


def get_vector_store(backend: str | None = None) -> VectorStore:
    """Return an unconnected `VectorStore` instance for the requested backend.

    `backend` defaults to the `VECTOR_STORE_BACKEND` environment variable, which
    defaults to `"pgvector"` -- the local-first default (docs/architecture/07 §3).
    Callers are responsible for calling `await store.connect()`.

    The `pgvector` backend is constructed with no collections registered; callers
    that need one build their own `PgVectorStore(dsn, collections={...})` directly
    (`get_vector_store` exists for the common case where a caller only needs the
    generic Protocol and doesn't yet know its collection map at factory-call time).
    """
    resolved = backend or os.environ.get("VECTOR_STORE_BACKEND", "pgvector")
    try:
        factory = _BACKEND_FACTORIES[resolved]
    except KeyError as exc:
        available = ", ".join(sorted(_BACKEND_FACTORIES)) or "(none registered)"
        raise ValueError(
            f"Unknown VECTOR_STORE_BACKEND {resolved!r}. Available backends: {available}."
        ) from exc
    return factory()
