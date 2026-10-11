"""**D-4F-1's exception at runtime: one-second dispatch, no overlap, no duplicate.**

TDD 4F.8 §30.3 items 2 and 3. D-4F-1 was reopened on 2026-10-11 for this
engine's outbox dispatch interval only. The change is a one-second cron with
`max_jobs = 1`, and this file proves its safety claim against real
infrastructure, under the one deployment it is made for: a single worker.

**What is real.** This engine's own `WorkerSettings` runs in a real arq worker,
built by arq's own `create_worker`. That includes its one-second cron, its
`max_jobs`, its queue, and its real `startup` and `shutdown`. It runs against
real Redis, and dispatches rows from a real `perception.outbox_event` table in
real PostgreSQL to a real NATS subscriber. Rows are written by the real
repository's `enqueue_outbox`. Its environment is the one compose sets.

**How a run is made to outlast one second.** The dispatcher reads at most 100
rows a run. Against local PostgreSQL 16 and nats-server, a full 100-row run took
0.25–0.29 s. So seeding more rows cannot make one run outlast the interval; it
only makes more runs.

The stall is instead a real database condition. A concurrent transaction holds
`SHARE` on the outbox table, the lock a non-concurrent `CREATE INDEX` takes. It
blocks writes and not reads. So the first run selects its batch, publishes its
first row, and then waits on that row's `mark_dispatched` until the lock is
released. Nothing in the dispatcher is mocked, patched or delayed.

**What is observed, without changing behaviour:**
- arq's `on_job_start` and `after_job_end` hooks, which `WorkerSettings` does
  not set, time each run;
- a real NATS subscription counts each `event_id`;
- an independent SQL query counts rows left undispatched.

**The control.** The last test repeats the stall with arq's default
`max_jobs` (10), which is what this engine ran with until 2026-10-11, and asserts
that the hazard occurs. Without that control the two tests above could pass
against a dispatcher that is merely fast.

`@pytest.mark.real_infra`: needs Docker for PostgreSQL, Redis and NATS.
"""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
import time
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from types import ModuleType
from typing import Any
from uuid import UUID, uuid4

import pytest
from arq.worker import create_worker
from nova_contracts import EventEnvelope
from nova_contracts.events.perception import PerceptionWorkspaceObservedPayload
from nova_eventbus_sdk.backends.nats import NatsEventBus
from nova_perception_engine.domain.ports import OutboxEvent
from nova_perception_engine.repository.postgres_perception_repository import (
    PostgresPerceptionRepository,
)
from nova_service_kit import create_engine, create_session_factory
from nova_testkit.postgres import run_alembic_upgrade
from nova_testkit.waiting import wait_until
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncTransaction
from testcontainers.nats import NatsContainer
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
_WORKERS = "nova_perception_engine.workers"
_REDIS_CONTAINER_PORT = 6379

SUBJECT = "perception.workspace.observed"
BATCH = 100
"""`dispatch_ready_events`' per-run cap, which `arq_run_outbox_dispatch` keeps."""
STALL_SECONDS = 3.0
"""How long the table lock holds after the first run starts. Long enough that
at least two later ticks come due while that run is still alive."""
SETTLE_SECONDS = 3.0
"""Kept running after the last delivery, so at least two more ticks run. Any
row left published but unmarked would be published again by them."""
DEADLINE_SECONDS = 30.0
ARQ_DEFAULT_MAX_JOBS = 10
"""`arq.worker.Worker`'s own default, and this engine's effective setting
before 2026-10-11."""


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    os.environ["PERCEPTION_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
async def database(postgres_container: PostgresContainer) -> AsyncIterator[AsyncEngine]:
    """A real, committing engine. Each test starts from an empty outbox."""
    engine = create_engine(postgres_container.get_connection_url())
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM perception.outbox_event"))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM perception.outbox_event"))
    await engine.dispose()


@pytest.fixture
def repository(database: AsyncEngine) -> PostgresPerceptionRepository:
    return PostgresPerceptionRepository(create_session_factory(database))


