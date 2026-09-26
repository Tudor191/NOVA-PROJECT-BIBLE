"""`cognitive_state.sensor_state` against **real PostgreSQL and real NATS** --
Phase 4F.7, ratified A-4F7-1 and A-4F7-2 (TDD 4F.7 §8, §28).

What only real infrastructure can prove, and where each claim is proven:

* **P-26 -- the schema is current-state storage and nothing else**: exactly two
  tables in `cognitive_state`, and `sensor_state` has exactly the five ratified
  columns. Read from `information_schema`, not from the ORM.
* **P-25 -- one record per sensor, one conditional statement**: the first report
  inserts; a redelivery of the current row's `event_id` and an older report both
  change nothing (the repository says so, and independent SQL agrees); a newer
  report replaces the row; two sensors are two rows.
* **P-15 -- the real Event Bus path**: a report published over a real NATS
  connection by a bus **bound as `perception-engine` binds its own** reaches the
  **production** `create_app` lifespan subscription, lands in real Postgres (read
  back by independent SQL) and is served by `GET /v1/cognitive-state/sensors` over
  a real socket. Unknown statuses, redeliveries and stale reports travel the
  same real path and change nothing.
* **P-24 -- restart persistence**: the engine is shut down and a new one started
  against the same database; the record is served unchanged, and no startup path
  resets it.
* **K-1 -- the documented limitation**: a report published while no
  `cognitive-state-engine` is subscribed is **not** received, and nothing replays
  it. Asserted with an ordered marker, never with a sleep.

**The producer is not `perception-engine`'s code.** Control 7 forbids one engine
depending on another, tests included -- the 4F.6 precedent. This bus carries
`perception-engine`'s engine name and publishes the one subject its allow-list
holds (`perception-engine/events/published.py`); the two halves meet at the
registered contract, `PerceptionSensorHealthChangedPayload`, whose producer half
is proven in `perception-engine`'s own real-infra tier (P-16).

`@pytest.mark.real_infra`: requires Docker (or equivalent real services).
"""

from __future__ import annotations

import asyncio
import os
import socket
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
import uvicorn
from nova_cognitive_state_engine.config import Settings
from nova_cognitive_state_engine.domain.sensor_state import SensorStateRecord
from nova_cognitive_state_engine.events.handlers import make_sensor_health_handler
from nova_cognitive_state_engine.main import create_app
from nova_cognitive_state_engine.repository.postgres_cognitive_state_repository import (
    PostgresCognitiveStateRepository,
)
from nova_contracts import EventEnvelope
from nova_contracts.events.perception import PerceptionSensorHealthChangedPayload
from nova_eventbus_sdk import BoundEventBus
from nova_eventbus_sdk.backends.nats import NatsEventBus
from nova_testkit.postgres import run_alembic_upgrade
from nova_testkit.waiting import wait_until
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
SUBJECT = "perception.sensor.health_changed"
T0 = datetime(2026, 9, 26, 8, 0, tzinfo=UTC)


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    os.environ["COGNITIVE_STATE_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
async def database(postgres_container: PostgresContainer) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(postgres_container.get_connection_url())
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM cognitive_state.sensor_state"))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM cognitive_state.sensor_state"))
    await engine.dispose()


@pytest.fixture
def repository(database: AsyncEngine) -> PostgresCognitiveStateRepository:
    return PostgresCognitiveStateRepository(async_sessionmaker(database, expire_on_commit=False))


async def _rows(database: AsyncEngine) -> list[dict]:  # type: ignore[type-arg]
    """Independent SQL on its own connection -- never the repository that wrote."""
    async with database.connect() as connection:
        result = await connection.execute(
            text(
                "SELECT sensor_id, sensor_type, state, reported_at, last_event_id "
                "FROM cognitive_state.sensor_state ORDER BY sensor_id"
            )
        )
        return [dict(row._mapping) for row in result]


def _record(
    state: str = "running",
    *,
    sensor_id: str = "companion-filesystem",
    at: datetime = T0,
    event_id: UUID | None = None,
) -> SensorStateRecord:
    return SensorStateRecord(
        sensor_id=sensor_id,
        sensor_type="filesystem",
        state=state,  # type: ignore[arg-type]
        reported_at=at,
        last_event_id=event_id or uuid4(),
    )


