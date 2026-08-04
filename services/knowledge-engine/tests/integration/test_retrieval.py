"""`domain/retrieval.py` against real `InMemoryVectorStore`/`InMemoryGraphStore`
backends (not the HTTP layer) -- exercises the semantic + graph + name fan-out
directly.
"""

from uuid import uuid4

from nova_embeddings_sdk.backends.in_memory import InMemoryEmbeddingProvider
from nova_graphstore_sdk.backends.in_memory import InMemoryGraphStore
from nova_knowledge_engine.domain import retrieval
from nova_knowledge_engine.domain.models import KnowledgeNode
from nova_vectorstore_sdk import VectorRecord
from nova_vectorstore_sdk.backends.in_memory import InMemoryVectorStore

from tests.fakes.metadata_repository import FakeKnowledgeMetadataRepository

VECTOR_COLLECTION = retrieval.DEFAULT_VECTOR_COLLECTION


async def _setup(
    repository: FakeKnowledgeMetadataRepository,
    vector_index: InMemoryVectorStore,
    embedding_provider: InMemoryEmbeddingProvider,
) -> KnowledgeNode:
    postgres_node = KnowledgeNode(
        node_id="technology:postgresql",
        label="Technology",
        name="PostgreSQL",
        embedding_model="test-model",
    )
    repository.nodes[postgres_node.node_id] = postgres_node

    embedding = await embedding_provider.embed("PostgreSQL")
    await vector_index.upsert(
        VECTOR_COLLECTION,
        VectorRecord(id=postgres_node.node_id, vector=embedding.vector, metadata={}),
    )
    return postgres_node


async def test_semantic_search_finds_node_by_embedding() -> None:
    repository = FakeKnowledgeMetadataRepository()
    vector_index = InMemoryVectorStore()
    await vector_index.connect()
    embedding_provider = InMemoryEmbeddingProvider()
    graph_store = InMemoryGraphStore()
    await graph_store.connect()

    node = await _setup(repository, vector_index, embedding_provider)

    result = await retrieval.retrieve(
        retrieval.RetrievalQuery(correlation_id=uuid4(), query_text="PostgreSQL"),
        repository=repository,
        vector_index=vector_index,
        embedding_provider=embedding_provider,
        graph_store=graph_store,
    )

    assert not result.degraded
    assert any(r.node_id == node.node_id for r in result.results)


async def test_name_search_finds_node_without_embedding() -> None:
    repository = FakeKnowledgeMetadataRepository()
    vector_index = InMemoryVectorStore()
    await vector_index.connect()
    embedding_provider = InMemoryEmbeddingProvider()
    graph_store = InMemoryGraphStore()
    await graph_store.connect()

    node = KnowledgeNode(node_id="technology:redis", label="Technology", name="Redis")
    repository.nodes[node.node_id] = node

    result = await retrieval.retrieve(
        retrieval.RetrievalQuery(correlation_id=uuid4(), query_text="Redis"),
        repository=repository,
        vector_index=vector_index,
        embedding_provider=embedding_provider,
        graph_store=graph_store,
    )

    assert any(r.node_id == node.node_id for r in result.results)


async def test_graph_traversal_from_seed_surfaces_connected_node() -> None:
    repository = FakeKnowledgeMetadataRepository()
    vector_index = InMemoryVectorStore()
    await vector_index.connect()
    embedding_provider = InMemoryEmbeddingProvider()
    graph_store = InMemoryGraphStore()
    await graph_store.connect()

    seed = KnowledgeNode(node_id="technology:postgresql", label="Technology", name="PostgreSQL")
    neighbor = KnowledgeNode(node_id="technology:pgvector", label="Technology", name="pgvector")
    repository.nodes[seed.node_id] = seed
    repository.nodes[neighbor.node_id] = neighbor
    await graph_store.upsert_node("Technology", seed.node_id, {})
    await graph_store.upsert_node("Technology", neighbor.node_id, {})
    await graph_store.upsert_relationship(seed.node_id, "DEPENDS_ON", neighbor.node_id, {})

    result = await retrieval.retrieve(
        retrieval.RetrievalQuery(correlation_id=uuid4(), seed_node_id=seed.node_id),
        repository=repository,
        vector_index=vector_index,
        embedding_provider=embedding_provider,
        graph_store=graph_store,
    )

    # The seed itself is the traversal anchor, not a "result" unless it also
    # matches semantically/by name (neither leg runs here, no query_text) --
    # only the node it's connected to is surfaced.
    node_ids = {r.node_id for r in result.results}
    assert neighbor.node_id in node_ids
    neighbor_result = next(r for r in result.results if r.node_id == neighbor.node_id)
    assert seed.node_id in neighbor_result.related_node_ids


async def test_unreachable_graph_store_degrades_gracefully() -> None:
    repository = FakeKnowledgeMetadataRepository()
    vector_index = InMemoryVectorStore()
    await vector_index.connect()
    embedding_provider = InMemoryEmbeddingProvider()
    graph_store = InMemoryGraphStore()  # never connected -- traverse() raises

    node = KnowledgeNode(node_id="technology:redis", label="Technology", name="Redis")
    repository.nodes[node.node_id] = node

    result = await retrieval.retrieve(
        retrieval.RetrievalQuery(correlation_id=uuid4(), seed_node_id=node.node_id),
        repository=repository,
        vector_index=vector_index,
        embedding_provider=embedding_provider,
        graph_store=graph_store,
    )

    assert result.degraded is True
