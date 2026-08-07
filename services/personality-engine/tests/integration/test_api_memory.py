"""`GET /memory` (docs/design/phase-2d/02-personality-engine.md Sec11,
Sec6) -- read-only this phase (ADR-030)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from nova_personality_engine.config import Settings
from nova_personality_engine.domain.models import MemoryProfile
from nova_personality_engine.main import create_app

from tests.fakes.repository import FakePersonalityRepository


def test_memory_returns_the_resolved_profile(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(
        Settings(),
        repository=FakePersonalityRepository(
            memory_profile=MemoryProfile(
                verbosity="concise", technical_depth="deep", source="static_default"
            )
        ),
    )
    with TestClient(app) as client:
        response = client.get("/v1/personality/memory")

    assert response.status_code == 200
    body = response.json()
    assert body["verbosity"] == "concise"
    assert body["technical_depth"] == "deep"
    assert body["source"] == "static_default"
