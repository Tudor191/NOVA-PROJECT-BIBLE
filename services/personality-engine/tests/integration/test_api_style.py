"""`GET /style` (docs/design/phase-2d/02-personality-engine.md Sec11,
Sec5)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from nova_personality_engine.config import Settings
from nova_personality_engine.main import create_app

from tests.fakes.repository import FakePersonalityRepository


@pytest.fixture
def client(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings(), repository=FakePersonalityRepository())
    with TestClient(app) as test_client:
        yield test_client


def test_style_defaults_to_professional_with_no_hint(client) -> None:  # type: ignore[no-untyped-def]
    response = client.get("/v1/personality/style")
    assert response.status_code == 200
    assert response.json()["style"] == "professional"


@pytest.mark.parametrize(
    ("situation_hint", "expected_style"),
    [
        ("debugging", "analytical"),
        ("learning_session", "educational"),
        ("emergency", "emergency"),
        ("executive_meeting", "executive"),
        ("brainstorming", "creative"),
        ("quick_check", "minimal"),
        ("casual", "friendly"),
        ("technical_review", "technical"),
        ("unrecognized_hint", "professional"),
    ],
)
def test_style_maps_every_situation_hint(client, situation_hint, expected_style) -> None:  # type: ignore[no-untyped-def]
    response = client.get("/v1/personality/style", params={"situation_hint": situation_hint})
    assert response.status_code == 200
    assert response.json()["style"] == expected_style


def test_style_returns_503_when_core_identity_is_not_loaded(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings(), repository=FakePersonalityRepository(core_identity=None))
    with TestClient(app) as test_client:
        response = test_client.get("/v1/personality/style")

    assert response.status_code == 503
