"""`clients.communication_client.CommunicationClient` (TDD 3C §5, Fork D
precedent) -- a real Event Bus round trip through
`communication.session.lookup_by_user.request` and
`communication.intent.deliver.request`, mirroring `digital-twin-engine`'s
own `test_communication_client.py` convention: an in-process stand-in for
`communication-engine`'s own network position *serves* both requests for
real over the in-memory Event Bus, and this engine's own (non-fake)
`CommunicationClient`, constructed by `create_app` with no override, calls
them directly -- the wire contract itself is exercised, not bypassed by
dependency injection.

`Settings()` defaults `primary_user_id` to `None`, so `create_app`'s own
lifespan bootstrap-install loop never attempts a disclosure call itself
(Permission Review is skipped for every built-in) -- this test instead
calls `app.state.communication_port`'s methods directly, exactly as
`digital-twin-engine`'s own test does."""

from __future__ import annotations

from uuid import uuid4

from nova_capability_engine.config import Settings
from nova_capability_engine.main import create_app
from nova_contracts import (
    CommunicationIntentDeliverReplyPayload,
    CommunicationIntentDeliverRequestPayload,
    CommunicationSessionLookupByUserReplyPayload,
    CommunicationSessionLookupByUserRequestPayload,
)
from nova_eventbus_sdk import BoundEventBus

from tests.fakes.repository import FakeCapabilityRepository


async def test_a_real_get_connected_session_call_reaches_a_real_lookup_rpc_round_trip(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings(), repository=FakeCapabilityRepository())

    async with app.router.lifespan_context(app):
        received_requests: list[CommunicationSessionLookupByUserRequestPayload] = []
        expected_session_id = uuid4()

        communication_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
            engine_name="communication-engine",
            publishable_subjects=frozenset(),
            subscribable_subjects=frozenset(
                {
                    "communication.session.lookup_by_user.request",
                    "communication.intent.deliver.request",
                }
            ),
        )

        async def _serve_lookup(envelope):  # type: ignore[no-untyped-def]
            payload = CommunicationSessionLookupByUserRequestPayload.model_validate(
                envelope.payload
            )
            received_requests.append(payload)
            return CommunicationSessionLookupByUserReplyPayload(
                user_id=payload.user_id, session_id=expected_session_id
            )

        await communication_bus.serve(
            "communication.session.lookup_by_user.request",
            _serve_lookup,
            source_engine="communication-engine",
        )

        user_id = uuid4()
        result = await app.state.communication_port.get_connected_session(user_id=user_id)

        assert result == expected_session_id
        assert len(received_requests) == 1
        assert received_requests[0].user_id == user_id


async def test_a_real_deliver_intent_call_reaches_a_real_intent_deliver_rpc_round_trip(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings(), repository=FakeCapabilityRepository())

    async with app.router.lifespan_context(app):
        received_requests: list[CommunicationIntentDeliverRequestPayload] = []

        communication_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
            engine_name="communication-engine",
            publishable_subjects=frozenset(),
            subscribable_subjects=frozenset(
                {
                    "communication.session.lookup_by_user.request",
                    "communication.intent.deliver.request",
                }
            ),
        )

        async def _serve_deliver(envelope):  # type: ignore[no-untyped-def]
            payload = CommunicationIntentDeliverRequestPayload.model_validate(envelope.payload)
            received_requests.append(payload)
            return CommunicationIntentDeliverReplyPayload(
                delivered=True, personality_validated=True
            )

        await communication_bus.serve(
            "communication.intent.deliver.request",
            _serve_deliver,
            source_engine="communication-engine",
        )

        session_id = uuid4()
        result = await app.state.communication_port.deliver_intent(
            session_id=session_id, content="New capability installed: 'filesystem'."
        )

        assert result is True
        assert len(received_requests) == 1
        assert received_requests[0].session_id == session_id
        assert received_requests[0].content == "New capability installed: 'filesystem'."
        assert received_requests[0].requesting_engine == "capability-engine"
