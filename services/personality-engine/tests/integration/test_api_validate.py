"""`POST /validate` (docs/design/phase-2d/02-personality-engine.md Sec11,
Sec4, Sec8) -- every hard-stop/soft-correction path, plus the audit trail
Sec9/Doc 23 Sec8 requires."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from nova_personality_engine.config import Settings
from nova_personality_engine.main import create_app

from tests.fakes.repository import FakePersonalityRepository


def _harness(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakePersonalityRepository()
    app = create_app(Settings(), repository=repository)
    return app, repository


def test_validate_passes_clean_content_unmodified(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    app, repository = _harness(monkeypatch)
    with TestClient(app) as client:
        response = client.post(
            "/validate",
            json={
                "content": "The build finished successfully.",
                "confidence_tier": "high",
                "session_id": str(uuid4()),
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is True
    assert body["adjusted_content"] is None
    assert body["violations"] == []
    assert len(repository.audit_records) == 1


def test_validate_hedges_overclaiming_language_under_low_confidence(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    app, _ = _harness(monkeypatch)
    with TestClient(app) as client:
        response = client.post(
            "/validate",
            json={
                "content": "This will definitely work.",
                "confidence_tier": "low",
                "session_id": str(uuid4()),
            },
        )

    body = response.json()
    assert body["passed"] is True
    assert body["adjusted_content"] is not None
    assert body["adjusted_content"] != "This will definitely work."
    assert body["violations"][0]["check_family"] == "confidence_language"


def test_validate_hard_stops_on_a_forbidden_pattern(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    app, repository = _harness(monkeypatch)
    with TestClient(app) as client:
        response = client.post(
            "/validate",
            json={
                "content": "Act now, don't wait, before it's too late.",
                "confidence_tier": "unknown",
                "session_id": str(uuid4()),
            },
        )

    body = response.json()
    assert body["passed"] is False
    assert body["adjusted_content"] is None
    assert body["violations"][0]["check_family"] == "forbidden_pattern"
    assert repository.audit_records[0][1].passed is False


def test_validate_hard_stops_on_emotional_instability(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    app, _ = _harness(monkeypatch)
    with TestClient(app) as client:
        response = client.post(
            "/validate",
            json={
                "content": "That's not my fault, I never said that.",
                "confidence_tier": "unknown",
                "session_id": str(uuid4()),
            },
        )

    body = response.json()
    assert body["passed"] is False
    assert body["violations"][0]["check_family"] == "emotional_stability"


def test_validate_corrects_shouted_formatting(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    app, _ = _harness(monkeypatch)
    with TestClient(app) as client:
        response = client.post(
            "/validate",
            json={
                "content": "This is REALLY IMPORTANT!!!",
                "confidence_tier": "high",
                "session_id": str(uuid4()),
            },
        )

    body = response.json()
    assert body["passed"] is True
    assert body["adjusted_content"] is not None
    assert "!!!" not in body["adjusted_content"]
    assert body["violations"][0]["check_family"] == "professionalism_floor"


def test_validate_returns_503_when_core_identity_is_not_loaded(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings(), repository=FakePersonalityRepository(core_identity=None))
    with TestClient(app) as client:
        response = client.post(
            "/validate",
            json={
                "content": "Hello.",
                "confidence_tier": "high",
                "session_id": str(uuid4()),
            },
        )

    assert response.status_code == 503
