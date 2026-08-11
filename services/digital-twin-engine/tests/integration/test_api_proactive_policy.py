"""`GET`/`PATCH /v1/digital-twin/proactive-policy` (`api/proactive_policy.py`)."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from nova_digital_twin_engine.config import Settings
from nova_digital_twin_engine.main import create_app

from tests.fakes.repository import FakeDigitalTwinRepository


def test_get_proactive_policy_returns_defaults_for_an_unknown_user(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeDigitalTwinRepository()
    app = create_app(Settings(), repository=repository)
    with TestClient(app) as client:
        user_id = uuid4()
        response = client.get(
            "/v1/digital-twin/proactive-policy", params={"user_id": str(user_id)}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["enabled"] is True
        assert body["max_per_topic_per_window"] == {}
        assert body["window_hours"] == 24


def test_patch_proactive_policy_configures_a_topic_limit(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeDigitalTwinRepository()
    app = create_app(Settings(), repository=repository)
    with TestClient(app) as client:
        user_id = uuid4()
        response = client.patch(
            "/v1/digital-twin/proactive-policy",
            params={"user_id": str(user_id)},
            json={"max_per_topic_per_window": {"deploy": 3}},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["max_per_topic_per_window"] == {"deploy": 3}
        assert body["enabled"] is True  # untouched field preserved
