"""The `perception.sensor.health_changed` handler -- TDD 4F.7 §8.2, §28.2.

What this tier can prove without a broker or a database: what the handler hands
to the store, and what it refuses to. The store here is a behavioural in-memory
one that *keeps* records, so every assertion is about the resulting state -- what
is stored -- and never merely that a method was called.

The conditional-upsert semantics themselves (redelivery, order) live in SQL and
are proven against real Postgres in
`tests/integration/test_sensor_state_real_infra.py` (P-15, P-25); a fake that
re-implemented them would only prove that the fake agrees with itself.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from nova_cognitive_state_engine.domain.sensor_state import SensorStateRecord
from nova_cognitive_state_engine.events.handlers import (
    SENSOR_HEALTH_SUBJECT,
    make_sensor_health_handler,
)
from nova_contracts import EventEnvelope


class KeepingStore:
    """Stores what it is given, one record per `sensor_id`, last write wins."""

    def __init__(self) -> None:
        self.records: dict[str, SensorStateRecord] = {}

    async def apply_sensor_report(self, record: SensorStateRecord) -> bool:
        self.records[record.sensor_id] = record
        return True

    async def list_sensor_states(self) -> list[SensorStateRecord]:
        return [self.records[key] for key in sorted(self.records)]


class FailingStore(KeepingStore):
    async def apply_sensor_report(self, record: SensorStateRecord) -> bool:
        raise ConnectionError("store unavailable")


def _envelope(
    status: str, *, sensor_id: str = "companion-filesystem", **payload: object
) -> EventEnvelope:
    body: dict[str, object] = {
        "sensor_id": sensor_id,
        "sensor_type": "filesystem",
        "status": status,
        "schema_version": 1,
    }
    body.update(payload)
    return EventEnvelope(
        subject=SENSOR_HEALTH_SUBJECT,
        source_engine="perception-engine",
        correlation_id=uuid4(),
        payload=body,
    )


@pytest.mark.parametrize(
    "status", ["uninitialized", "initialized", "running", "paused", "stopped", "failed"]
)
async def test_a_lifecycle_report_is_stored_unchanged(status: str) -> None:
    store = KeepingStore()
    envelope = _envelope(status)
    await make_sensor_health_handler(store)(envelope)

    record = store.records["companion-filesystem"]
    assert record.state == status
    assert record.sensor_type == "filesystem"
    assert record.reported_at == envelope.occurred_at  # dispatch time, named for what it is
    assert record.last_event_id == envelope.event_id


@pytest.mark.parametrize(
    "status", ["healthy", "unhealthy", "unrecognized", "Running", " running", ""]
)
async def test_an_unknown_status_is_not_stored_and_is_logged(
    status: str, caplog: pytest.LogCaptureFixture
) -> None:
    store = KeepingStore()
    with caplog.at_level(logging.WARNING):
        await make_sensor_health_handler(store)(_envelope(status))

    assert store.records == {}
    assert any(
        r.levelno == logging.WARNING and r.getMessage() == "sensor_report_rejected_unknown_status"
        for r in caplog.records
    )


async def test_an_unknown_status_leaves_the_previous_known_state_unchanged() -> None:
    """A-4F7-1: the table keeps *"the latest normalized known state"*. A
    rejected report is not a state, so it must not displace one."""
    store = KeepingStore()
    handler = make_sensor_health_handler(store)
    known = _envelope("running")
    await handler(known)

    await handler(_envelope("healthy"))

    record = store.records["companion-filesystem"]
    assert record.state == "running"
    assert record.last_event_id == known.event_id
    assert record.reported_at == known.occurred_at


async def test_an_invalid_payload_is_not_stored(caplog: pytest.LogCaptureFixture) -> None:
    store = KeepingStore()
    broken = EventEnvelope(
        subject=SENSOR_HEALTH_SUBJECT,
        source_engine="perception-engine",
        correlation_id=uuid4(),
        payload={"sensor_id": "companion-filesystem"},  # no sensor_type, no status
    )
    with caplog.at_level(logging.WARNING):
        await make_sensor_health_handler(store)(broken)

    assert store.records == {}
    assert any(r.getMessage() == "sensor_report_rejected_invalid_payload" for r in caplog.records)


async def test_a_store_failure_is_logged_and_never_raised(caplog: pytest.LogCaptureFixture) -> None:
    """The handler runs inside the SDK's NATS callback, where a raised exception
    reaches nothing that could act on it."""
    with caplog.at_level(logging.ERROR):
        await make_sensor_health_handler(FailingStore())(_envelope("running"))

    assert any(r.getMessage() == "sensor_report_not_stored" for r in caplog.records)


async def test_reported_at_is_the_envelope_time_not_the_handler_clock() -> None:
    """No fabricated timestamp: `reported_at` is the envelope's own
    `occurred_at`, even when that is well in the past."""
    store = KeepingStore()
    past = datetime.now(UTC) - timedelta(hours=3)
    envelope = _envelope("stopped").model_copy(update={"occurred_at": past})
    await make_sensor_health_handler(store)(envelope)

    assert store.records["companion-filesystem"].reported_at == past
