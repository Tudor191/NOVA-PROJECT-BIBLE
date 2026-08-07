"""A real Event Bus round-trip through `events/handlers.py`'s served
`personality.validate_response.request` and `personality.style.select.
request` RPCs (docs/design/phase-2d/02-personality-engine.md Sec7.1, Sec10)
-- every other test exercises this engine's validator/selector only via the
HTTP path; this is the one place the handlers themselves, registered by
`create_app`'s `bus.serve(...)` calls, are actually invoked through a
subscription rather than called as a bare Python function.

`app.state.bus` is this engine's own `BoundEventBus`, whose
`publishable_subjects` (`events/published.py`) is empty by design -- this
engine only ever *serves* these two subjects, never calls them on itself. A
second `BoundEventBus`, wrapping the exact same underlying in-memory bus
instance, stands in for the kind of external caller (`communication-engine`)
whose own `published.py` would legitimately list them.
"""

from __future__ import annotations

from uuid import uuid4

from nova_contracts import (
    PersonalityStyleSelectReplyPayload,
    PersonalityStyleSelectRequestPayload,
    PersonalityValidateResponseReplyPayload,
    PersonalityValidateResponseRequestPayload,
)
from nova_eventbus_sdk import BoundEventBus
from nova_personality_engine.config import Settings
from nova_personality_engine.main import create_app

from tests.fakes.repository import FakePersonalityRepository


async def test_validate_response_rpc_round_trips_through_the_real_event_bus(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakePersonalityRepository()
    app = create_app(Settings(), repository=repository)

    async with app.router.lifespan_context(app):
        caller_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
            engine_name="test-caller-engine",
            publishable_subjects=frozenset(
                {"personality.validate_response.request", "personality.style.select.request"}
            ),
            subscribable_subjects=frozenset(),
        )
        correlation_id = uuid4()
        reply_envelope = await caller_bus.request(
            "personality.validate_response.request",
            PersonalityValidateResponseRequestPayload(
                content="The build finished successfully.",
                confidence_tier="high",
                session_id=uuid4(),
                requesting_engine="test-caller-engine",
                correlation_id=correlation_id,
            ),
            source_engine="test-caller-engine",
        )
        reply = PersonalityValidateResponseReplyPayload.model_validate(reply_envelope.payload)
        assert reply.passed is True
        assert repository.audit_records  # the handler actually ran, not a stub reply


async def test_style_select_rpc_round_trips_through_the_real_event_bus(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings(), repository=FakePersonalityRepository())

    async with app.router.lifespan_context(app):
        caller_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
            engine_name="test-caller-engine",
            publishable_subjects=frozenset(
                {"personality.validate_response.request", "personality.style.select.request"}
            ),
            subscribable_subjects=frozenset(),
        )
        reply_envelope = await caller_bus.request(
            "personality.style.select.request",
            PersonalityStyleSelectRequestPayload(
                situation_hint="debugging",
                requesting_engine="test-caller-engine",
                correlation_id=uuid4(),
            ),
            source_engine="test-caller-engine",
        )
        reply = PersonalityStyleSelectReplyPayload.model_validate(reply_envelope.payload)
        assert reply.style == "analytical"
