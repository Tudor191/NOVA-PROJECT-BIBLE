"""`sensor_lifecycle` over the **real** sensor classes -- Phase 4F.7, TDD 4F.7
§8.1, P-12 and P-23 (§16, §28.4).

The sensors are the real `VoiceSensor`, `CameraSensor` and `FilesystemSensor`,
running their real `domain/sensor.py` state machine. The repository is the
behavioural in-memory one every perception test uses, and it **keeps** what it
is given: each assertion is on the recorded outbox row's subject and payload,
never merely on a call having happened (TDD 4F.7 §18).

- **P-12:** exactly one report per real change, carrying the new state; **zero**
  for a no-op (M6). `stop` is reported (M7).
- **P-23:** every reported `status` is a `SensorState` value and equals
  `sensor.state()` read after the call -- never `health_check()`'s
  `"healthy"` / `"unhealthy"` (M17).

The four production call-site groups are asserted through the real app in
`tests/integration/test_sensor_lifecycle_call_sites.py`.
"""

from __future__ import annotations

import logging
from typing import get_args
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from nova_perception_engine import sensor_lifecycle
from nova_perception_engine.domain.ports import OutboxEvent
from nova_perception_engine.domain.sensor import SensorErrorReport, SensorState
from nova_perception_engine.sensors.camera_sensor import CameraSensor
from nova_perception_engine.sensors.filesystem_sensor import FilesystemSensor
from nova_perception_engine.sensors.voice_sensor import VoiceSensor

from tests.fakes.ai_model_port import FakeAIModelOrchestrationPort
from tests.fakes.repository import FakePerceptionRepository

SUBJECT = "perception.sensor.health_changed"
_KEY = Fernet.generate_key()


def _sensor(kind: str, repository: FakePerceptionRepository):  # type: ignore[no-untyped-def]
    if kind == "filesystem":
        return FilesystemSensor()
    cls = VoiceSensor if kind == "voice" else CameraSensor
    return cls(
        repository=repository, ai_model_port=FakeAIModelOrchestrationPort(), encryption_key=_KEY
    )


def _reports(repository: FakePerceptionRepository) -> list[dict]:  # type: ignore[type-arg]
    return [row.payload for row in repository.outbox.values() if row.subject == SUBJECT]


def _error(sensor_id: str) -> SensorErrorReport:
    return SensorErrorReport(sensor_id=sensor_id, message="boom", occurred_at="2026-09-26T08:00Z")


_TYPES = {"voice": "voice", "camera": "camera", "filesystem": "filesystem"}


# --- P-12 / P-23: one report per real change ---------------------------------------------


@pytest.mark.parametrize("kind", ["voice", "camera", "filesystem"])
async def test_each_real_transition_reports_exactly_its_new_state(kind: str) -> None:
    repository = FakePerceptionRepository()
    sensor = _sensor(kind, repository)
    correlation_id = uuid4()

    expected: list[str] = []
    for action in ("initialize", "start", "stop"):
        await sensor_lifecycle.transition(
            sensor, action, repository=repository, correlation_id=correlation_id
        )
        expected.append(sensor.state())

    assert expected == ["initialized", "running", "stopped"]
    assert _reports(repository) == [
        {
            "sensor_id": sensor.sensor_id,
            "sensor_type": _TYPES[kind],
            "status": status,
            "schema_version": 1,
        }
        for status in expected
    ]
    assert {row.correlation_id for row in repository.outbox.values()} == {correlation_id}


@pytest.mark.parametrize("kind", ["voice", "camera", "filesystem"])
async def test_p23_every_status_is_a_sensor_state_value_equal_to_the_state_after(
    kind: str,
) -> None:
    """P-23 / M17. Each report is compared with `sensor.state()` read right after
    the call that produced it, and with the vocabulary itself."""
    repository = FakePerceptionRepository()
    sensor = _sensor(kind, repository)
    vocabulary = set(get_args(SensorState))

    for action in ("initialize", "start", "stop"):
        await sensor_lifecycle.transition(
            sensor, action, repository=repository, correlation_id=uuid4()
        )
        latest = _reports(repository)[-1]["status"]
        assert latest == sensor.state()
        assert latest in vocabulary
        assert latest not in {"healthy", "unhealthy"}


