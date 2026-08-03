import pytest
from nova_graphstore_sdk.backends.in_memory import InMemoryGraphStore
from nova_graphstore_sdk.backends.neo4j import Neo4jGraphStore
from nova_graphstore_sdk.factory import get_graph_store


def test_default_backend_is_neo4j(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GRAPH_STORE_BACKEND", raising=False)
    store = get_graph_store()
    assert isinstance(store, Neo4jGraphStore)


def test_explicit_in_memory_backend() -> None:
    store = get_graph_store("in_memory")
    assert isinstance(store, InMemoryGraphStore)


def test_env_var_selects_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRAPH_STORE_BACKEND", "in_memory")
    store = get_graph_store()
    assert isinstance(store, InMemoryGraphStore)


def test_unknown_backend_raises_with_available_list() -> None:
    with pytest.raises(ValueError, match="in_memory"):
        get_graph_store("memgraph")
