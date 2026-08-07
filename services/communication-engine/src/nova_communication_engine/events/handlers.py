"""`communication.intent.deliver.request`, `communication.session.create.
request`, and `communication.session.close.request` served RPC handlers
(docs/design/phase-2d/01-communication-engine.md Sec7, Sec8.2, Sec11, Sec12)
-- the Event Bus counterparts to the `api/sessions.py` HTTP endpoints, and
the one path any content-source engine (Reasoning Engine, and later
Planning/agents) actually uses to reach the `communication.intent` gate.
"""

from __future__ import annotations

import contextlib

from fastapi import FastAPI
from nova_contracts import (
    CommunicationIntentDeliverReplyPayload,
    CommunicationIntentDeliverRequestPayload,
    CommunicationSessionCloseReplyPayload,
    CommunicationSessionCloseRequestPayload,
    CommunicationSessionCreateReplyPayload,
    CommunicationSessionCreateRequestPayload,
    EventEnvelope,
)

from nova_communication_engine.domain import session_lifecycle
from nova_communication_engine.domain.intent_gate import deliver_intent
from nova_communication_engine.domain.state_machine import InvalidTransitionError

__all__ = [
    "make_intent_deliver_handler",
    "make_session_close_handler",
    "make_session_create_handler",
]


def make_intent_deliver_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> CommunicationIntentDeliverReplyPayload:
        state = app.state
        payload = CommunicationIntentDeliverRequestPayload.model_validate(envelope.payload)

        session = await state.repository.get_session(payload.session_id)
        if session is None:
            return CommunicationIntentDeliverReplyPayload(
                delivered=False, personality_validated=False, rejection_reason="session_not_found"
            )

        try:
            session = await session_lifecycle.mark_content_ready(
                session=session, repository=state.repository, correlation_id=payload.correlation_id
            )
        except InvalidTransitionError as exc:
            return CommunicationIntentDeliverReplyPayload(
                delivered=False,
                personality_validated=False,
                rejection_reason=f"invalid_session_state: {exc}",
            )

        adapter = state.session_registry.get_adapter(session.session_id)
        barge_in_signal = state.session_registry.get_barge_in_signal(session.session_id)

        outcome = await deliver_intent(
            session=session,
            content=payload.content,
            confidence_tier=payload.confidence_tier,
            channel_adapter=adapter,
            personality_port=state.personality_port,
            model_orchestration_port=state.model_orchestration_port,
            repository=state.repository,
            barge_in_signal=barge_in_signal,
            correlation_id=payload.correlation_id,
        )

        if outcome.rejection_reason != "barged_in":
            # A rejected or failed delivery still transitions Speaking ->
            # Waiting (design doc Sec3.1 defines no recovery edge for a
            # failed delivery) -- the alternative, a session stuck in
            # Speaking forever, would be a materially worse defect. The
            # "barged_in" case is excluded: `api/websocket.py`'s concurrent
            # audio-chunk handler already transitioned Speaking -> Listening
            # by the time this RPC returns.
            with contextlib.suppress(InvalidTransitionError):
                await session_lifecycle.mark_delivered(
                    session=session,
                    repository=state.repository,
                    correlation_id=payload.correlation_id,
                )

        state.metrics.intent_deliveries_total.add(
            1, {"outcome": "delivered" if outcome.delivered else "rejected"}
        )
        if outcome.degraded:
            state.metrics.personality_rpc_degraded_total.add(1)
        if outcome.rejection_reason == "barged_in":
            state.metrics.barge_ins_total.add(1)

        return CommunicationIntentDeliverReplyPayload(
            delivered=outcome.delivered,
            personality_validated=outcome.personality_validated,
            degraded=outcome.degraded,
            turn_id=outcome.turn_id,
            rejection_reason=outcome.rejection_reason,
        )

    return handle


def make_session_create_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> CommunicationSessionCreateReplyPayload:
        state = app.state
        payload = CommunicationSessionCreateRequestPayload.model_validate(envelope.payload)
        session = await session_lifecycle.create_session(
            user_id=payload.user_id,
            channel=payload.channel,
            device_id=payload.device_id,
            repository=state.repository,
            world_model_port=state.world_model_port,
            correlation_id=payload.correlation_id,
        )
        return CommunicationSessionCreateReplyPayload(
            session_id=session.session_id, state=session.state, created_at=session.created_at
        )

    return handle


def make_session_close_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> CommunicationSessionCloseReplyPayload:
        state = app.state
        payload = CommunicationSessionCloseRequestPayload.model_validate(envelope.payload)
        session = await state.repository.get_session(payload.session_id)
        if session is None:
            raise ValueError(f"Session {payload.session_id} not found.")
        updated = await session_lifecycle.close_session(
            session=session, repository=state.repository, correlation_id=payload.correlation_id
        )
        state.session_registry.unregister(payload.session_id)
        assert updated.closed_at is not None
        return CommunicationSessionCloseReplyPayload(
            session_id=updated.session_id, state=updated.state, closed_at=updated.closed_at
        )

    return handle
