import pytest
from nova_vectorstore_sdk.backends.in_memory import InMemoryVectorStore
from nova_vectorstore_sdk.backends.pgvector import PgVectorStore
from nova_vectorstore_sdk.factory import get_vector_store


def test_default_backend_is_pgvector(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VECTOR_STORE_BACKEND", raising=False)
    store = get_vector_store()
    assert isinstance(store, PgVectorStore)


def test_explicit_in_memory_backend() -> None:
    store = get_vector_store("in_memory")
    assert isinstance(store, InMemoryVectorStore)


def test_env_var_selects_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VECTOR_STORE_BACKEND", "in_memory")
    store = get_vector_store()
    assert isinstance(store, InMemoryVectorStore)


def test_unknown_backend_raises_with_available_list() -> None:
    with pytest.raises(ValueError, match="in_memory"):
        get_vector_store("qdrant")