@pytest.fixture
def workers(
    postgres_container: PostgresContainer,
    redis_container: RedisContainer,
    nats_container: NatsContainer,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> ModuleType:
    """This engine's real `workers` module, imported with the variables
    compose gives `perception-engine-worker`, pointed at the containers.

    The module builds `Settings()` at import, so it is reloaded after the
    environment is set; an earlier import in the same session would otherwise
    hold the defaults. `redis_client` is requested for its `FLUSHDB`, so no
    arq key survives from another test."""
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(_REDIS_CONTAINER_PORT)
    monkeypatch.setenv("PERCEPTION_ENGINE_POSTGRES_DSN", postgres_container.get_connection_url())
    monkeypatch.setenv("PERCEPTION_ENGINE_REDIS_URL", f"redis://{host}:{port}/0")
    monkeypatch.setenv("EVENT_BUS_BACKEND", "nats")
    monkeypatch.setenv("NATS_URL", nats_container.nats_uri())
    module = (
        importlib.reload(sys.modules[_WORKERS])
        if _WORKERS in sys.modules
        else importlib.import_module(_WORKERS)
    )
    settings = module.WorkerSettings
    assert settings.redis_settings.port == int(port)
    assert not {"on_job_start", "on_job_end", "after_job_end"} & set(vars(settings)), (
        "WorkerSettings now sets a job hook; this file's observation hooks would replace it"
    )
    return module


@pytest.fixture
async def deliveries(nats_event_bus: NatsEventBus) -> AsyncIterator[Counter[UUID]]:
    """Every `event_id` a real subscriber receives on the dispatched subject,
    counted. A sentinel round trip proves the subscription is live before any
    worker publishes."""
    received: Counter[UUID] = Counter()

    async def on_event(envelope: EventEnvelope) -> None:
        received[envelope.event_id] += 1

    subscription = await nats_event_bus.subscribe(SUBJECT, on_event)
    sentinel = EventEnvelope(subject=SUBJECT, source_engine="test", correlation_id=uuid4())
    await nats_event_bus.publish(sentinel)
    await wait_until(lambda: received[sentinel.event_id] == 1, timeout_s=5)
    del received[sentinel.event_id]
    yield received
    await subscription.unsubscribe()


@dataclass
class Run:
    job_id: str
    started: float
    ended: float | None = None

    @property
    def tick(self) -> float:
        """The instant arq scheduled this run for, in seconds: `run_cron`
        names each tick's job `<name>:<unix ms>`."""
        return int(self.job_id.rsplit(":", 1)[1]) / 1000


class RunLog:
    """Each dispatch run's start and end, from arq's own job hooks."""

    def __init__(self) -> None:
        self.runs: dict[str, Run] = {}

    async def on_job_start(self, ctx: dict[str, Any]) -> None:
        self.runs[ctx["job_id"]] = Run(ctx["job_id"], started=time.time())

    async def after_job_end(self, ctx: dict[str, Any]) -> None:
        self.runs[ctx["job_id"]].ended = time.time()

    def ordered(self) -> list[Run]:
        return sorted(self.runs.values(), key=lambda run: run.started)

    def idle(self) -> bool:
        return bool(self.runs) and all(run.ended is not None for run in self.runs.values())

    def overlapping(self) -> list[tuple[str, str]]:
        return [
            (a.job_id, b.job_id)
            for a, b in combinations(self.ordered(), 2)
            if a.ended is None or b.started < a.ended
        ]


@asynccontextmanager
async def running(workers: ModuleType, log: RunLog, **overrides: Any) -> AsyncIterator[None]:
    """A real arq worker built from the real `WorkerSettings`. `overrides`
    carry only the observation hooks, except in the control."""
    worker = create_worker(
        workers.WorkerSettings,
        handle_signals=False,
        on_job_start=log.on_job_start,
        after_job_end=log.after_job_end,
        **overrides,
    )
    task = asyncio.create_task(worker.async_run())
    try:
        yield
    finally:
        await worker.close()
        await asyncio.gather(task, return_exceptions=True)


class TableWriteLock:
    """`SHARE` on the outbox table, held by its own real transaction: the lock
    a non-concurrent `CREATE INDEX` takes. Reads proceed; every `UPDATE`, so
    every `mark_dispatched`, waits."""

    def __init__(self, database: AsyncEngine) -> None:
        self._database = database
        self._connection: AsyncConnection | None = None
        self._transaction: AsyncTransaction | None = None

    async def acquire(self) -> None:
        self._connection = await self._database.connect()
        self._transaction = await self._connection.begin()
        await self._connection.execute(text("LOCK TABLE perception.outbox_event IN SHARE MODE"))

    async def release(self) -> None:
        if self._transaction is not None:
            await self._transaction.rollback()
            self._transaction = None
        if self._connection is not None:
            await self._connection.close()
            self._connection = None


async def seed(repository: PostgresPerceptionRepository, count: int) -> set[UUID]:
    """Real outbox rows through the real repository. Each row id is the
    `event_id` the dispatcher publishes it under."""
    ids = set()
    for index in range(count):
        payload = PerceptionWorkspaceObservedPayload(
            object_id=f"{index:064x}",
            label=f"project-{index}",
            user_id=uuid4(),
            object_type="project",
            sensor_id="companion-filesystem",
            observed_at=datetime.now(UTC),
        )
        ids.add(
            await repository.enqueue_outbox(
                OutboxEvent(
                    subject=SUBJECT,
                    payload=payload.model_dump(mode="json"),
                    correlation_id=uuid4(),
                )
            )
        )
    return ids


async def undispatched(database: AsyncEngine) -> int:
    """Independent SQL on its own connection, never the repository."""
    async with database.connect() as connection:
        result = await connection.execute(
            text("SELECT count(*) FROM perception.outbox_event WHERE dispatched_at IS NULL")
        )
        return int(result.scalar_one())


async def drain(log: RunLog, deliveries: Counter[UUID], seeded: set[UUID]) -> None:
    """Every seeded row delivered, two more ticks given the chance to publish
    anything twice, then no run in flight."""
    await wait_until(lambda: seeded <= set(deliveries), timeout_s=DEADLINE_SECONDS)
    await asyncio.sleep(SETTLE_SECONDS)
    await wait_until(log.idle, timeout_s=DEADLINE_SECONDS)


async def stall_the_first_run(
    log: RunLog, deliveries: Counter[UUID], lock: TableWriteLock
) -> None:
    """With the lock already held: wait for the first run to publish its first
    row (its mark now waiting on the lock), hold until `STALL_SECONDS` after
    that run started, then release."""
    await wait_until(lambda: bool(log.runs), timeout_s=5)
    await wait_until(lambda: sum(deliveries.values()) >= 1, timeout_s=5)
    first = log.ordered()[0]
    await asyncio.sleep(max(0.0, first.started + STALL_SECONDS - time.time()))
    await lock.release()


async def test_the_real_worker_drains_the_outbox_once_per_row_on_a_one_second_cadence(
    workers: ModuleType,
    repository: PostgresPerceptionRepository,
    database: AsyncEngine,
    deliveries: Counter[UUID],
) -> None:
    seeded = await seed(repository, 3 * BATCH + 50)
    log = RunLog()

    async with running(workers, log):
        await drain(log, deliveries, seeded)

    runs = log.ordered()
    ticks = [run.tick for run in runs]
    assert len(runs) >= 6, f"expected at least six one-second runs, saw {len(runs)}"
    assert ticks == sorted(ticks), "arq started the ticks out of order"
    gaps = {round(later - earlier, 3) for earlier, later in zip(ticks, ticks[1:], strict=False)}
    assert gaps == {1.0}, f"consecutive dispatch ticks must be one second apart, saw {gaps}"
    assert log.overlapping() == []
    assert set(deliveries) == seeded
    assert {event_id: n for event_id, n in deliveries.items() if n != 1} == {}
    assert await undispatched(database) == 0


async def test_a_run_that_outlasts_the_interval_delays_later_ticks_and_publishes_nothing_twice(
    workers: ModuleType,
    repository: PostgresPerceptionRepository,
    database: AsyncEngine,
    deliveries: Counter[UUID],
) -> None:
    seeded = await seed(repository, BATCH + 50)
    log = RunLog()
    lock = TableWriteLock(database)

    await lock.acquire()
    try:
        async with running(workers, log):
            await stall_the_first_run(log, deliveries, lock)
            await drain(log, deliveries, seeded)
    finally:
        await lock.release()

    stalled, *later = log.ordered()
    assert stalled.ended is not None
    # The condition under test happened: one run outlived the interval...
    assert stalled.ended - stalled.started > 1.0, (
        f"the stalled run lasted {stalled.ended - stalled.started:.2f}s; the stall did not take"
    )
    # ...ticks came due while it was alive, and arq started none of them until it ended.
    due_meanwhile = [run for run in later if stalled.started < run.tick < stalled.ended]
    assert len(due_meanwhile) >= 2, f"only {len(due_meanwhile)} ticks came due during the stall"
    assert all(run.started >= stalled.ended for run in due_meanwhile)
    assert log.overlapping() == []
    # Every row published exactly once, and marked.
    assert set(deliveries) == seeded
    assert {event_id: n for event_id, n in deliveries.items() if n != 1} == {}
    assert await undispatched(database) == 0


async def test_control_without_the_concurrency_limit_the_same_stall_overlaps_and_duplicates(
    workers: ModuleType,
    repository: PostgresPerceptionRepository,
    database: AsyncEngine,
    deliveries: Counter[UUID],
) -> None:
    """The negative control (TDD 4F.8 §30.3 item 3): the identical scenario,
    with `max_jobs` back at arq's default. If this stops failing the safety
    property, the test above has stopped being evidence for it."""
    seeded = await seed(repository, BATCH + 50)
    log = RunLog()
    lock = TableWriteLock(database)

    await lock.acquire()
    try:
        async with running(workers, log, max_jobs=ARQ_DEFAULT_MAX_JOBS):
            await stall_the_first_run(log, deliveries, lock)
            await drain(log, deliveries, seeded)
    finally:
        await lock.release()

    duplicated = {event_id: n for event_id, n in deliveries.items() if n > 1}
    assert log.overlapping(), "without max_jobs = 1, later ticks should start during the stall"
    assert duplicated, "without max_jobs = 1, a row should be published more than once"
    assert set(deliveries) == seeded
    assert await undispatched(database) == 0
