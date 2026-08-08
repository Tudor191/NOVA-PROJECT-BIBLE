"""Real-NATS-JetStream test fixtures via `testcontainers` (ADR-033's
real-infrastructure tier; docs/design/nova-testkit/
technical-implementation-plan.md §2.4, §3.4).

`nats_container` starts one throwaway `nats:2-alpine` container -- the exact
image `infra/docker/docker-compose.local.yml`'s `nats` service already pins --
with JetStream enabled (`-js`), the one command flag that actually matters for
real-infrastructure testing. `-sd /data` (persistent storage dir) and
`-m 8222` (HTTP monitoring endpoint) from compose's own
`command: ["-js", "-sd", "/data", "-m", "8222"]` are both deliberately
omitted: this container is throwaway per test session (no persistence to
survive a restart), and readiness here uses `NatsContainer`'s own log-based
check (waiting for "Server is ready" in container logs), not an HTTP
`/healthz` poll, so the monitoring port has no consumer.

`nats_event_bus` connects this project's own, already-production,
JetStream-backed `EventBus` implementation
(`nova_eventbus_sdk.backends.nats.NatsEventBus`) to the container -- no new
NATS client written for tests, the identical class every engine's `main.py`
uses against `docker-compose.local.yml`, just pointed at a throwaway
container instead.

**Unverified in this environment**: written against `testcontainers==4.13.3`'s
real, installed API (confirmed by direct introspection) -- that version's
`NatsContainer` has no `jetstream=` constructor kwarg (added in a later
release than this workspace's `>=4.9` floor resolves), so `-js` is set
directly via `with_command`, the same mechanism the newer kwarg uses
internally. Never executed against a real container here -- no Docker daemon
reachable (confirmed). Every real-NATS test using these fixtures is marked
`@pytest.mark.real_infra`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from nova_eventbus_sdk.backends.nats import NatsEventBus
from testcontainers.nats import NatsContainer

__all__ = ["nats_container", "nats_event_bus"]

_NATS_IMAGE = "nats:2-alpine"
"""Matches infra/docker/docker-compose.local.yml's `nats` service exactly."""


@pytest.fixture(scope="session")
def nats_container() -> Iterator[NatsContainer]:
    """One throwaway, session-scoped NATS container with JetStream enabled.
    `NatsContainer.start()` already blocks on a real "Server is ready" log
    line before returning -- no additional readiness polling needed here."""
    container = NatsContainer(_NATS_IMAGE)
    container.with_command("-js")
    with container as started:
        yield started


@pytest.fixture
async def nats_event_bus(nats_container: NatsContainer) -> AsyncIterator[NatsEventBus]:
    """A real `NatsEventBus` connected to `nats_container`. Isolation: a
    fresh, uniquely-prefixed subject namespace per test is the caller's own
    responsibility -- JetStream streams are explicitly provisioned, so there
    is no single "flush everything" primitive to call here the way
    `redis_client`/`neo4j_driver` have (implementation plan §2.4)."""
    bus = NatsEventBus(servers=nats_container.nats_uri())
    await bus.connect()
    yield bus
    await bus.close()
