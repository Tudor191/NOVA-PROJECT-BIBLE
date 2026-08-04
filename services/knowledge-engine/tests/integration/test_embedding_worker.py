from nova_embeddings_sdk.backends.in_memory import InMemoryEmbeddingProvider
from nova_knowledge_engine.domain.models import KnowledgeNode
from nova_knowledge_engine.workers.embedding_worker import run_embedding_pass
from nova_vectorstore_sdk import VectorQuery
from nova_vectorstore_sdk.backends.in_memory import InMemoryVectorStore

from tests.fakes.metadata_repository import FakeKnowledgeMetadataRepository


async def test_embeds_nodes_missing_a_vector() -> None:
    repository = FakeKnowledgeMetadataRepository()
    vector_index = InMemoryVectorStore()
    await vector_index.connect()
    embedding_provider = InMemoryEmbeddingProvider()

    node = KnowledgeNode(node_id="technology:postgresql", label="Technology", name="PostgreSQL")
    repository.nodes[node.node_id] = node

    count = await run_embedding_pass(
        repository, vector_index, embedding_provider, current_model="test-model"
    )

    assert count == 1
    matches = await vector_index.search(
        "knowledge_nodes",
        VectorQuery(vector=(await embedding_provider.embed("PostgreSQL")).vector, top_k=1),
    )
    assert matches[0].id == node.node_id


async def test_re_embeds_stale_model_nodes() -> None:
    repository = FakeKnowledgeMetadataRepository()
    vector_index = InMemoryVectorStore()
    await vector_index.connect()
    embedding_provider = InMemoryEmbeddingProvider()

    node = KnowledgeNode(
        node_id="technology:redis",
        label="Technology",
        name="Redis",
        embedding=[0.1, 0.2, 0.3],
        embedding_model="old-model",
    )
    repository.nodes[node.node_id] = node

    count = await run_embedding_pass(
        repository, vector_index, embedding_provider, current_model="new-model"
    )

    assert count == 1


async def test_no_candidates_is_a_no_op() -> None:
    repository = FakeKnowledgeMetadataRepository()
    vector_index = InMemoryVectorStore()
    await vector_index.connect()
    embedding_provider = InMemoryEmbeddingProvider()

    count = await run_embedding_pass(
        repository, vector_index, embedding_provider, current_model="test-model"
    )

    assert count == 0
