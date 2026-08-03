"""nova-embeddings-sdk: the EmbeddingProvider interface (ADR-009) and its backends.

No engine may import an embedding model client directly -- only this package's
`EmbeddingProvider` Protocol and `get_embedding_provider()` factory.
"""

from nova_embeddings_sdk.factory import get_embedding_provider, register_backend
from nova_embeddings_sdk.interface import Embedding, EmbeddingProvider, EmbeddingProviderHealth

__all__ = [
    "Embedding",
    "EmbeddingProvider",
    "EmbeddingProviderHealth",
    "get_embedding_provider",
    "register_backend",
]
