from nova_embeddings_sdk.backends.in_memory import DEFAULT_DIMENSIONS, InMemoryEmbeddingProvider


async def test_embed_is_deterministic() -> None:
    provider = InMemoryEmbeddingProvider()
    first = await provider.embed("hello world")
    second = await provider.embed("hello world")

    assert first.vector == second.vector


async def test_embed_differs_for_different_text() -> None:
    provider = InMemoryEmbeddingProvider()
    a = await provider.embed("hello")
    b = await provider.embed("goodbye")

    assert a.vector != b.vector


async def test_embed_has_default_dimensions() -> None:
    provider = InMemoryEmbeddingProvider()
    result = await provider.embed("some text")

    assert result.dimensions == DEFAULT_DIMENSIONS
    assert len(result.vector) == DEFAULT_DIMENSIONS


async def test_embed_respects_custom_dimensions() -> None:
    provider = InMemoryEmbeddingProvider(dimensions=16)
    result = await provider.embed("some text")

    assert result.dimensions == 16
    assert len(result.vector) == 16


async def test_embed_batch_matches_individual_embed_calls() -> None:
    provider = InMemoryEmbeddingProvider()
    texts = ["one", "two", "three"]

    batch_results = await provider.embed_batch(texts)
    individual_results = [await provider.embed(t) for t in texts]

    assert [r.vector for r in batch_results] == [r.vector for r in individual_results]


async def test_health_reports_available() -> None:
    provider = InMemoryEmbeddingProvider()
    health = await provider.health()

    assert health.available is True
    assert health.backend == "in_memory"
