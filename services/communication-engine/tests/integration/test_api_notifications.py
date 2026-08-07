"""`POST /notifications` (docs/design/phase-2d/01-communication-engine.md
Sec10, Sec12)."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from nova_communication_engine.config import Settings
from nova_communication_engine.main import create_app

from tests.fakes.ports import FakeModelOrchestrationPort, FakePersonalityPort, FakeWorldModelPort
from tests.fakes.repository import FakeCommunicationRepository


def test_create_notification_defaults_priority_and_leaves_it_undelivered(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(
        Settings(),
        repository=FakeCommunicationRepository(),
        personality_port=FakePersonalityPort(),
        model_orchestration_port=FakeModelOrchestrationPort(),
        world_model_port=FakeWorldModelPort(),
    )
    with TestClient(app) as client:
        response = client.post(
            "/notifications", json={"user_id": str(uuid4()), "content": "Your report is ready."}
        )

    assert response.status_code == 201
    body = response.json()
    assert body["priority"] == "normal"
    assert body["delivered_at"] is None
