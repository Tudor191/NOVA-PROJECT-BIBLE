"""**P-16 -- the real Event Bus path, producer half** (Phase 4F.7, TDD 4F.7 §16,
§18), against **real PostgreSQL and real NATS**:

    real lifecycle call (`sensor_lifecycle.transition`, real `FilesystemSensor`)
      → real `PostgresPerceptionRepository` → one committed outbox row
      → read back by **independent SQL** on its own connection
      → the real `dispatch_ready_events`, publishing through a bus bound exactly
        as the worker binds its own (`workers/__init__.py`)
      → a real NATS subscriber receives it: `event_id == row id`, the right
        subject, and a `status` that is one of `SensorState`'s six values.

The consumer half -- the same subject arriving at `cognitive-state-engine`'s
production subscription and landing in `cognitive_state.sensor_state` -- is that
engine's P-15. The two halves meet at the registered contract,
`PerceptionSensorHealthChangedPayload`; no test imports the other engine
(control 7, the 4F.6 precedent).

**Why not the shared `postgres_session_factory` fixture**: its writes never
commit and are invisible to a second connection, and both properties are the
claim here (`test_workspace_real_postgres_e2e.py` records the same reasoning).

`@pytest.mark.real_infra`: requires Docker (or equivalent real services).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import get_args
from uuid import uuid4

import pytest
from nova_contracts import EventEnvelope
from nova_contracts.events.perception import PerceptionSensorHealthChangedPayload
from nova_eventbus_sdk import BoundEventBus
from nova_eventbus_sdk.backends.nats import NatsEventBus
from nova_perception_engine import sensor_lifecycle
from nova_perception_engine.domain.sensor import SensorState
from nova_perception_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_perception_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_perception_engine.repository.outbox_dispatcher import dispatch_ready_events
from nova_perception_engine.repository.postgres_perception_repository import (
    PostgresPerceptionRepository,
)
from nova_perception_engine.sensors.filesystem_sensor import FilesystemSensor
from nova_service_kit import create_engine, create_session_factory
from nova_testkit.postgres import run_alembic_upgrade
from nova_testkit.waiting import wait_until
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
SUBJECT = "perception.sensor.health_changed"


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    os.environ["PERCEPTION_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
async def database(postgres_container: PostgresContainer) -> AsyncIterator[AsyncEngine]:
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
async def worker_bus(nats_container) -> AsyncIterator[BoundEventBus]:  # type: ignore[no-untyped-def]
    """Bound exactly as `workers/__init__.py::startup` binds the dispatcher's
    bus: this engine's name and its own allow-lists."""
    bus = BoundEventBus(
        NatsEventBus(servers=nats_container.nats_uri()),
        engine_name="perception-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )
    await bus.connect()
    yield bus
    await bus.close()


async def _outbox_rows(database: AsyncEngine) -> list[dict]:  # type: ignore[type-arg]
    """Independent SQL on its own connection -- never the repository that wrote."""
    async with database.connect() as connection:
        result = await connection.execute(
            text(
                "SELECT id, subject, payload, correlation_id, dispatched_at "
                "FROM perception.outbox_event ORDER BY created_at"
            )
        )
        return [dict(row) for row in result.mappings().all()]


async def test_p16_a_real_lifecycle_call_travels_the_outbox_to_a_real_subscriber(
    repository: PostgresPerceptionRepository,
    database: AsyncEngine,
    worker_bus: BoundEventBus,
    nats_event_bus: NatsEventBus,
) -> None:
    sensor = FilesystemSensor()
    correlation_id = uuid4()

    await sensor_lifecycle.transition(
        sensor, "initialize", repository=repository, correlation_id=correlation_id
    )

    rows = await _outbox_rows(database)
    assert len(rows) == 1
    row = rows[0]
    assert row["subject"] == SUBJECT
    assert row["payload"] == {
        "sensor_id": "companion-filesystem",
        "sensor_type": "filesystem",
        "status": "initialized",
        "schema_version": 1,
    }
    assert row["correlation_id"] == correlation_id
    assert row["dispatched_at"] is None  # queued, not published: that is the worker's job

    received: list[EventEnvelope] = []

    async def handler(envelope: EventEnvelope) -> None:
        received.append(envelope)

    subscription = await nats_event_bus.subscribe(SUBJECT, handler)
    try:
        assert await dispatch_ready_events(repository, worker_bus) == 1
        await wait_until(lambda: bool(received), timeout_s=10.0)
    finally:
        await subscription.unsubscribe()

    assert len(received) == 1
    envelope = received[0]
    assert envelope.event_id == row["id"]
    assert envelope.subject == SUBJECT
    assert envelope.source_engine == "perception-engine"
    assert envelope.correlation_id == correlation_id
    payload = PerceptionSensorHealthChangedPayload.model_validate(envelope.payload)
    assert payload.status in get_args(SensorState)
    assert payload.status == sensor.state()

    # Marked dispatched, so a second pass publishes nothing.
    assert (await _outbox_rows(database))[0]["dispatched_at"] is not None
    assert await dispatch_ready_events(repository, worker_bus) == 0


async def test_p16_a_no_op_transition_writes_no_row(
    repository: PostgresPerceptionRepository, database: AsyncEngine
) -> None:
    """M6 against the real table: `start` from `uninitialized` is undefined, the
    filesystem sensor stays put, and nothing reaches the outbox."""
    sensor = FilesystemSensor()

    await sensor_lifecycle.transition(
        sensor, "start", repository=repository, correlation_id=uuid4()
    )

    assert sensor.state() == "uninitialized"
    assert await _outbox_rows(database) == []
