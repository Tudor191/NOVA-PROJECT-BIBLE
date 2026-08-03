"""Tests for the parts of `backends.pgvector` that don't require a live Postgres:
identifier validation and collection registration. Behavioral parity with a real
database is exercised via integration tests against testcontainers
(docs/architecture/16-testing-strategy.md §3), not here.
"""

import pytest
from nova_vectorstore_sdk.backends.pgvector import PgVectorCollection, PgVectorStore


def test_valid_identifiers_accepted() -> None:
    PgVectorCollection(table="memory.memory_record", id_column="id", vector_column="embedding")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"table": "memory; DROP TABLE users;--"},
        {"table": "memory.memory_record", "id_column": "id; --"},
        {"table": "memory.memory_record", "vector_column": "embed ding"},
        {"table": "memory.memory_record", "metadata_columns": ("ok", "bad col")},
    ],
)
def test_invalid_identifiers_rejected(kwargs: dict[str, object]) -> None:
    defaults = {"table": "memory.memory_record"}
    defaults.update(kwargs)
    with pytest.raises(ValueError, match="Invalid SQL identifier"):
        PgVectorCollection(**defaults)  # type: ignore[arg-type]


def test_unknown_collection_raises_with_available_list() -> None:
    store = PgVectorStore(
        dsn="postgresql://localhost/nova",
        collections={"memories": PgVectorCollection(table="memory.memory_record")},
    )
    with pytest.raises(ValueError, match="memories"):
        store._collection("unknown")  # noqa: SLF001 -- exercising the lookup directly
