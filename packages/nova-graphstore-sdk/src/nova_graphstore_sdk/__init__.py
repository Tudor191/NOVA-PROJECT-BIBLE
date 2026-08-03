"""nova-graphstore-sdk: the GraphStore interface (ADR-007) and its backends.

No engine may import a graph database client (`neo4j`, or any future alternative)
directly -- only this package's `GraphStore` Protocol and `get_graph_store()`
factory.
"""

from nova_graphstore_sdk.boundary import BoundGraphStore, LabelNotAllowedError
from nova_graphstore_sdk.factory import get_graph_store, register_backend
from nova_graphstore_sdk.interface import (
    FilterOp,
    GraphNode,
    GraphPath,
    GraphQuery,
    GraphRelationship,
    GraphResult,
    GraphStore,
    GraphStoreHealth,
    PropertyFilter,
    TraversalDirection,
    TraversalSpec,
)

__all__ = [
    "BoundGraphStore",
    "FilterOp",
    "GraphNode",
    "GraphPath",
    "GraphQuery",
    "GraphRelationship",
    "GraphResult",
    "GraphStore",
    "GraphStoreHealth",
    "LabelNotAllowedError",
    "PropertyFilter",
    "TraversalDirection",
    "TraversalSpec",
    "get_graph_store",
    "register_backend",
]
