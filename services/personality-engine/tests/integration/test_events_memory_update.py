"""A real Event Bus round-trip through `events/handlers.py::
make_memory_update_handler` (docs/design/phase-2d/02-personality-engine.md
Sec7.2, Sec10; docs/design/phase-2d/06-personal-companion.md Sec7.1) --
verifies the `personality.memory.update` subscription registered by
`create_app` actually persists via `PersonalityRepository.
update_memory_profile` and refreshes `app.state.memory_profile` so the
very next `select_style` call sees it, without an extra database read on
that hot path.
"""

from __future__ import annotations

from uuid import uuid4

from nova_contracts import (
    EventEnvelope,
    PersonalityMemoryUpdatePayload,
    PersonalityStyleSelectReplyPayload,
    PersonalityStyleSelectRequestPayload,
)
from nova_eventbus_sdk import BoundEventBus
from nova_personality_engine.config import Settings
from nova_personality_engine.domain.models import MemoryProfile
from nova_personality_engine.main import create_app

from tests.fakes.repository import FakePersonalityRepository


async def _publish_memory_update(app, payload: PersonalityMemoryUpdatePayload) -> None:  # type: ignore[no-untyped-def]
    # personality-engine's own bus has no publish permission for this
    # subject (it only ever subscribes) -- a second `BoundEventBus`, wrapping
    # the same underlying in-memory broker, stands in for the real publisher
    # (digital-twin-engine), mirroring `test_events_personality_request.py`'s
    # own "second bus as external caller" convention.
    publisher_bus = BoundEventBus(
        app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
        engine_name="digital-twin-engine",
        publishable_subjects=frozenset({"personality.memory.update"}),
        subscribable_subjects=frozenset(),
    )
    envelope = EventEnvelope(
        subject="personality.memory.update",
        source_engine="digital-twin-engine",
        correlation_id=uuid4(),
        payload=payload.model_dump(mode="json"),
    )
    await publisher_bus.publish(envelope)


async def test_a_published_update_persists_and_refreshes_the_cached_profile(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakePersonalityRepository()
    app = create_app(Settings(), repository=repository)

    async with app.router.lifespan_context(app):
        assert app.state.memory_profile.verbosity == "moderate"

        await _publish_memory_update(app, PersonalityMemoryUpdatePayload(verbosity="concise"))

        assert app.state.memory_profile.verbosity == "concise"
        assert app.state.memory_profile.source == "digital_twin"
        assert repository.memory_profile.verbosity == "concise"


async def test_an_update_naming_only_one_field_leaves_the_others_unchanged(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakePersonalityRepository(
        memory_profile=MemoryProfile(
            verbosity="moderate", technical_depth="expert", source="static_default"
        )
    )
    app = create_app(Settings(), repository=repository)

    async with app.router.lifespan_context(app):
        await _publish_memory_update(app, PersonalityMemoryUpdatePayload(verbosity="concise"))

        assert app.state.memory_profile.verbosity == "concise"
        assert app.state.memory_profile.technical_depth == "expert"  # untouched


async def test_the_next_style_select_call_reflects_the_update(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """The hot path (Sec8, Sec12) reads `app.state.memory_profile` only --
    this confirms the refresh actually reaches that read, not just the
    repository."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings(), repository=FakePersonalityRepository())

    async with app.router.lifespan_context(app):
        await _publish_memory_update(app, PersonalityMemoryUpdatePayload(verbosity="concise"))

        caller_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
            engine_name="test-caller-engine",
            publishable_subjects=frozenset({"personality.style.select.request"}),
            subscribable_subjects=frozenset(),
        )
        reply_envelope = await caller_bus.request(
            "personality.style.select.request",
            PersonalityStyleSelectRequestPayload(
                situation_hint=None,
                requesting_engine="test-caller-engine",
                correlation_id=uuid4(),
            ),
            source_engine="test-caller-engine",
        )
        reply = PersonalityStyleSelectReplyPayload.model_validate(reply_envelope.payload)
        assert reply.verbosity == "concise"
