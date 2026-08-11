"""`GET /v1/digital-twin/preferences` (`api/preferences.py`)."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from nova_digital_twin_engine.config import Settings
from nova_digital_twin_engine.domain.models import CommunicationProfile
from nova_digital_twin_engine.main import create_app

from tests.fakes.repository import FakeDigitalTwinRepository


def test_preferences_returns_defaults_for_an_unknown_user(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeDigitalTwinRepository()
    app = create_app(Settings(), repository=repository)
    with TestClient(app) as client:
        user_id = uuid4()
        response = client.get("/v1/digital-twin/preferences", params={"user_id": str(user_id)})
        assert response.status_code == 200
        body = response.json()
        assert body["conversation_pacing"] is None
        assert body["habit_timing_hint"] is None


def test_preferences_returns_the_stored_values(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeDigitalTwinRepository()
    app = create_app(Settings(), repository=repository)
    with TestClient(app) as client:
        user_id = uuid4()
        repository.profiles[user_id] = CommunicationProfile(
            user_id=user_id, conversation_pacing="slow", habit_timing_hint="evenings"
        )
        response = client.get("/v1/digital-twin/preferences", params={"user_id": str(user_id)})
        body = response.json()
        assert body["conversation_pacing"] == "slow"
        assert body["habit_timing_hint"] == "evenings"
