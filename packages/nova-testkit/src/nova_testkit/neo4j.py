"""Real-Neo4j test fixtures via `testcontainers` (ADR-033's real-infrastructure
tier; docs/design/nova-testkit/technical-implementation-plan.md §2.4, §3.2).

`neo4j_container` starts one throwaway `neo4j:5-community` container -- the
exact image `infra/docker/docker-compose.local.yml`'s `neo4j` service already
pins -- with the same `apoc` plugin enabled (`NEO4J_PLUGINS`), since
`nova-graphstore-sdk`'s real backend depends on APOC being available and a test
container that doesn't enable it would silently under-test that dependency.
`neo4j_driver` yields a real, async `neo4j.AsyncDriver`, constructed the same
way `nova_graphstore_sdk.backends.neo4j.Neo4jGraphStore.connect()` does
(`AsyncGraphDatabase.driver(uri, auth=(user, password))`) -- not the container
class's own `get_driver()` (which returns a *sync* `neo4j.Driver`, wrong for
this fully-async codebase).

**Unverified in this environment**: written against `testcontainers==4.13.3`'s
real, installed API (confirmed by direct introspection), but never executed
against a real container here -- no Docker daemon reachable (confirmed).
Every real-Neo4j test using these fixtures is marked `@pytest.mark.real_infra`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from neo4j import AsyncDriver, AsyncGraphDatabase
from testcontainers.neo4j import Neo4jContainer

__all__ = ["neo4j_container", "neo4j_driver"]

_NEO4J_IMAGE = "neo4j:5-community"
"""Matches infra/docker/docker-compose.local.yml's `neo4j` service exactly."""

_NEO4J_PASSWORD = "nova_testkit_password"
_NEO4J_USER = "neo4j"


@pytest.fixture(scope="session")
def neo4j_container() -> Iterator[Neo4jContainer]:
    """One throwaway, session-scoped Neo4j container, APOC enabled to match
    production. `Neo4jContainer.start()` already blocks on a real
    `driver.verify_connectivity()` round trip (`_connect`'s own readiness
    check, itself gated on the "Remote interface available at" log line) --
    no additional readiness polling needed here."""
    container = Neo4jContainer(_NEO4J_IMAGE, password=_NEO4J_PASSWORD, username=_NEO4J_USER)
    container.with_env("NEO4J_PLUGINS", '["apoc"]')
    with container as started:
        yield started


@pytest.fixture
async def neo4j_driver(neo4j_container: Neo4jContainer) -> AsyncIterator[AsyncDriver]:
    """A real, async `AsyncDriver` connected to `neo4j_container`. Runs
    `MATCH (n) DETACH DELETE n` both before yielding (in case a prior test in
    the same session left state) and in teardown -- Neo4j has no
    transaction/rollback primitive spanning a whole test the way
    `postgres_session` does, so explicit deletion is this store's own
    isolation mechanism (implementation plan §2.4)."""
    driver = AsyncGraphDatabase.driver(
        neo4j_container.get_connection_url(), auth=(_NEO4J_USER, _NEO4J_PASSWORD)
    )

    async def _clear() -> None:
        async with driver.session() as session:
            await session.run("MATCH (n) DETACH DELETE n")

    await _clear()
    try:
        yield driver
    finally:
        await _clear()
        await driver.close()