# --- P-26: the schema -----------------------------------------------------------------


async def test_p26_the_schema_holds_exactly_two_tables(database: AsyncEngine) -> None:
    async with database.connect() as connection:
        tables = (
            (
                await connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'cognitive_state' ORDER BY table_name"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert list(tables) == ["active_thought", "sensor_state"]


async def test_p26_sensor_state_has_exactly_the_five_ratified_columns(
    database: AsyncEngine,
) -> None:
    async with database.connect() as connection:
        columns = (
            await connection.execute(
                text(
                    "SELECT column_name, data_type, is_nullable "
                    "FROM information_schema.columns "
                    "WHERE table_schema = 'cognitive_state' AND table_name = 'sensor_state' "
                    "ORDER BY ordinal_position"
                )
            )
        ).all()
        primary_key = (
            (
                await connection.execute(
                    text(
                        "SELECT kcu.column_name FROM information_schema.table_constraints tc "
                        "JOIN information_schema.key_column_usage kcu "
                        "  ON tc.constraint_name = kcu.constraint_name "
                        " AND tc.table_schema = kcu.table_schema "
                        "WHERE tc.table_schema = 'cognitive_state' "
                        "  AND tc.table_name = 'sensor_state' "
                        "  AND tc.constraint_type = 'PRIMARY KEY'"
                    )
                )
            )
            .scalars()
            .all()
        )

    assert [tuple(c) for c in columns] == [
        ("sensor_id", "text", "NO"),
        ("sensor_type", "text", "NO"),
        ("state", "text", "NO"),
        ("reported_at", "timestamp with time zone", "NO"),
        ("last_event_id", "uuid", "NO"),
    ]
    assert list(primary_key) == ["sensor_id"]


# --- P-25: one record per sensor, one conditional statement -----------------------------


async def test_p25_the_first_report_inserts(
    repository: PostgresCognitiveStateRepository, database: AsyncEngine
) -> None:
    record = _record("running")
    assert await repository.apply_sensor_report(record) is True
    rows = await _rows(database)
    assert len(rows) == 1
    assert rows[0]["state"] == "running"
    assert rows[0]["last_event_id"] == record.last_event_id


async def test_p25_a_redelivery_of_the_current_event_changes_nothing(
    repository: PostgresCognitiveStateRepository, database: AsyncEngine
) -> None:
    record = _record("running")
    await repository.apply_sensor_report(record)
    before = await _rows(database)

    assert await repository.apply_sensor_report(record) is False
    assert await _rows(database) == before


async def test_p25_an_older_report_never_overwrites_a_newer_one(
    repository: PostgresCognitiveStateRepository, database: AsyncEngine
) -> None:
    newer = _record("stopped", at=T0 + timedelta(seconds=10))
    await repository.apply_sensor_report(newer)

    assert await repository.apply_sensor_report(_record("running", at=T0)) is False
    rows = await _rows(database)
    assert rows[0]["state"] == "stopped"
    assert rows[0]["last_event_id"] == newer.last_event_id


async def test_p25_a_newer_report_replaces_the_record_and_leaves_one_row(
    repository: PostgresCognitiveStateRepository, database: AsyncEngine
) -> None:
    for offset, state in enumerate(["initialized", "running", "paused", "running", "stopped"]):
        assert await repository.apply_sensor_report(
            _record(state, at=T0 + timedelta(seconds=offset))
        )

    rows = await _rows(database)
    assert len(rows) == 1
    assert rows[0]["state"] == "stopped"
    assert rows[0]["reported_at"] == T0 + timedelta(seconds=4)


async def test_p25_an_equal_time_report_with_a_new_event_applies(
    repository: PostgresCognitiveStateRepository, database: AsyncEngine
) -> None:
    await repository.apply_sensor_report(_record("running", at=T0))
    replacement = _record("failed", at=T0)
    assert await repository.apply_sensor_report(replacement) is True
    assert (await _rows(database))[0]["last_event_id"] == replacement.last_event_id


async def test_p25_two_sensors_are_two_rows(
    repository: PostgresCognitiveStateRepository, database: AsyncEngine
) -> None:
    await repository.apply_sensor_report(_record("running", sensor_id="companion-filesystem"))
    await repository.apply_sensor_report(_record("stopped", sensor_id="camera-sensor-1"))
    rows = await _rows(database)
    assert [(r["sensor_id"], r["state"]) for r in rows] == [
        ("camera-sensor-1", "stopped"),
        ("companion-filesystem", "running"),
    ]
    listed = await repository.list_sensor_states()
    assert [(r.sensor_id, r.state) for r in listed] == [
        ("camera-sensor-1", "stopped"),
        ("companion-filesystem", "running"),
    ]


async def test_an_unknown_status_leaves_the_stored_record_unchanged(
    repository: PostgresCognitiveStateRepository, database: AsyncEngine
) -> None:
    """The handler against the real repository: a rejected report is not
    stored, so the latest *known* state survives it (A-4F7-1, A-4F7-2)."""
    handler = make_sensor_health_handler(repository)
    await handler(_envelope("running", at=T0))
    before = await _rows(database)

    await handler(_envelope("unhealthy", at=T0 + timedelta(seconds=30)))
    await handler(_envelope("Running", at=T0 + timedelta(seconds=31)))

    assert await _rows(database) == before


# --- the real Event Bus path ------------------------------------------------------------


def _envelope(
    status: str,
    *,
    sensor_id: str = "companion-filesystem",
    at: datetime | None = None,
    event_id: UUID | None = None,
) -> EventEnvelope:
    payload = PerceptionSensorHealthChangedPayload(
        sensor_id=sensor_id, sensor_type="filesystem", status=status
    )
    values: dict[str, object] = {
        "subject": SUBJECT,
        "source_engine": "perception-engine",
        "correlation_id": uuid4(),
        "payload": payload.model_dump(mode="json"),
    }
    if at is not None:
        values["occurred_at"] = at
    if event_id is not None:
        values["event_id"] = event_id
    return EventEnvelope(**values)  # type: ignore[arg-type]


@pytest.fixture
async def producer(nats_container) -> AsyncIterator[BoundEventBus]:  # type: ignore[no-untyped-def]
    """A real NATS connection, bound with `perception-engine`'s engine name and the
    one subject this test publishes -- a subject `perception-engine`'s own
    allow-list holds. Not imported from that engine (control 7)."""
    backend = NatsEventBus(servers=nats_container.nats_uri())
    bus = BoundEventBus(
        backend,
        engine_name="perception-engine",
        publishable_subjects=frozenset({SUBJECT}),
        subscribable_subjects=frozenset(),
    )
    await bus.connect()
    yield bus
    await bus.close()


@asynccontextmanager
async def _running_engine(
    postgres_container: PostgresContainer,
    nats_container,
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[no-untyped-def]
) -> AsyncIterator[httpx.AsyncClient]:
    """The **production** app -- its own `nova-service-kit` engine, its own
    repository, its own lifespan subscription -- served by a real uvicorn in this
    test's own event loop (the `action-engine` 4F.4 precedent: the asyncpg
    connections must not cross loops)."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "nats")
    monkeypatch.setenv("NATS_URL", nats_container.nats_uri())
    app = create_app(Settings(postgres_dsn=postgres_container.get_connection_url()))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    task = asyncio.create_task(server.serve())
    deadline = time.monotonic() + 30.0
    while not server.started:
        if task.done():
            await task
        if time.monotonic() > deadline:
            raise RuntimeError("uvicorn did not start within the deadline")
        await asyncio.sleep(0.02)
    bound: socket.socket = server.servers[0].sockets[0]
    try:
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{bound.getsockname()[1]}", timeout=10.0
        ) as client:
            yield client
    finally:
        server.should_exit = True
        await task


async def _state_of(database: AsyncEngine, sensor_id: str) -> str | None:
    for row in await _rows(database):
        if row["sensor_id"] == sensor_id:
            return str(row["state"])
    return None


async def test_p15_a_real_report_reaches_the_table_and_the_api(
    producer: BoundEventBus,
    database: AsyncEngine,
    postgres_container: PostgresContainer,
    nats_container,  # type: ignore[no-untyped-def]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with _running_engine(postgres_container, nats_container, monkeypatch) as client:
        report = _envelope("running", at=T0)
        await producer.publish(report)
        await wait_until(lambda: _state_of(database, "companion-filesystem"), timeout_s=10.0)

        rows = await _rows(database)
        assert rows == [
            {
                "sensor_id": "companion-filesystem",
                "sensor_type": "filesystem",
                "state": "running",
                "reported_at": T0,
                "last_event_id": report.event_id,
            }
        ]
        response = await client.get("/v1/cognitive-state/sensors")
        assert response.status_code == 200
        assert response.json() == {
            "sensors": [
                {
                    "sensor_id": "companion-filesystem",
                    "sensor_type": "filesystem",
                    "state": "running",
                    "reported_at": "2026-09-26T08:00:00Z",
                }
            ]
        }


async def test_p15_redelivery_stale_and_unknown_reports_change_nothing_over_the_real_bus(
    producer: BoundEventBus,
    database: AsyncEngine,
    postgres_container: PostgresContainer,
    nats_container,  # type: ignore[no-untyped-def]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each disturbing report is followed by a **marker** on another sensor. NATS
    delivers one connection's messages in order and the subscription handles
    them in order, so once the marker is stored, the report before it has been
    handled -- no sleep stands in for that."""
    async with _running_engine(postgres_container, nats_container, monkeypatch):
        older = _envelope("running", at=T0)
        newer = _envelope("stopped", at=T0 + timedelta(seconds=10))
        await producer.publish(older)
        await producer.publish(newer)
        await wait_until(lambda: _is(database, "companion-filesystem", "stopped"), timeout_s=10.0)
        settled = await _rows(database)

        for index, disturbance in enumerate(
            [
                older,  # a redelivery that is also stale
                newer,  # a redelivery of the current event
                _envelope("healthy", at=T0 + timedelta(seconds=20)),  # unknown: never stored
                _envelope("RUNNING", at=T0 + timedelta(seconds=21)),  # case-sensitive
            ]
        ):
            marker = f"marker-{index}"
            await producer.publish(disturbance)
            await producer.publish(_envelope("initialized", sensor_id=marker, at=T0))
            await wait_until(lambda m=marker: _is(database, m, "initialized"), timeout_s=10.0)

            current = [r for r in await _rows(database) if r["sensor_id"] == "companion-filesystem"]
            assert current == [r for r in settled if r["sensor_id"] == "companion-filesystem"]


async def _is(database: AsyncEngine, sensor_id: str, state: str) -> bool:
    return await _state_of(database, sensor_id) == state


async def test_p24_the_record_survives_a_restart_and_nothing_resets_it(
    producer: BoundEventBus,
    database: AsyncEngine,
    postgres_container: PostgresContainer,
    nats_container,  # type: ignore[no-untyped-def]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with _running_engine(postgres_container, nats_container, monkeypatch):
        await producer.publish(_envelope("failed", at=T0))
        await wait_until(lambda: _is(database, "companion-filesystem", "failed"), timeout_s=10.0)
    stored = await _rows(database)

    # A new engine, a new lifespan, the same database -- and no new report.
    async with _running_engine(postgres_container, nats_container, monkeypatch) as client:
        assert await _rows(database) == stored
        served = (await client.get("/v1/cognitive-state/sensors")).json()

    assert served == {
        "sensors": [
            {
                "sensor_id": "companion-filesystem",
                "sensor_type": "filesystem",
                "state": "failed",
                "reported_at": "2026-09-26T08:00:00Z",
            }
        ]
    }


async def test_k1_a_report_published_while_offline_is_not_received(
    producer: BoundEventBus,
    database: AsyncEngine,
    postgres_container: PostgresContainer,
    nats_container,  # type: ignore[no-untyped-def]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TDD 4F.7 §15 **K-1**, asserted rather than assumed. Core NATS keeps nothing
    for a subscriber that is not there, and this engine invents no replay,
    retry, queue or recovery. The ordered marker proves the engine *was*
    listening afterwards, so the absence is the limitation and not a slow start."""
    await producer.publish(_envelope("running", sensor_id="published-while-offline", at=T0))

    async with _running_engine(postgres_container, nats_container, monkeypatch) as client:
        await producer.publish(_envelope("running", sensor_id="published-while-online", at=T0))
        await wait_until(lambda: _is(database, "published-while-online", "running"), timeout_s=10.0)

        assert await _state_of(database, "published-while-offline") is None
        served = (await client.get("/v1/cognitive-state/sensors")).json()["sensors"]
        assert [s["sensor_id"] for s in served] == ["published-while-online"]
