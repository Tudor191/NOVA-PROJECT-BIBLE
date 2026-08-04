"""`workers/embedding_worker.py` -- async embedding generation off the write path
(docs/design/phase-1/01-memory-engine.md §10), against `FakeMemoryRepository` +
`InMemoryVectorStore` + `InMemoryEmbeddingProvider` + `InMemoryEventBus`.
"""

from uuid import uuid4

from nova_contracts import EventEnvelope
from nova_embeddings_sdk.backends.in_memory import InMemoryEmbeddingProvider
from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus
from nova_memory_engine.domain import long_term
from nova_memory_engine.domain.models import MemoryType
from nova_memory_engine.workers.embedding_worker import run_embedding_pass
from nova_vectorstore_sdk import VectorQuery
from nova_vectorstore_sdk.backends.in_memory import InMemoryVectorStore

from tests.fakes.memory_repository import FakeMemoryRepository


async def test_embeds_rows_with_null_embedding() -> None:
    repo = FakeMemoryRepository()
    vector_index = InMemoryVectorStore()
    await vector_index.connect()
    embeddings = InMemoryEmbeddingProvider()
    bus = InMemoryEventBus()
    await bus.connect()
    record = await long_term.write(
        repo,
        user_id=uuid4(),
        memory_type=MemoryType.SEMANTIC,
        content="needs an embedding",
        correlation_id=uuid4(),
    )
    assert record.embedding is None

    count = await run_embedding_pass(
        repo, vector_index, embeddings, bus, current_model="fake-deterministic"
    )

    assert count == 1
    query_embedding = await embeddings.embed(record.content)
    results = await vector_index.search(
        "memory_records", VectorQuery(vector=query_embedding.vector, top_k=1)
    )
    assert results[0].id == str(record.id)


async def test_embedding_completed_event_is_published() -> None:
    repo = FakeMemoryRepository()
    vector_index = InMemoryVectorStore()
    await vector_index.connect()
    embeddings = InMemoryEmbeddingProvider()
    bus = InMemoryEventBus()
    await bus.connect()
    received: list[EventEnvelope] = []

    async def handler(envelope: EventEnvelope) -> None:
        received.append(envelope)

    await bus.subscribe("memory.embedding.completed", handler)
    record = await long_term.write(
        repo,
        user_id=uuid4(),
        memory_type=MemoryType.SEMANTIC,
        content="needs an embedding",
        correlation_id=uuid4(),
    )

    await run_embedding_pass(
        repo, vector_index, embeddings, bus, current_model="fake-deterministic"
    )

    assert len(received) == 1
    assert received[0].payload["memory_id"] == str(record.id)
    assert received[0].payload["embedding_model"] == "fake-deterministic"


async def test_no_candidates_embeds_nothing() -> None:
    repo = FakeMemoryRepository()
    vector_index = InMemoryVectorStore()
    await vector_index.connect()
    embeddings = InMemoryEmbeddingProvider()
    bus = InMemoryEventBus()
    await bus.connect()

    count = await run_embedding_pass(
        repo, vector_index, embeddings, bus, current_model="fake-deterministic"
    )

    assert count == 0


async def test_stale_model_rows_are_re_embedded() -> None:
    repo = FakeMemoryRepository()
    vector_index = InMemoryVectorStore()
    await vector_index.connect()
    embeddings = InMemoryEmbeddingProvider()
    bus = InMemoryEventBus()
    await bus.connect()
    record = await long_term.write(
        repo,
        user_id=uuid4(),
        memory_type=MemoryType.SEMANTIC,
        content="already embedded with an old model",
        correlation_id=uuid4(),
    )
    repo.memories[record.id].embedding = [0.1, 0.2]
    repo.memories[record.id].embedding_model = "old-model"

    count = await run_embedding_pass(repo, vector_index, embeddings, bus, current_model="new-model")

    assert count == 1
