"""`digital_twin.preferences.get.request` served RPC handler
(`events/handlers.py::make_preferences_get_handler`) -- Fork A's field
split: serves only digital-twin-owned pacing/habit-timing fields, never
verbosity/technical_depth/terminology (docs/design/phase-2d/
06-personal-companion.md Sec8)."""

from __future__ import annotations

from uuid import uuid4

from nova_contracts import DigitalTwinPreferencesGetRequestPayload, EventEnvelope
from nova_digital_twin_engine.config import Settings
from nova_digital_twin_engine.domain.models import CommunicationProfile
from nova_digital_twin_engine.events.handlers import make_preferences_get_handler
from nova_digital_twin_engine.main import create_app

from tests.fakes.repository import FakeDigitalTwinRepository


def _envelope(user_id) -> EventEnvelope:  # type: ignore[no-untyped-def]
    payload = DigitalTwinPreferencesGetRequestPayload(user_id=user_id)
    return EventEnvelope(
        subject="digital_twin.preferences.get.request",
        source_engine="communication-engine",
        correlation_id=uuid4(),
        payload=payload.model_dump(mode="json"),
    )


async def test_returns_defaults_for_an_unknown_user(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeDigitalTwinRepository()
    app = create_app(Settings(), repository=repository)

    async with app.router.lifespan_context(app):
        user_id = uuid4()
        reply = await make_preferences_get_handler(app)(_envelope(user_id))

        assert reply.user_id == user_id
        assert reply.preferences == {"conversation_pacing": None, "habit_timing_hint": None}


async def test_returns_the_stored_pacing_and_habit_fields_only(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeDigitalTwinRepository()
    app = create_app(Settings(), repository=repository)

    async with app.router.lifespan_context(app):
        user_id = uuid4()
        repository.profiles[user_id] = CommunicationProfile(
            user_id=user_id,
            verbosity="concise",
            technical_depth="expert",
            conversation_pacing="slow",
            habit_timing_hint="mornings",
            source="learned",
        )

        reply = await make_preferences_get_handler(app)(_envelope(user_id))

        assert reply.preferences == {"conversation_pacing": "slow", "habit_timing_hint": "mornings"}
        assert "verbosity" not in reply.preferences
        assert "technical_depth" not in reply.preferences
