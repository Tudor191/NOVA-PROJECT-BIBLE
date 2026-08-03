"""Tests for the parts of `backends.neo4j` that don't require a live database:
identifier validation, which guards against Cypher injection since labels and
relationship types can't be parameterized. Behavioral parity with the in-memory
backend is exercised via integration tests against testcontainers
(docs/architecture/16-testing-strategy.md §3), not here.
"""

import pytest
from nova_graphstore_sdk.backends.neo4j import _validate_identifier


def test_valid_identifier_accepted() -> None:
    assert _validate_identifier("Concept") == "Concept"
    assert _validate_identifier("RELATED_TO") == "RELATED_TO"


@pytest.mark.parametrize("bad", ["Concept `MATCH", "Concept)", "Concept OR 1=1", ""])
def test_invalid_identifier_rejected(bad: str) -> None:
    with pytest.raises(ValueError, match="Invalid Cypher"):
        _validate_identifier(bad)
