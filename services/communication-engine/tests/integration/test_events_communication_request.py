"""A real Event Bus round-trip through `events/handlers.py`'s four served
RPCs (docs/design/phase-2d/01-communication-engine.md Sec11;
docs/design/phase-2d/06-personal-companion.md Sec10.2, Fork D adds the
fourth, `communication.session.lookup_by_user.request`) -- every other
test exercises this engine's session/intent logic only via the HTTP path;
this is the one place the handlers themselves, registered by `create_app`'s
`bus.serve(...)` calls, are actually invoked through a subscription rather
than called as a bare Python function.
"""

from __future__ import annotations

from uuid import uuid4

from nova_communication_engine.config import Settings
from nova_communication_engine.domain.models import ChannelType, ConversationState
from nova_communication_engine.main import create_app
from nova_contracts import (
    CommunicationIntentDeliverReplyPayload,
    CommunicationIntentDeliverRequestPayload,
    CommunicationSessionCloseReplyPayload,
    CommunicationSessionCloseRequestPayload,
    CommunicationSessionCreateReplyPayload,
    CommunicationSessionCreateRequestPayload,
    CommunicationSessionLookupByUserReplyPayload,
    CommunicationSessionLookupByUserRequestPayload,
)
from nova_eventbus_sdk import BoundEventBus

from tests.fakes.channel_adapter import FakeChannelAdapter
from tests.fakes.ports import (
    FakeModelOrchestrationPort,
    FakePersonalityPort,
    FakeReasoningPort,
    FakeWorldModelPort,
)
from tests.fakes.repository import FakeCommunicationRepository


async def test_session_create_and_intent_deliver_round_trip_through_the_real_event_bus(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCommunicationRepository()
    app = create_app(
        Settings(),
        repository=repository,
        personality_port=FakePersonalityPort(),
        model_orchestration_port=FakeModelOrchestrationPort(),
        world_model_port=FakeWorldModelPort(),
        reasoning_port=FakeReasoningPort(),
    )

    async with app.router.lifespan_context(app):
        caller_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
            engine_name="reasoning-engine",
            publishable_subjects=frozenset(
                {
                    "communication.session.create.request",
                    "communication.intent.deliver.request",
                    "communication.session.close.request",
                }
            ),
            subscribable_subjects=frozenset(),
        )

        create_reply_envelope = await caller_bus.request(
            "communication.session.create.request",
            CommunicationSessionCreateRequestPayload(
                user_id=uuid4(),
                channel=ChannelType.TEXT,
                device_id=uuid4(),
                requesting_engine="ws-gateway",
            ),
            source_engine="reasoning-engine",
        )
        create_reply = CommunicationSessionCreateReplyPayload.model_validate(
            create_reply_envelope.payload
        )
        assert create_reply.state == ConversationState.IDLE
        session_id = create_reply.session_id

        # Force the session into Thinking (as if a turn had already been
        # recorded) -- this test exercises the intent-delivery RPC, not the
        # HTTP turn-recording path already covered by test_api_sessions.py.
        session = await repository.get_session(session_id)
        assert session is not None
        await repository.update_session_state(session_id, state=ConversationState.THINKING.value)

        deliver_reply_envelope = await caller_bus.request(
            "communication.intent.deliver.request",
            CommunicationIntentDeliverRequestPayload(
                session_id=session_id, content="Hello!", requesting_engine="reasoning-engine"
            ),
            source_engine="reasoning-engine",
        )
        deliver_reply = CommunicationIntentDeliverReplyPayload.model_validate(
            deliver_reply_envelope.payload
        )
        # No live socket is registered, but the session is `text`, so the
        # Event Bus carries it (`BusTextChannelAdapter`) and the gate reports
        # a real delivery. `delivered` asserts a channel accepted the
        # utterance -- not that a person saw it (ADR-005).
        assert deliver_reply.delivered is True
        assert deliver_reply.rejection_reason is None

        updated_session = await repository.get_session(session_id)
        assert updated_session is not None
        assert updated_session.state == ConversationState.WAITING

        close_reply_envelope = await caller_bus.request(
            "communication.session.close.request",
            CommunicationSessionCloseRequestPayload(
                session_id=session_id, requesting_engine="ws-gateway"
            ),
            source_engine="reasoning-engine",
        )
        close_reply = CommunicationSessionCloseReplyPayload.model_validate(
            close_reply_envelope.payload
        )
        assert close_reply.state == ConversationState.COMPLETED


async def test_session_lookup_by_user_finds_a_connected_session(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(
        Settings(),
        repository=FakeCommunicationRepository(),
        personality_port=FakePersonalityPort(),
        model_orchestration_port=FakeModelOrchestrationPort(),
        world_model_port=FakeWorldModelPort(),
        reasoning_port=FakeReasoningPort(),
    )

    async with app.router.lifespan_context(app):
        user_id = uuid4()
        session_id = uuid4()
        app.state.session_registry.register(session_id, FakeChannelAdapter(), user_id=user_id)

        caller_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
            engine_name="digital-twin-engine",
            publishable_subjects=frozenset({"communication.session.lookup_by_user.request"}),
            subscribable_subjects=frozenset(),
        )
        reply_envelope = await caller_bus.request(
            "communication.session.lookup_by_user.request",
            CommunicationSessionLookupByUserRequestPayload(user_id=user_id),
            source_engine="digital-twin-engine",
        )
        reply = CommunicationSessionLookupByUserReplyPayload.model_validate(reply_envelope.payload)
        assert reply.session_id == session_id


async def test_session_lookup_by_user_returns_none_for_a_disconnected_user(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(
        Settings(),
        repository=FakeCommunicationRepository(),
        personality_port=FakePersonalityPort(),
        model_orchestration_port=FakeModelOrchestrationPort(),
        world_model_port=FakeWorldModelPort(),
        reasoning_port=FakeReasoningPort(),
    )

    async with app.router.lifespan_context(app):
        caller_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
            engine_name="digital-twin-engine",
            publishable_subjects=frozenset({"communication.session.lookup_by_user.request"}),
            subscribable_subjects=frozenset(),
        )
        reply_envelope = await caller_bus.request(
            "communication.session.lookup_by_user.request",
            CommunicationSessionLookupByUserRequestPayload(user_id=uuid4()),
            source_engine="digital-twin-engine",
        )
        reply = CommunicationSessionLookupByUserReplyPayload.model_validate(reply_envelope.payload)
        assert reply.session_id is None
