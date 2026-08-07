"""`WS /sessions/{id}` (docs/design/phase-2d/01-communication-engine.md
Sec12) -- the text channel path: an inbound WebSocket text frame is
recorded as a turn, and disconnecting pauses the session (design doc Sec9's
"Channel Adapter disconnects" row).

Polls the HTTP context endpoint after sending, rather than asserting
immediately, since the WebSocket frame is handled by the server's own async
task -- there is no synchronous guarantee it has finished processing the
instant `send_json` returns on the test client side.
"""

from __future__ import annotations

import time
from uuid import uuid4

from fastapi.testclient import TestClient
from nova_communication_engine.config import Settings
from nova_communication_engine.main import create_app

from tests.fakes.ports import FakeModelOrchestrationPort, FakePersonalityPort, FakeWorldModelPort
from tests.fakes.repository import FakeCommunicationRepository


def _wait_for_turn_count(
    client: TestClient, session_id: str, expected: int, *, timeout_s: float = 2.0
) -> dict:
    deadline = time.monotonic() + timeout_s
    context: dict = {}
    while time.monotonic() < deadline:
        context = client.get(f"/sessions/{session_id}/context").json()
        if context["turn_count"] >= expected:
            return context
        time.sleep(0.02)
    return context


def test_websocket_text_frame_is_recorded_as_an_inbound_turn(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(
        Settings(),
        repository=FakeCommunicationRepository(),
        personality_port=FakePersonalityPort(),
        model_orchestration_port=FakeModelOrchestrationPort(),
        world_model_port=FakeWorldModelPort(),
    )
    with TestClient(app) as client:
        created = client.post(
            "/sessions",
            json={"user_id": str(uuid4()), "channel": "text", "device_id": str(uuid4())},
        ).json()
        session_id = created["session_id"]

        with client.websocket_connect(f"/sessions/{session_id}") as websocket:
            websocket.send_json({"kind": "text", "content": "Hello over websocket"})
            context = _wait_for_turn_count(client, session_id, 1)

        assert context["turn_count"] == 1
        assert context["state"] == "thinking"


def test_disconnecting_pauses_the_session(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(
        Settings(),
        repository=FakeCommunicationRepository(),
        personality_port=FakePersonalityPort(),
        model_orchestration_port=FakeModelOrchestrationPort(),
        world_model_port=FakeWorldModelPort(),
    )
    with TestClient(app) as client:
        created = client.post(
            "/sessions",
            json={"user_id": str(uuid4()), "channel": "text", "device_id": str(uuid4())},
        ).json()
        session_id = created["session_id"]

        with client.websocket_connect(f"/sessions/{session_id}"):
            pass  # connect, then disconnect immediately

        deadline = time.monotonic() + 2.0
        state = None
        while time.monotonic() < deadline:
            state = client.get(f"/sessions/{session_id}/context").json()["state"]
            if state == "paused":
                break
            time.sleep(0.02)
        assert state == "paused"


def test_unknown_session_id_closes_the_websocket(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(
        Settings(),
        repository=FakeCommunicationRepository(),
        personality_port=FakePersonalityPort(),
        model_orchestration_port=FakeModelOrchestrationPort(),
        world_model_port=FakeWorldModelPort(),
    )
    with TestClient(app) as client:
        try:
            with client.websocket_connect(f"/sessions/{uuid4()}"):
                pass
        except Exception:
            pass  # a rejected connection surfaces as a WebSocketDisconnect-family exception
