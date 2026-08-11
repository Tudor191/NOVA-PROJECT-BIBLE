"""`GET`/`PATCH /v1/digital-twin/profile`, `POST /v1/digital-twin/reset`
(`api/profile.py`)."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from nova_digital_twin_engine.config import Settings
from nova_digital_twin_engine.main import create_app

from tests.fakes.repository import FakeDigitalTwinRepository


def _client(monkeypatch, repository: FakeDigitalTwinRepository) -> TestClient:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings(), repository=repository)
    return TestClient(app)


def test_get_profile_returns_defaults_for_an_unknown_user(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    repository = FakeDigitalTwinRepository()
    with _client(monkeypatch, repository) as client:
        user_id = uuid4()
        response = client.get("/v1/digital-twin/profile", params={"user_id": str(user_id)})
        assert response.status_code == 200
        body = response.json()
        assert body["verbosity"] == "moderate"
        assert body["source"] == "static_default"


def test_patch_profile_applies_a_direct_user_override_and_records_history(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    repository = FakeDigitalTwinRepository()
    with _client(monkeypatch, repository) as client:
        user_id = uuid4()
        response = client.patch(
            "/v1/digital-twin/profile",
            params={"user_id": str(user_id)},
            json={"verbosity": "concise"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["verbosity"] == "concise"
        assert body["source"] == "learned"

        assert len(repository.evolution_entries) == 1
        entry = repository.evolution_entries[0]
        assert entry.field == "verbosity"
        assert entry.previous_value == "moderate"
        assert entry.new_value == "concise"
        assert entry.source == "user_override"
        assert entry.confidence == 1.0


def test_patch_profile_with_no_actual_change_writes_no_history(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    repository = FakeDigitalTwinRepository()
    with _client(monkeypatch, repository) as client:
        user_id = uuid4()
        response = client.patch(
            "/v1/digital-twin/profile",
            params={"user_id": str(user_id)},
            json={"verbosity": "moderate"},  # already the default
        )
        assert response.status_code == 200
        assert repository.evolution_entries == []


def test_reset_restores_defaults(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    repository = FakeDigitalTwinRepository()
    with _client(monkeypatch, repository) as client:
        user_id = uuid4()
        client.patch(
            "/v1/digital-twin/profile",
            params={"user_id": str(user_id)},
            json={"verbosity": "concise"},
        )
        response = client.post("/v1/digital-twin/reset", params={"user_id": str(user_id)})
        assert response.status_code == 200
        body = response.json()
        assert body["verbosity"] == "moderate"
        assert body["source"] == "static_default"
        # The audit trail from the earlier PATCH is not deleted.
        assert len(repository.evolution_entries) == 1
