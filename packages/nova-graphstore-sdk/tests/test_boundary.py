import pytest
from nova_graphstore_sdk.backends.in_memory import InMemoryGraphStore
from nova_graphstore_sdk.boundary import BoundGraphStore, LabelNotAllowedError
from nova_graphstore_sdk.interface import GraphQuery, TraversalSpec


async def _bound_store(
    *, allowed_labels: frozenset[str], allowed_relationship_types: frozenset[str] = frozenset()
) -> BoundGraphStore:
    inner = InMemoryGraphStore()
    await inner.connect()
    return BoundGraphStore(
        inner,
        engine_name="knowledge-engine",
        allowed_labels=allowed_labels,
        allowed_relationship_types=allowed_relationship_types,
    )


async def test_upsert_node_outside_allow_list_is_rejected() -> None:
    store = await _bound_store(allowed_labels=frozenset({"Concept"}))
    with pytest.raises(LabelNotAllowedError):
        await store.upsert_node("WorldProject", "n1", {})


async def test_upsert_node_within_allow_list_succeeds() -> None:
    store = await _bound_store(allowed_labels=frozenset({"Concept"}))
    await store.upsert_node("Concept", "n1", {})  # should not raise


async def test_upsert_relationship_outside_allow_list_is_rejected() -> None:
    store = await _bound_store(
        allowed_labels=frozenset({"Concept"}), allowed_relationship_types=frozenset({"USES"})
    )
    with pytest.raises(LabelNotAllowedError):
        await store.upsert_relationship("a", "CONFLICTS_WITH", "b")


async def test_query_outside_allow_list_is_rejected() -> None:
    store = await _bound_store(allowed_labels=frozenset({"Concept"}))
    with pytest.raises(LabelNotAllowedError):
        await store.query(GraphQuery(label="WorldProject"))


async def test_traverse_target_label_outside_allow_list_is_rejected() -> None:
    store = await _bound_store(allowed_labels=frozenset({"Concept"}))
    with pytest.raises(LabelNotAllowedError):
        await store.traverse("n1", TraversalSpec(target_labels=("WorldProject",)))


async def test_delete_node_is_not_label_checked() -> None:
    store = await _bound_store(allowed_labels=frozenset({"Concept"}))
    await store.upsert_node("Concept", "n1", {})
    await store.delete_node("n1")  # should not raise -- see boundary.py module docstring
