"""**S-3 and S-4**, through the real lifespan-driven app with the sensor registered.

4F.2 could only reach this route by injecting a sensor into `app.state`, because
`sensors_by_source` had no `"filesystem"` key. 4F.3 registers one, so these run
against the **real** `create_app` wiring: the real `FilesystemSensor`, the real
route, the real orchestration, the real `domain/workspace.py`, and the real
outbox call. Only the repository and the model port are fakes — the same two
every other integration test in this engine fakes, for the same reasons.

- **S-3**: exactly one outbox row for one accepted event.
- **S-4**: the raw path is absent from that row's payload.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from nova_perception_engine.config import Settings
from nova_perception_engine.domain.workspace import object_id_for_path
from nova_perception_engine.main import create_app

from tests.fakes.ai_model_port import FakeAIModelOrchestrationPort
from tests.fakes.repository import FakePerceptionRepository

_PRIMARY_USER_ID = uuid4()
_ENCRYPTION_KEY = "3ktMjuHsQ9TNWhEiReuORzkawsz4KEYq2zDMZByQhHo="  # test-only Fernet key

# A path with several identifying segments, so "the path did not leak" is a
# meaningful assertion rather than one satisfied by a short name.
PATH = "/home/ada/projects/analytical-engine/design/notes.md"
SEGMENTS = ("home", "ada", "projects", "analytical-engine", "design")


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
        yield client, repository, app


def _rows(repository: FakePerceptionRepository) -> list:
    return list(repository.outbox.values())


def _submit(client: TestClient, *, path: str = PATH, at: datetime | None = None):  # type: ignore[no-untyped-def]
    return client.post(
        "/v1/perception/workspace-observations",
        params={"source": "filesystem"},
        json={"path": path, "observed_at": (at or datetime.now(UTC)).isoformat()},
    )


def test_the_filesystem_source_is_registered(harness) -> None:  # type: ignore[no-untyped-def]
    """**L-12 settled.** The gap 4F.2 shipped and disclosed is closed: the route
    no longer 404s on `source=filesystem`."""
    _, _, app = harness
    assert "filesystem" in app.state.sensors_by_source
    assert app.state.sensors_by_source["filesystem"].state() == "running"


def test_the_registry_entry_appears_on_the_sensors_surface(harness) -> None:  # type: ignore[no-untyped-def]
    client, _, _ = harness
    listed = client.get("/v1/perception/sensors").json()
    assert "companion-filesystem" in {entry["sensor_id"] for entry in listed}


def test_s3_one_accepted_event_produces_exactly_one_outbox_row(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository, _ = harness
    response = _submit(client)

    assert response.status_code == 202, response.text
    assert response.json()["published"] is True
    assert len(_rows(repository)) == 1
    assert _rows(repository)[0].subject == "perception.workspace.observed"


def test_s4_the_raw_path_is_absent_from_the_outbox_payload(harness) -> None:  # type: ignore[no-untyped-def]
    """**The security property, against a real OS-shaped path.**

    Checked over the whole serialized row, not just `object_id`: a leak into
    any field would be equally bad, and checking one field would miss it.
    """
    client, repository, _ = harness
    _submit(client)

    row = _rows(repository)[0]
    serialized = str(row.payload)

    assert PATH not in serialized
    for segment in SEGMENTS:
        assert segment not in serialized, f"path segment {segment!r} leaked into the payload"

    assert row.payload["object_id"] == object_id_for_path(PATH)
    assert row.payload["label"] == "notes.md"


def test_s4_the_http_response_does_not_echo_the_path_either(harness) -> None:  # type: ignore[no-untyped-def]
    client, _, _ = harness
    body = _submit(client).text
    assert PATH not in body
    for segment in SEGMENTS:
        assert segment not in body


def test_the_user_id_is_resolved_server_side(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository, _ = harness
    _submit(client)
    assert _rows(repository)[0].payload["user_id"] == str(_PRIMARY_USER_ID)


def test_a_client_supplied_user_id_is_ignored(harness) -> None:  # type: ignore[no-untyped-def]
    """The identity boundary end to end: the field does not exist on the
    request model, so a hostile body cannot reach `user_id`."""
    client, repository, _ = harness
    hostile = uuid4()
    response = client.post(
        "/v1/perception/workspace-observations",
        params={"source": "filesystem"},
        json={
            "path": PATH,
            "observed_at": datetime.now(UTC).isoformat(),
            "user_id": str(hostile),
        },
    )

    assert response.status_code == 202
    payload = _rows(repository)[0].payload
    assert payload["user_id"] == str(_PRIMARY_USER_ID)
    assert str(hostile) not in str(payload)


def test_a_burst_is_debounced_to_one_row(harness) -> None:  # type: ignore[no-untyped-def]
    """Exactly-once for one logical edit, through the real debouncer."""
    client, repository, _ = harness
    start = datetime.now(UTC)
    for offset in (0.0, 0.2, 0.5, 0.9):
        _submit(client, at=start + timedelta(seconds=offset))

    assert len(_rows(repository)) == 1


def test_a_separate_edit_after_the_window_publishes_again(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository, _ = harness
    start = datetime.now(UTC)
    _submit(client, at=start)
    _submit(client, at=start + timedelta(seconds=5))

    assert len(_rows(repository)) == 2


def test_a_paused_sensor_drops_the_observation(harness) -> None:  # type: ignore[no-untyped-def]
    """AC-7 clause 2 at the pipeline level, now exercisable because the sensor
    is really registered and can really be paused."""
    client, repository, app = harness
    sensor = app.state.sensors_by_source["filesystem"]

    # `pause()` is async by Protocol but does no I/O -- it moves one field
    # through `next_state`. `asyncio.run` drives it without needing the
    # TestClient's own loop, which is not reachable from this synchronous body.
    asyncio.run(sensor.pause())
    assert sensor.state() == "paused"

    response = _submit(client)
    assert response.status_code == 202
    assert response.json()["published"] is False
    assert response.json()["reason"] == "sensor_not_running"
    assert _rows(repository) == []


def test_an_unknown_source_still_404s(harness) -> None:  # type: ignore[no-untyped-def]
    """Registering `"filesystem"` must not make every source resolve."""
    client, _, _ = harness
    response = client.post(
        "/v1/perception/workspace-observations",
        params={"source": "not-a-sensor"},
        json={"path": PATH, "observed_at": datetime.now(UTC).isoformat()},
    )
    assert response.status_code == 404


def test_a_malformed_body_is_rejected_without_publishing(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository, _ = harness
    missing_timestamp = client.post(
        "/v1/perception/workspace-observations",
        params={"source": "filesystem"},
        json={"path": PATH},
    )
    assert missing_timestamp.status_code == 422
    assert _rows(repository) == []


def test_the_existing_biometric_route_is_unaffected(harness) -> None:  # type: ignore[no-untyped-def]
    """4F.3 changes no existing contract. The window route still 404s for an
    unregistered source and still takes a raw body, not JSON."""
    client, _, _ = harness
    response = client.post(
        "/v1/perception/observations", params={"source": "not-a-sensor"}, content=b"\x00" * 32
    )
    assert response.status_code == 404
