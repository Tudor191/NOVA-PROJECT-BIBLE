"""`GET /identity` and `GET /identity/snapshot` (docs/design/phase-2d/
02-personality-engine.md Sec11)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from nova_personality_engine.config import Settings
from nova_personality_engine.domain.models import MemoryProfile
from nova_personality_engine.main import create_app

from tests.fakes.repository import FakePersonalityRepository


def test_identity_returns_the_loaded_core_identity(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings(), repository=FakePersonalityRepository())
    with TestClient(app) as client:
        response = client.get("/identity")

    assert response.status_code == 200
    body = response.json()
    assert "calm" in body["traits"]
    assert "Trust Before Intelligence" in body["values"]


def test_identity_returns_503_when_core_identity_is_not_loaded(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings(), repository=FakePersonalityRepository(core_identity=None))
    with TestClient(app) as client:
        response = client.get("/identity")

    assert response.status_code == 503


def test_identity_snapshot_reflects_the_default_style_and_memory_profile(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(
        Settings(),
        repository=FakePersonalityRepository(
            memory_profile=MemoryProfile(verbosity="concise", technical_depth="deep")
        ),
    )
    with TestClient(app) as client:
        response = client.get("/identity/snapshot")

    assert response.status_code == 200
    body = response.json()
    assert body["default_style"] == "professional"
    assert body["verbosity"] == "concise"
    assert body["technical_depth"] == "deep"


def test_identity_snapshot_returns_503_when_core_identity_is_not_loaded(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings(), repository=FakePersonalityRepository(core_identity=None))
    with TestClient(app) as client:
        response = client.get("/identity/snapshot")

    assert response.status_code == 503
