"""End-to-end tests through `api/consent.py` -- exercises the real FastAPI
app (lifespan-driven) against in-memory fakes (docs/design/phase-2d/
03-perception-engine.md §3.3, §11, §14). Revocation's synchronous sensor
`stop()` call is asserted directly, not just the persistence half.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from nova_perception_engine.config import Settings
from nova_perception_engine.main import create_app

from tests.fakes.ai_model_port import FakeAIModelOrchestrationPort
from tests.fakes.repository import FakePerceptionRepository


@pytest.fixture
def harness(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakePerceptionRepository()
    app = create_app(
        Settings(), repository=repository, ai_model_port=FakeAIModelOrchestrationPort()
    )
    with TestClient(app) as client:
        yield client, app


def test_grant_consent_then_status_reflects_it(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    user_id = uuid4()

    grant = client.post(
        "/v1/perception/consent",
        json={"user_id": str(user_id), "source": "camera", "scope": "presence detection"},
    )
    assert grant.status_code == 201
    assert grant.json()["revoked_at"] is None

    status = client.get("/v1/perception/consent", params={"user_id": str(user_id)})
    assert status.status_code == 200
    assert len(status.json()) == 1


def test_revoke_consent_with_no_active_grant_is_404(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    response = client.delete(
        "/v1/perception/consent/microphone", params={"user_id": str(uuid4())}
    )
    assert response.status_code == 404


def test_revoke_consent_stops_the_matching_sensor(harness) -> None:  # type: ignore[no-untyped-def]
    client, app = harness
    user_id = uuid4()
    client.post(
        "/v1/perception/consent",
        json={"user_id": str(user_id), "source": "microphone", "scope": "wake detection"},
    )
    voice_sensor = app.state.sensors_by_source["microphone"]
    assert voice_sensor.state() == "running"  # started at engine startup

    response = client.delete(
        "/v1/perception/consent/microphone", params={"user_id": str(user_id)}
    )

    assert response.status_code == 200
    assert response.json()["revoked_at"] is not None
    assert voice_sensor.state() == "stopped"


async def test_revoke_consent_on_an_already_stopped_sensor_does_not_raise(harness) -> None:  # type: ignore[no-untyped-def]
    client, app = harness
    user_id = uuid4()
    client.post(
        "/v1/perception/consent",
        json={"user_id": str(user_id), "source": "camera", "scope": "presence"},
    )
    camera_sensor = app.state.sensors_by_source["camera"]
    await camera_sensor.stop()  # already stopped before revocation runs

    response = client.delete("/v1/perception/consent/camera", params={"user_id": str(user_id)})

    assert response.status_code == 200
