import pytest
from nova_vectorstore_sdk.backends.in_memory import InMemoryVectorStore
from nova_vectorstore_sdk.interface import VectorQuery, VectorRecord


async def _connected_store() -> InMemoryVectorStore:
    store = InMemoryVectorStore()
    await store.connect()
    return store


async def test_search_ranks_by_cosine_similarity() -> None:
    store = await _connected_store()
    await store.upsert("memories", VectorRecord(id="a", vector=[1.0, 0.0]))
    await store.upsert("memories", VectorRecord(id="b", vector=[0.0, 1.0]))
    await store.upsert("memories", VectorRecord(id="c", vector=[0.9, 0.1]))

    results = await store.search("memories", VectorQuery(vector=[1.0, 0.0], top_k=10))

    assert [r.id for r in results] == ["a", "c", "b"]
    assert results[0].score == pytest.approx(1.0)


async def test_search_respects_top_k() -> None:
    store = await _connected_store()
    for i in range(5):
        await store.upsert("memories", VectorRecord(id=str(i), vector=[float(i), 0.0]))

    results = await store.search("memories", VectorQuery(vector=[1.0, 0.0], top_k=2))

    assert len(results) == 2


async def test_search_applies_metadata_filters() -> None:
    store = await _connected_store()
    await store.upsert(
        "memories",
        VectorRecord(id="mine", vector=[1.0, 0.0], metadata={"user_id": "u1"}),
    )
    await store.upsert(
        "memories",
        VectorRecord(id="theirs", vector=[1.0, 0.0], metadata={"user_id": "u2"}),
    )

    results = await store.search(
        "memories", VectorQuery(vector=[1.0, 0.0], top_k=10, filters={"user_id": "u1"})
    )

    assert [r.id for r in results] == ["mine"]


async def test_search_applies_min_score() -> None:
    store = await _connected_store()
    await store.upsert("memories", VectorRecord(id="close", vector=[1.0, 0.0]))
    await store.upsert("memories", VectorRecord(id="far", vector=[0.0, 1.0]))

    results = await store.search(
        "memories", VectorQuery(vector=[1.0, 0.0], top_k=10, min_score=0.5)
    )

    assert [r.id for r in results] == ["close"]


async def test_upsert_overwrites_existing_record() -> None:
    store = await _connected_store()
    await store.upsert("memories", VectorRecord(id="a", vector=[1.0, 0.0]))
    await store.upsert("memories", VectorRecord(id="a", vector=[0.0, 1.0]))

    results = await store.search("memories", VectorQuery(vector=[0.0, 1.0], top_k=10))

    assert len(results) == 1
    assert results[0].score == pytest.approx(1.0)


async def test_delete_removes_record_from_search() -> None:
    store = await _connected_store()
    await store.upsert("memories", VectorRecord(id="a", vector=[1.0, 0.0]))

    await store.delete("memories", "a")
    results = await store.search("memories", VectorQuery(vector=[1.0, 0.0], top_k=10))

    assert results == []


async def test_upsert_batch() -> None:
    store = await _connected_store()
    records = [VectorRecord(id=str(i), vector=[float(i), 0.0]) for i in range(3)]

    await store.upsert_batch("memories", records)
    results = await store.search("memories", VectorQuery(vector=[1.0, 0.0], top_k=10))

    assert {r.id for r in results} == {"0", "1", "2"}


async def test_operations_require_connect_first() -> None:
    store = InMemoryVectorStore()
    with pytest.raises(RuntimeError):
        await store.search("memories", VectorQuery(vector=[1.0, 0.0]))


async def test_health_reports_connection_state() -> None:
    store = InMemoryVectorStore()
    disconnected = await store.health()
    assert disconnected.connected is False

    await store.connect()
    connected = await store.health()
    assert connected.connected is True
    assert connected.backend == "in_memory"
