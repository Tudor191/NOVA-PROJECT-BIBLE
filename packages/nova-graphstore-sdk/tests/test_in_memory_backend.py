import pytest
from nova_graphstore_sdk.backends.in_memory import InMemoryGraphStore
from nova_graphstore_sdk.interface import (
    GraphQuery,
    PropertyFilter,
    TraversalDirection,
    TraversalSpec,
)


async def _connected_store() -> InMemoryGraphStore:
    store = InMemoryGraphStore()
    await store.connect()
    return store


async def test_upsert_node_is_idempotent_and_merges_properties() -> None:
    store = await _connected_store()
    await store.upsert_node("Concept", "n1", {"name": "Python"})
    await store.upsert_node("Concept", "n1", {"confidence": 0.9})

    result = await store.query(GraphQuery(label="Concept"))

    assert len(result.nodes) == 1
    assert result.nodes[0].properties == {"name": "Python", "confidence": 0.9}


async def test_query_filters_by_label_and_property() -> None:
    store = await _connected_store()
    await store.upsert_node("Concept", "n1", {"name": "Python"})
    await store.upsert_node("Concept", "n2", {"name": "Rust"})
    await store.upsert_node("Technology", "n3", {"name": "Docker"})

    result = await store.query(
        GraphQuery(
            label="Concept", filters=[PropertyFilter(property="name", op="eq", value="Python")]
        )
    )

    assert [n.id for n in result.nodes] == ["n1"]


async def test_query_returns_directly_attached_relationships() -> None:
    store = await _connected_store()
    await store.upsert_node("Concept", "n1", {})
    await store.upsert_node("Concept", "n2", {})
    await store.upsert_relationship("n1", "RELATED_TO", "n2")

    result = await store.query(GraphQuery(label="Concept"))

    assert any(r.from_id == "n1" and r.to_id == "n2" for r in result.relationships)


async def test_traverse_respects_max_hops() -> None:
    store = await _connected_store()
    for i in range(4):
        await store.upsert_node("Node", str(i), {})
    for i in range(3):
        await store.upsert_relationship(str(i), "NEXT", str(i + 1))

    result = await store.traverse("0", TraversalSpec(max_hops=2))

    reached = {n.id for n in result.nodes}
    assert reached == {"1", "2"}


async def test_traverse_respects_relationship_type_filter() -> None:
    store = await _connected_store()
    await store.upsert_node("Node", "a", {})
    await store.upsert_node("Node", "b", {})
    await store.upsert_node("Node", "c", {})
    await store.upsert_relationship("a", "USES", "b")
    await store.upsert_relationship("a", "CONFLICTS_WITH", "c")

    result = await store.traverse("a", TraversalSpec(relationship_types=("USES",), max_hops=1))

    assert {n.id for n in result.nodes} == {"b"}


async def test_traverse_respects_direction() -> None:
    store = await _connected_store()
    await store.upsert_node("Node", "a", {})
    await store.upsert_node("Node", "b", {})
    await store.upsert_relationship("a", "USES", "b")

    outgoing_from_b = await store.traverse(
        "b", TraversalSpec(direction=TraversalDirection.OUTGOING, max_hops=1)
    )
    incoming_to_b = await store.traverse(
        "b", TraversalSpec(direction=TraversalDirection.INCOMING, max_hops=1)
    )

    assert outgoing_from_b.nodes == []
    assert {n.id for n in incoming_to_b.nodes} == {"a"}


async def test_traverse_respects_target_labels() -> None:
    store = await _connected_store()
    await store.upsert_node("Concept", "start", {})
    await store.upsert_node("Technology", "tech", {})
    await store.upsert_node("Person", "person", {})
    await store.upsert_relationship("start", "USES", "tech")
    await store.upsert_relationship("start", "CREATED_BY", "person")

    result = await store.traverse("start", TraversalSpec(target_labels=("Technology",), max_hops=1))

    assert {n.id for n in result.nodes} == {"tech"}


async def test_delete_node_removes_node_and_its_relationships() -> None:
    store = await _connected_store()
    await store.upsert_node("Node", "a", {})
    await store.upsert_node("Node", "b", {})
    await store.upsert_relationship("a", "REL", "b")

    await store.delete_node("a")

    result = await store.query(GraphQuery(label="Node"))
    assert [n.id for n in result.nodes] == ["b"]
    assert result.relationships == []


async def test_operations_require_connect_first() -> None:
    store = InMemoryGraphStore()
    with pytest.raises(RuntimeError):
        await store.query(GraphQuery(label="Node"))