@pytest.mark.parametrize("kind", ["voice", "camera"])
async def test_a_reported_error_that_fails_the_sensor_reports_failed(kind: str) -> None:
    repository = FakePerceptionRepository()
    sensor = _sensor(kind, repository)
    await sensor.initialize()
    await sensor.start()
    correlation_id = uuid4()

    await sensor_lifecycle.report_sensor_error(
        sensor, _error(sensor.sensor_id), repository=repository, correlation_id=correlation_id
    )

    assert sensor.state() == "failed"
    assert _reports(repository) == [
        {
            "sensor_id": sensor.sensor_id,
            "sensor_type": _TYPES[kind],
            "status": "failed",
            "schema_version": 1,
        }
    ]
    assert next(iter(repository.outbox.values())).correlation_id == correlation_id


# --- P-12 / M6: no report for a no-op ------------------------------------------------------


async def test_the_filesystem_sensor_reports_nothing_on_error_it_has_no_failed_path() -> None:
    """RS-3b: the filesystem sensor records the error and stays `running`. 4F.7
    adds no `failed` path, so there is no change and nothing is reported."""
    repository = FakePerceptionRepository()
    sensor = FilesystemSensor()
    await sensor.initialize()
    await sensor.start()

    await sensor_lifecycle.report_sensor_error(
        sensor, _error(sensor.sensor_id), repository=repository, correlation_id=uuid4()
    )

    assert sensor.state() == "running"
    assert len(sensor.errors) == 1
    assert repository.outbox == {}


@pytest.mark.parametrize(
    ("prepare", "action"),
    [
        ((), "start"),  # uninitialized -> start: undefined
        (("initialize",), "initialize"),  # initialized -> initialize: undefined
        (("initialize", "start"), "start"),  # running -> start: undefined
        (("initialize", "start", "stop"), "stop"),  # stopped -> stop: undefined
    ],
)
async def test_a_no_op_transition_reports_nothing(prepare: tuple[str, ...], action: str) -> None:
    """M6. The filesystem sensor treats an undefined pair as a no-op
    (`filesystem_sensor.py::_transition`), so its state is unchanged and a report
    would fabricate a change."""
    repository = FakePerceptionRepository()
    sensor = FilesystemSensor()
    for step in prepare:
        await getattr(sensor, step)()
    before = sensor.state()

    await sensor_lifecycle.transition(
        sensor,
        action,  # type: ignore[arg-type]
        repository=repository,
        correlation_id=uuid4(),
    )

    assert sensor.state() == before
    assert repository.outbox == {}


@pytest.mark.parametrize("kind", ["voice", "camera"])
async def test_an_illegal_transition_still_raises_and_reports_nothing(kind: str) -> None:
    """The camera and voice sensors reject an undefined pair by raising. That is
    unchanged: the helper neither swallows it nor reports a change that did not
    happen."""
    repository = FakePerceptionRepository()
    sensor = _sensor(kind, repository)

    with pytest.raises(ValueError, match="Illegal transition"):
        await sensor_lifecycle.transition(
            sensor, "start", repository=repository, correlation_id=uuid4()
        )

    assert sensor.state() == "uninitialized"
    assert repository.outbox == {}


# --- an enqueue failure ----------------------------------------------------------------


class _UnavailableOutbox(FakePerceptionRepository):
    async def enqueue_outbox(self, event: OutboxEvent):  # type: ignore[no-untyped-def]
        raise ConnectionError("outbox unavailable")


async def test_an_enqueue_failure_is_logged_and_the_transition_stands(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The report is about a transition that already happened; failing to queue
    it neither undoes the transition nor aborts its caller. Nothing retries it."""
    repository = _UnavailableOutbox()
    sensor = FilesystemSensor()

    with caplog.at_level(logging.ERROR):
        await sensor_lifecycle.transition(
            sensor, "initialize", repository=repository, correlation_id=uuid4()
        )

    assert sensor.state() == "initialized"
    assert repository.outbox == {}
    assert any(r.getMessage() == "sensor_lifecycle_report_not_enqueued" for r in caplog.records)
