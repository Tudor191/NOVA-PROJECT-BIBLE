"""Backend selection for `GraphStore` -- one configuration value, never a code
change, mirroring `nova_eventbus_sdk.factory` (ADR-006) and applying the same
pattern to graph persistence per ADR-007.
"""

from __future__ import annotations

import os
from collections.abc import Callable

from nova_graphstore_sdk.interface import GraphStore

_BackendFactory = Callable[[], GraphStore]

_BACKEND_FACTORIES: dict[str, _BackendFactory] = {}


def register_backend(name: str) -> Callable[[_BackendFactory], _BackendFactory]:
    """Register a factory function under `GRAPH_STORE_BACKEND=<name>`."""

    def _decorator(factory: _BackendFactory) -> _BackendFactory:
        _BACKEND_FACTORIES[name] = factory
        return factory

    return _decorator


def _build_in_memory() -> GraphStore:
    from nova_graphstore_sdk.backends.in_memory import InMemoryGraphStore

    return InMemoryGraphStore()


def _build_neo4j() -> GraphStore:
    from nova_graphstore_sdk.backends.neo4j import Neo4jGraphStore

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "nova_dev_password")
    return Neo4jGraphStore(uri=uri, user=user, password=password)


register_backend("in_memory")(_build_in_memory)
register_backend("neo4j")(_build_neo4j)


def get_graph_store(backend: str | None = None) -> GraphStore:
    """Return an unconnected `GraphStore` instance for the requested backend.

    `backend` defaults to the `GRAPH_STORE_BACKEND` environment variable, which
    defaults to `"neo4j"` -- the local-first default (docs/architecture/07 §4).
    Callers are responsible for calling `await store.connect()`.
    """
    resolved = backend or os.environ.get("GRAPH_STORE_BACKEND", "neo4j")
    try:
        factory = _BACKEND_FACTORIES[resolved]
    except KeyError as exc:
        available = ", ".join(sorted(_BACKEND_FACTORIES)) or "(none registered)"
        raise ValueError(
            f"Unknown GRAPH_STORE_BACKEND {resolved!r}. Available backends: {available}."
        ) from exc
    return factory()
