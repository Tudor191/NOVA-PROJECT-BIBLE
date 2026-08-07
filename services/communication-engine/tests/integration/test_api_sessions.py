"""End-to-end tests through `api/sessions.py` -- exercises the real FastAPI
app (lifespan-driven) against in-memory fakes for every port (no real
Postgres/Event Bus RPC involved).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from nova_communication_engine.config import Settings
from nova_communication_engine.main import create_app

from tests.fakes.ports import FakeModelOrchestrationPort, FakePersonalityPort, FakeWorldModelPort
from tests.fakes.repository import FakeCommunicationRepository


def _create_session_payload() -> dict:
    return {"user_id": str(uuid4()), "channel": "text", "device_id": str(uuid4())}


@pytest.fixture
def harness(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCommunicationRepository()
    app = create_app(
        Settings(),
        repository=repository,
        personality_port=FakePersonalityPort(),
        model_orchestration_port=FakeModelOrchestrationPort(),
        world_model_port=FakeWorldModelPort(),
    )
    with TestClient(app) as client:
        yield client, repository


def test_create_session_returns_idle_state(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    response = client.post("/v1/communication/sessions", json=_create_session_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "idle"
    assert body["channel"] == "text"


def test_full_session_lifecycle_through_the_http_api(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    created = client.post("/v1/communication/sessions", json=_create_session_payload()).json()
    session_id = created["session_id"]

    message = client.post(
        f"/v1/communication/sessions/{session_id}/messages", json={"content": "Hello NOVA"}
    )
    assert message.status_code == 202
    assert message.json()["session_id"] == session_id

    context = client.get(f"/v1/communication/sessions/{session_id}/context")
    assert context.status_code == 200
    assert context.json()["state"] == "thinking"
    assert context.json()["turn_count"] == 1

    # Closing from Thinking is not a documented transition (design doc
    # Sec3.1) -- only Waiting can close.
    premature_close = client.delete(f"/v1/communication/sessions/{session_id}")
    assert premature_close.status_code == 409


def test_pause_and_resume_through_the_http_api(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    created = client.post("/v1/communication/sessions", json=_create_session_payload()).json()
    session_id = created["session_id"]
    client.post(f"/v1/communication/sessions/{session_id}/messages", json={"content": "Hello"})

    paused = client.post(f"/v1/communication/sessions/{session_id}/pause")
    assert paused.status_code == 200
    assert paused.json()["state"] == "paused"

    resumed = client.post(f"/v1/communication/sessions/{session_id}/resume")
    assert resumed.status_code == 200
    assert resumed.json()["state"] == "listening"


def test_operations_on_a_missing_session_return_404(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    missing_id = uuid4()
    assert client.get(f"/v1/communication/sessions/{missing_id}/context").status_code == 404
    assert client.post(f"/v1/communication/sessions/{missing_id}/pause").status_code == 404
    assert client.delete(f"/v1/communication/sessions/{missing_id}").status_code == 404
