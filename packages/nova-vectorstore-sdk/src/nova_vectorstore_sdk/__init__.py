"""nova-vectorstore-sdk: the VectorStore interface and its backends.

No engine may import a vector database client (`asyncpg`+`pgvector`, or any future
alternative) directly -- only this package's `VectorStore` Protocol and
`get_vector_store()` factory.
"""

from nova_vectorstore_sdk.factory import get_vector_store, register_backend
from nova_vectorstore_sdk.interface import (
    VectorMatch,
    VectorQuery,
    VectorRecord,
    VectorStore,
    VectorStoreHealth,
)

__all__ = [
    "VectorMatch",
    "VectorQuery",
    "VectorRecord",
    "VectorStore",
    "VectorStoreHealth",
    "get_vector_store",
    "register_backend",
]
