"""`clients.communication_client.CommunicationClient` (TDD 3D §4, Fork D
precedent) -- a real Event Bus round trip through
`communication.session.lookup_by_user.request` and
`communication.intent.deliver.request`, mirroring `capability-engine`'s own
`test_communication_client.py` convention exactly."""

from __future__ import annotations

from uuid import uuid4

from nova_action_engine.config import Settings
from nova_action_engine.main import create_app
from nova_contracts import (
    CommunicationIntentDeliverReplyPayload,
    CommunicationIntentDeliverRequestPayload,
    CommunicationSessionLookupByUserReplyPayload,
    CommunicationSessionLookupByUserRequestPayload,
)
from nova_eventbus_sdk import BoundEventBus

from tests.fakes.capability_port import FakeCapabilityPort
from tests.fakes.identity_port import FakeIdentityPort
from tests.fakes.repository import FakeActionRepository


def _harness_app():  # type: ignore[no-untyped-def]
    return create_app(
        Settings(),
        repository=FakeActionRepository(),
        capability_port=FakeCapabilityPort(),
        identity_port=FakeIdentityPort(),
    )


async def test_a_real_get_connected_session_call_reaches_a_real_lookup_rpc_round_trip(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = _harness_app()

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
    app = _harness_app()

    async with app.router.lifespan_context(app):
        received_requests: list[CommunicationIntentDeliverRequestPayload] = []

        communication_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001
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
            session_id=session_id, content="Approval required: filesystem action."
        )

        assert result is True
        assert len(received_requests) == 1
        assert received_requests[0].session_id == session_id
        assert received_requests[0].requesting_engine == "action-engine"
