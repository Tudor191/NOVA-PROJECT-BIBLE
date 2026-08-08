"""Real-Redis test fixtures via `testcontainers` (ADR-033's real-infrastructure
tier; docs/design/nova-testkit/technical-implementation-plan.md §2.4, §3.3).

`redis_container` starts one throwaway `redis:7-alpine` container -- the exact
image `infra/docker/docker-compose.local.yml`'s `redis` service already pins.
`redis_client` yields a real, async `redis.asyncio.Redis`, constructed with
`Redis.from_url(...)` -- this project's own convention (e.g.
`world-model-engine/workers/__init__.py`'s `Redis.from_url(_SETTINGS.
redis_url)`), not the container class's own `get_client()` (which returns a
*sync* `redis.Redis`, wrong for this fully-async codebase).

**Unverified in this environment**: written against `testcontainers==4.13.3`'s
real, installed API (confirmed by direct introspection) and `redis==5.3.1`
(this workspace's own resolved version), but never executed against a real
container here -- no Docker daemon reachable (confirmed: even constructing a
`PostgresContainer` in this session raised `docker.errors.DockerException`
before `.start()` was ever called, since testcontainers connects to the Docker
daemon in `__init__`, not just `start()`). Every real-Redis test using these
fixtures is marked `@pytest.mark.real_infra`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from redis.asyncio import Redis
from testcontainers.redis import RedisContainer

__all__ = ["redis_client", "redis_container"]

_REDIS_IMAGE = "redis:7-alpine"
"""Matches infra/docker/docker-compose.local.yml's `redis` service exactly."""

_REDIS_CONTAINER_PORT = 6379
"""The container-internal port Redis always listens on -- looked up via
`get_exposed_port()` to find the dynamically-assigned *host* port
testcontainers picked, never assumed to be 6379 on the host side too
(implementation plan §2.4: no hardcoded host ports)."""


@pytest.fixture(scope="session")
def redis_container() -> Iterator[RedisContainer]:
    """One throwaway, session-scoped Redis container. `RedisContainer.start()`
    already blocks on a real `PING`/`PONG` round trip (`_connect`'s own
    `@wait_container_is_ready` readiness check) before returning -- no
    additional readiness polling needed here."""
    with RedisContainer(_REDIS_IMAGE, port=_REDIS_CONTAINER_PORT) as container:
        yield container


@pytest.fixture
async def redis_client(redis_container: RedisContainer) -> AsyncIterator[Redis]:
    """A real, async `Redis` client connected to `redis_container`. `FLUSHDB`
    both before yielding (in case a prior test in the same session left state)
    and in teardown (so the next test starts clean regardless of execution
    order) -- Redis has no transaction/rollback primitive to lean on the way
    `postgres_session` does, so explicit flush is this store's own isolation
    mechanism (implementation plan §2.4)."""
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(_REDIS_CONTAINER_PORT)
    client = Redis.from_url(f"redis://{host}:{port}/0")
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()
