# nova-embeddings-sdk

The `EmbeddingProvider` interface (ADR-009, docs/architecture/00-overview-and-decisions.md).
**No engine may import an embedding model client directly** -- only this package.

- `interface.py` -- the `EmbeddingProvider` Protocol every caller depends on
  (`embed`/`embed_batch`/`health`).
- `factory.py` -- `get_embedding_provider()`, resolving the
  `EMBEDDING_PROVIDER_BACKEND` environment variable (`ollama` by default) to a
  concrete backend, and `EMBEDDING_MODEL` (`nomic-embed-text` by default, per
  ADR-010) to a model name.
- `backends/in_memory.py` -- dependency-free, deterministic backend for tests and
  local dev. Vectors are a seeded hash of the input text -- stable per input, useful
  for asserting duplicate-detection logic in tests, but carry no real semantic
  meaning. Never use this backend to evaluate retrieval quality.
- `backends/ollama.py` -- the default production backend, serving `nomic-embed-text`
  (768 dimensions, ADR-010) locally via Ollama's HTTP API, zero-budget per Bible
  Part 7.

## Adding a new backend (e.g. routing through the AI Model Orchestration Engine in Phase 2)

1. Create `backends/<name>.py` implementing every method on `EmbeddingProvider`.
2. Register it in `factory.py`: `register_backend("<name>")(_build_<name>)`.
3. Add the shared contract test suite (docs/architecture/16 §4) against the new
   backend to prove behavioral equivalence with `ollama`.

No other package needs to change -- this is what ADR-009 exists to guarantee. When
the AI Model Orchestration Engine ships (Phase 2), it becomes a second
`EmbeddingProvider` implementation, routing through the Model Gateway for provider
selection, cost tracking, and privacy classification
(docs/architecture/06-ai-layer-architecture.md §1), swapped in via configuration.

## Usage

```python
from nova_embeddings_sdk import get_embedding_provider

provider = get_embedding_provider()  # reads EMBEDDING_PROVIDER_BACKEND, defaults to "ollama"
embedding = await provider.embed("The user prefers dark mode.")
# embedding.vector, embedding.model, embedding.dimensions
```
