"""The four production call-site groups report their lifecycle transitions --
Phase 4F.7, TDD 4F.7 §8.1, **P-12** and **P-23** (§16, §28.4).

Every test drives the **real** lifespan-driven `create_app` and the real sensor
classes. Only the repository and the model port are the fakes every other
perception integration test uses. Each assertion is on the recorded outbox
rows: which sensor, which lifecycle state, which correlation id -- and that
**nothing else** was reported.

| Call-site group | Correlation id (§8.1) |
|---|---|
| Startup (`main.py`) | one fresh `uuid4()` for the whole startup |
| Consent revocation (`api/consent.py`) | the revoked grant's `consent_id` |
| Observation-window failure (`observation_orchestration.py`) | the observation's `correlation_id` |
| Shutdown (`main.py`) | one fresh `uuid4()` for the whole shutdown |
"""

from __future__ import annotations

from typing import get_args
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from nova_perception_engine.config import Settings
from nova_perception_engine.domain.sensor import SensorState
from nova_perception_engine.main import create_app

from tests.fakes.ai_model_port import FakeAIModelOrchestrationPort
from tests.fakes.repository import FakePerceptionRepository
from tests.integration.startup_reports import (
    STARTUP_REPORTS,
    SUBJECT,
    startup_reports_in,
    take_startup_reports,
)

_PRIMARY_USER_ID = uuid4()
_LOUD = bytes([200]) * 320


class _FailingDetectionPort(FakeAIModelOrchestrationPort):
    """The model boundary (ADR-020) raising mid-window -- the one way a real
    observation reaches `handle_observation_window`'s failure branch."""

    async def detect_wake_phrase(self, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("model call failed")

    async def estimate_gaze(self, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("model call failed")


def _app(repository: FakePerceptionRepository, port: FakeAIModelOrchestrationPort | None = None):  # type: ignore[no-untyped-def]
    return create_app(
        Settings(primary_user_id=_PRIMARY_USER_ID),
        repository=repository,
        ai_model_port=port or FakeAIModelOrchestrationPort(),
    )


def _health_rows(repository: FakePerceptionRepository) -> list:  # type: ignore[type-arg]
    return [row for row in repository.outbox.values() if row.subject == SUBJECT]


def _reports(repository: FakePerceptionRepository) -> list[tuple[str, str, str, UUID]]:
    return [
        (
            row.payload["sensor_id"],
            row.payload["sensor_type"],
            row.payload["status"],
            row.correlation_id,
        )
        for row in _health_rows(repository)
    ]


@pytest.fixture(autouse=True)
def _in_memory_bus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")


# --- startup -------------------------------------------------------------------------


def test_startup_reports_each_sensors_initialized_then_running() -> None:
    repository = FakePerceptionRepository()
    with TestClient(_app(repository)):
        rows = list(repository.outbox.values())
        assert startup_reports_in(rows) == STARTUP_REPORTS
        assert len(rows) == 6
        assert len({row.correlation_id for row in rows}) == 1
        assert all(row.payload["status"] in get_args(SensorState) for row in rows)


# --- consent revocation ------------------------------------------------------------------


def test_revoking_consent_reports_the_stop_correlated_to_the_grant() -> None:
    repository = FakePerceptionRepository()
    with TestClient(_app(repository)) as client:
        take_startup_reports(repository)
        user_id = uuid4()
        client.post(
            "/v1/perception/consent",
            json={"user_id": str(user_id), "source": "microphone", "scope": "wake detection"},
        )
        revoked = client.delete(
            "/v1/perception/consent/microphone", params={"user_id": str(user_id)}
        )
        assert revoked.status_code == 200

        assert _reports(repository) == [
            ("voice-sensor-1", "voice", "stopped", UUID(revoked.json()["consent_id"]))
        ]


def test_revoking_consent_for_an_already_stopped_sensor_reports_nothing() -> None:
    """M6 at a call site. The sensor is already `stopped`; revocation performs no
    transition, so there is nothing to report."""
    repository = FakePerceptionRepository()
    with TestClient(_app(repository)) as client:
        take_startup_reports(repository)
        user_id = uuid4()
        for _ in range(2):
            client.post(
                "/v1/perception/consent",
                json={"user_id": str(user_id), "source": "camera", "scope": "presence"},
            )
            client.delete("/v1/perception/consent/camera", params={"user_id": str(user_id)})

        assert [status for _, _, status, _ in _reports(repository)] == ["stopped"]


# --- observation-window failure --------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "sensor_id", "sensor_type"),
    [("microphone", "voice-sensor-1", "voice"), ("camera", "camera-sensor-1", "camera")],
)
def test_a_failed_observation_window_reports_failed_correlated_to_it(
    source: str, sensor_id: str, sensor_type: str
) -> None:
    repository = FakePerceptionRepository()
    with TestClient(_app(repository, _FailingDetectionPort())) as client:
        take_startup_reports(repository)
        correlation_id = uuid4()
        response = client.post(
            "/v1/perception/observations",
            params={"source": source, "correlation_id": str(correlation_id)},
            content=_LOUD,
        )
        assert response.status_code == 202
        assert response.json()["published"] is False

        assert _reports(repository) == [(sensor_id, sensor_type, "failed", correlation_id)]
        assert [row.subject for row in repository.outbox.values()] == [SUBJECT]


# --- shutdown --------------------------------------------------------------------------


def test_shutdown_reports_each_running_sensor_stopped() -> None:
    repository = FakePerceptionRepository()
    with TestClient(_app(repository)):
        take_startup_reports(repository)

    reports = _reports(repository)
    assert [(sensor, kind, status) for sensor, kind, status, _ in reports] == [
        ("voice-sensor-1", "voice", "stopped"),
        ("camera-sensor-1", "camera", "stopped"),
        ("companion-filesystem", "filesystem", "stopped"),
    ]
    assert len({correlation for *_, correlation in reports}) == 1


def test_shutdown_reports_nothing_for_a_sensor_that_was_already_stopped() -> None:
    """M6 at shutdown: a sensor stopped by a revocation is not stopped again, so
    shutdown reports only the two that were still running."""
    repository = FakePerceptionRepository()
    with TestClient(_app(repository)) as client:
        take_startup_reports(repository)
        user_id = uuid4()
        client.post(
            "/v1/perception/consent",
            json={"user_id": str(user_id), "source": "microphone", "scope": "wake detection"},
        )
        client.delete("/v1/perception/consent/microphone", params={"user_id": str(user_id)})
        before_shutdown = len(_health_rows(repository))

    after = _reports(repository)[before_shutdown:]
    assert [(sensor, status) for sensor, _, status, _ in after] == [
        ("camera-sensor-1", "stopped"),
        ("companion-filesystem", "stopped"),
    ]
