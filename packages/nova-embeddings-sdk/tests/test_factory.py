import pytest
from nova_embeddings_sdk.backends.in_memory import InMemoryEmbeddingProvider
from nova_embeddings_sdk.backends.ollama import OllamaEmbeddingProvider
from nova_embeddings_sdk.factory import get_embedding_provider


def test_default_backend_is_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EMBEDDING_PROVIDER_BACKEND", raising=False)
    provider = get_embedding_provider()
    assert isinstance(provider, OllamaEmbeddingProvider)


def test_explicit_in_memory_backend() -> None:
    provider = get_embedding_provider("in_memory")
    assert isinstance(provider, InMemoryEmbeddingProvider)


def test_env_var_selects_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER_BACKEND", "in_memory")
    provider = get_embedding_provider()
    assert isinstance(provider, InMemoryEmbeddingProvider)


def test_unknown_backend_raises_with_available_list() -> None:
    with pytest.raises(ValueError, match="in_memory"):
        get_embedding_provider("openai")


def test_ollama_backend_defaults_to_nomic_embed_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    provider = get_embedding_provider("ollama")
    assert isinstance(provider, OllamaEmbeddingProvider)
    assert provider._model == "nomic-embed-text"  # noqa: SLF001 -- verifying ADR-010 default
