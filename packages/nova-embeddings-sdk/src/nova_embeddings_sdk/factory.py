"""Backend selection for `EmbeddingProvider` -- one configuration value, never a
code change, mirroring `nova_eventbus_sdk.factory` (ADR-006) and applying the same
pattern to embedding generation per ADR-009.
"""

from __future__ import annotations

import os
from collections.abc import Callable

from nova_embeddings_sdk.interface import EmbeddingProvider

_BackendFactory = Callable[[], EmbeddingProvider]

_BACKEND_FACTORIES: dict[str, _BackendFactory] = {}


def register_backend(name: str) -> Callable[[_BackendFactory], _BackendFactory]:
    """Register a factory function under `EMBEDDING_PROVIDER_BACKEND=<name>`."""

    def _decorator(factory: _BackendFactory) -> _BackendFactory:
        _BACKEND_FACTORIES[name] = factory
        return factory

    return _decorator


def _build_in_memory() -> EmbeddingProvider:
    from nova_embeddings_sdk.backends.in_memory import InMemoryEmbeddingProvider

    return InMemoryEmbeddingProvider()


def _build_ollama() -> EmbeddingProvider:
    from nova_embeddings_sdk.backends.ollama import DEFAULT_MODEL, OllamaEmbeddingProvider

    base_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    model = os.environ.get("EMBEDDING_MODEL", DEFAULT_MODEL)
    return OllamaEmbeddingProvider(base_url=base_url, model=model)


register_backend("in_memory")(_build_in_memory)
register_backend("ollama")(_build_ollama)


def get_embedding_provider(backend: str | None = None) -> EmbeddingProvider:
    """Return an `EmbeddingProvider` instance for the requested backend.

    `backend` defaults to the `EMBEDDING_PROVIDER_BACKEND` environment variable,
    which defaults to `"ollama"` -- the local-first, zero-budget default (ADR-009,
    Bible Part 7). The model served defaults to `EMBEDDING_MODEL`, which defaults to
    `nomic-embed-text` per ADR-010.
    """
    resolved = backend or os.environ.get("EMBEDDING_PROVIDER_BACKEND", "ollama")
    try:
        factory = _BACKEND_FACTORIES[resolved]
    except KeyError as exc:
        available = ", ".join(sorted(_BACKEND_FACTORIES)) or "(none registered)"
        raise ValueError(
            f"Unknown EMBEDDING_PROVIDER_BACKEND {resolved!r}. Available backends: {available}."
        ) from exc
    return factory()
