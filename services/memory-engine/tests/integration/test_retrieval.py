"""Full write -> retrieve round trip through `domain/retrieval.py`, fanning out to
both `VectorIndex` (semantic) and `MemoryRepository` (timeline) -- docs/design/
phase-1/01-memory-engine.md §7.
"""

from uuid import uuid4

from nova_embeddings_sdk.backends.in_memory import InMemoryEmbeddingProvider
from nova_memory_engine.domain import long_term, retrieval
from nova_memory_engine.domain.models import MemoryType
from nova_vectorstore_sdk import VectorRecord
from nova_vectorstore_sdk.backends.in_memory import InMemoryVectorStore

from tests.fakes.memory_repository import FakeMemoryRepository


async def _seeded_repo_and_index() -> (
    tuple[FakeMemoryRepository, InMemoryVectorStore, InMemoryEmbeddingProvider]
):
    repo = FakeMemoryRepository()
    vector_index = InMemoryVectorStore()
    await vector_index.connect()
    embeddings = InMemoryEmbeddingProvider()
    return repo, vector_index, embeddings


async def test_retrieve_finds_memory_via_timeline_when_no_query_text() -> None:
    repo, vector_index, embeddings = await _seeded_repo_and_index()
    user_id = uuid4()
    await long_term.write(
        repo,
        user_id=user_id,
        memory_type=MemoryType.SEMANTIC,
        content="the user prefers dark mode",
        correlation_id=uuid4(),
    )

    result = await retrieval.retrieve(
        retrieval.RetrievalQuery(user_id=user_id, correlation_id=uuid4()),
        repository=repo,
        vector_index=vector_index,
        embedding_provider=embeddings,
    )

    assert result.degraded is False
    assert len(result.results) == 1
    assert result.results[0].content == "the user prefers dark mode"


async def test_retrieve_finds_memory_via_semantic_search() -> None:
    repo, vector_index, embeddings = await _seeded_repo_and_index()
    user_id = uuid4()
    record = await long_term.write(
        repo,
        user_id=user_id,
        memory_type=MemoryType.SEMANTIC,
        content="the user prefers dark mode",
        correlation_id=uuid4(),
    )
    # Simulate what embedding_worker would have done asynchronously.
    embedded = await embeddings.embed(record.content)
    await vector_index.upsert(
        "memory_records",
        VectorRecord(
            id=str(record.id),
            vector=embedded.vector,
            metadata={
                "user_id": str(user_id),
                "memory_type": "semantic",
                "content": record.content,
                "importance_score": record.importance_score,
            },
        ),
    )

    result = await retrieval.retrieve(
        retrieval.RetrievalQuery(
            user_id=user_id, correlation_id=uuid4(), query_text="the user prefers dark mode"
        ),
        repository=repo,
        vector_index=vector_index,
        embedding_provider=embeddings,
    )

    assert result.degraded is False
    assert len(result.results) == 1
    assert result.results[0].memory_id == record.id
    assert result.results[0].similarity is not None
    assert result.results[0].similarity > 0.99  # deterministic embedding of identical text


async def test_retrieve_scopes_to_requesting_user() -> None:
    repo, vector_index, embeddings = await _seeded_repo_and_index()
    owner = uuid4()
    stranger = uuid4()
    await long_term.write(
        repo,
        user_id=owner,
        memory_type=MemoryType.SEMANTIC,
        content="owner's memory",
        correlation_id=uuid4(),
    )

    result = await retrieval.retrieve(
        retrieval.RetrievalQuery(user_id=stranger, correlation_id=uuid4()),
        repository=repo,
        vector_index=vector_index,
        embedding_provider=embeddings,
    )

    assert result.results == []


async def test_retrieve_degrades_gracefully_when_vector_index_unreachable() -> None:
    repo, _, embeddings = await _seeded_repo_and_index()
    user_id = uuid4()
    await long_term.write(
        repo,
        user_id=user_id,
        memory_type=MemoryType.SEMANTIC,
        content="still findable via timeline",
        correlation_id=uuid4(),
    )
    disconnected_vector_index = InMemoryVectorStore()  # never connected

    result = await retrieval.retrieve(
        retrieval.RetrievalQuery(
            user_id=user_id, correlation_id=uuid4(), query_text="a query"
        ),
        repository=repo,
        vector_index=disconnected_vector_index,
        embedding_provider=embeddings,
    )

    assert result.degraded is True
    # Falls back to timeline results rather than failing the whole read.
    assert len(result.results) == 1


async def test_retrieve_increments_access_count_on_returned_results() -> None:
    repo, vector_index, embeddings = await _seeded_repo_and_index()
    user_id = uuid4()
    record = await long_term.write(
        repo,
        user_id=user_id,
        memory_type=MemoryType.SEMANTIC,
        content="accessed memory",
        correlation_id=uuid4(),
    )
    assert repo.memories[record.id].access_count == 0

    await retrieval.retrieve(
        retrieval.RetrievalQuery(user_id=user_id, correlation_id=uuid4()),
        repository=repo,
        vector_index=vector_index,
        embedding_provider=embeddings,
    )

    assert repo.memories[record.id].access_count == 1
