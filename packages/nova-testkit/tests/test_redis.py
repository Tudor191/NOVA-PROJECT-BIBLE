"""Verifies `nova_testkit.redis`'s fixtures against a real Redis container --
real writes/reads, real TTL expiry, and isolation between tests via FLUSHDB
(implementation plan §13's verification bar).

`@pytest.mark.real_infra`: excluded from the default `pytest`/`turbo run test`
invocation (ADR-033) -- requires Docker. **Not executed in the environment
this file was written in** (no reachable Docker daemon there); see
`redis.py`'s own module docstring.
"""

import asyncio

import pytest
from redis.asyncio import Redis

pytestmark = pytest.mark.real_infra


async def test_real_set_and_get_round_trip(redis_client: Redis) -> None:
    await redis_client.set("testkit:widget", "gizmo")

    value = await redis_client.get("testkit:widget")

    assert value == b"gizmo"


async def test_real_ttl_expiry(redis_client: Redis) -> None:
    await redis_client.set("testkit:ephemeral", "value", px=50)

    assert await redis_client.get("testkit:ephemeral") == b"value"
    await asyncio.sleep(0.15)
    assert await redis_client.get("testkit:ephemeral") is None


async def test_flushdb_isolates_each_test(redis_client: Redis) -> None:
    """Runs after the two tests above in file order; if FLUSHDB isolation
    were broken, `testkit:widget` would still be present here."""
    assert await redis_client.get("testkit:widget") is None
    assert await redis_client.dbsize() == 0
