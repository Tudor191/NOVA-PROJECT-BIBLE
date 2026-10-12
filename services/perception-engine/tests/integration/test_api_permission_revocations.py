"""**D2 through the real app: a revocation report fails the filesystem sensor,
publishes `failed`, and stops the workspace stream** (TDD 4F.8 §29.1 A-4F8-1
(a), (a1), (a2); E-5 and E-6 at the engine's boundary).

The real `create_app`, the real `FilesystemSensor`, the real route, the real
`sensor_lifecycle` and the real workspace gate. Only the repository and the
model port are fakes, as in every other integration test in this engine. The
real-infrastructure tier, with the real companion process, real PostgreSQL and
real NATS, is `test_permission_revocation_real_infra.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from nova_perception_engine.config import Settings
from nova_perception_engine.main import create_app

from tests.fakes.ai_model_port import FakeAIModelOrchestrationPort
from tests.fakes.repository import FakePerceptionRepository
from tests.integration.startup_reports import take_startup_reports

_PRIMARY_USER_ID = uuid4()
_ENCRYPTION_KEY = "3ktMjuHsQ9TNWhEiReuORzkawsz4KEYq2zDMZByQhHo="  # test-only Fernet key
HEALTH = "perception.sensor.health_changed"
ROUTE = "/v1/perception/permission-revocations"


@pytest.fixture
def harness(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakePerceptionRepository()
    app = create_app(
        Settings(primary_user_id=_PRIMARY_USER_ID, template_encryption_key=_ENCRYPTION_KEY),
        repository=repository,
        ai_model_port=FakeAIModelOrchestrationPort(),
    )
    with TestClient(app) as client:
        take_startup_reports(repository)
        yield client, repository, app


def _revoke(client: TestClient, *, source: str = "filesystem", **params):  # type: ignore[no-untyped-def]
    return client.post(
        ROUTE,
        params={"source": source, **params},
        json={"detected_at": datetime.now(UTC).isoformat()},
    )


def _health_reports(repository: FakePerceptionRepository) -> list[dict]:  # type: ignore[type-arg]
    return [row.payload for row in repository.outbox.values() if row.subject == HEALTH]


def test_a_report_fails_the_sensor_and_publishes_failed_once(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository, app = harness
    correlation_id = uuid4()

    response = _revoke(client, correlation_id=str(correlation_id))

    assert response.status_code == 202
    assert response.json() == {
        "sensor_id": "companion-filesystem",
        "state": "failed",
        "transitioned": True,
    }
    assert app.state.sensors_by_source["filesystem"].state() == "failed"
    assert _health_reports(repository) == [
        {
            "sensor_id": "companion-filesystem",
            "sensor_type": "filesystem",
            "status": "failed",
            "schema_version": 1,
        }
    ]
    (row,) = repository.outbox.values()
    assert row.correlation_id == correlation_id


def test_the_sensors_surface_shows_the_failure(harness) -> None:  # type: ignore[no-untyped-def]
    client, _, _ = harness
    _revoke(client)
    listed = {entry["sensor_id"]: entry for entry in client.get("/v1/perception/sensors").json()}
    assert listed["companion-filesystem"]["state"] == "failed"
    assert listed["companion-filesystem"]["available"] is False


def test_every_later_observation_is_dropped(harness) -> None:  # type: ignore[no-untyped-def]
    """E-6 at the engine: after the report, the existing `running` gate drops a
    workspace observation, and nothing reaches the outbox."""
    client, repository, _ = harness
    _revoke(client)
    before = len(repository.outbox)

    response = client.post(
        "/v1/perception/workspace-observations",
        params={"source": "filesystem"},
        json={"path": "/workspace/after.md", "observed_at": datetime.now(UTC).isoformat()},
    )

    assert response.status_code == 202
    assert response.json()["published"] is False
    assert response.json()["reason"] == "sensor_not_running"
    assert len(repository.outbox) == before


def test_a_repeated_report_changes_nothing_and_publishes_nothing(harness) -> None:  # type: ignore[no-untyped-def]
    """A-4F8-1 (a2): no recovery, and an unacknowledged report the companion
    resends must not publish a second `failed`."""
    client, repository, _ = harness
    _revoke(client)

    response = _revoke(client)

    assert response.status_code == 202
    assert response.json()["state"] == "failed"
    assert response.json()["transitioned"] is False
    assert len(_health_reports(repository)) == 1


def test_an_unregistered_or_unratified_source_is_refused(harness) -> None:  # type: ignore[no-untyped-def]
    """Only the companion's source can be reported. A camera, which this route
    was not ratified for, stays running."""
    client, repository, app = harness

    assert _revoke(client, source="nowhere").status_code == 404
    assert _revoke(client, source="camera").status_code == 404
    assert app.state.sensors_by_source["camera"].state() == "running"
    assert repository.outbox == {}


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"detected_at": "2026-10-11T00:00:00Z", "path": "/workspace"},
        {"detected_at": "2026-10-11T00:00:00Z", "user_id": str(uuid4())},
    ],
)
def test_the_body_is_exactly_a_detection_time(harness, body) -> None:  # type: ignore[no-untyped-def]
    """No path and no identity can be supplied: either is refused, not ignored."""
    client, repository, app = harness
    response = client.post(ROUTE, params={"source": "filesystem"}, json=body)
    assert response.status_code == 422
    assert app.state.sensors_by_source["filesystem"].state() == "running"
    assert repository.outbox == {}
