"""Verifies `nova_testkit.neo4j`'s fixtures against a real Neo4j container --
real node/relationship creation, real traversal, and isolation between tests
via `DETACH DELETE` (implementation plan §13's verification bar).

`@pytest.mark.real_infra`: excluded from the default `pytest`/`turbo run test`
invocation (ADR-033) -- requires Docker. **Not executed in the environment
this file was written in** (no reachable Docker daemon there); see
`neo4j.py`'s own module docstring.
"""

import pytest
from neo4j import AsyncDriver

pytestmark = pytest.mark.real_infra


async def test_real_node_and_relationship_creation_and_traversal(
    neo4j_driver: AsyncDriver,
) -> None:
    async with neo4j_driver.session() as session:
        await session.run(
            "CREATE (a:Widget {name: 'gizmo'})-[:CONNECTS_TO]->(b:Widget {name: 'gadget'})"
        )

        result = await session.run(
            "MATCH (a:Widget {name: 'gizmo'})-[:CONNECTS_TO]->(b:Widget) RETURN b.name AS name"
        )
        record = await result.single()

    assert record is not None
    assert record["name"] == "gadget"


async def test_detach_delete_isolates_each_test(neo4j_driver: AsyncDriver) -> None:
    """Runs after the test above in file order; if `DETACH DELETE` isolation
    were broken, the `gizmo`/`gadget` nodes would still be present here."""
    async with neo4j_driver.session() as session:
        result = await session.run("MATCH (n:Widget) RETURN count(n) AS n")
        record = await result.single()

    assert record is not None
    assert record["n"] == 0
