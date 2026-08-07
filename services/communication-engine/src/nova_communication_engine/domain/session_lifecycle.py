"""Session creation/close/pause/resume and inbound-turn recording -- the real
(non-pass-through) halves of design doc Sec6's Communication Lifecycle:
Receive, Retrieve Context (session-creation-time only, Sec8.7), Determine
Intent's *publishing* half (Sec6's table: "every inbound message becomes a
`communication.turn.received` event"), and Choose Communication Channel
(trivial -- same channel the turn arrived on, already on the session).

Every state transition publishes `communication.session.state_changed`
(design doc Sec11) -- the Live Communication Dashboard's data source, so it
is emitted on every transition this module makes, not only create/close.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from nova_contracts.events.communication import (
    CommunicationSessionCompletedPayload,
    CommunicationSessionCreatedPayload,
    CommunicationSessionStateChangedPayload,
    CommunicationTurnReceivedPayload,
)

from nova_communication_engine.domain.models import (
    ChannelType,
    ConversationSession,
    ConversationState,
    ConversationTurn,
    TurnDirection,
)
from nova_communication_engine.domain.ports import (
    CommunicationRepository,
    OutboxEvent,
    WorldModelPort,
)
from nova_communication_engine.domain.state_machine import ConversationEvent, transition

__all__ = [
    "InvalidCloseStateError",
    "close_session",
    "create_session",
    "pause_session",
    "recover_session_to_paused",
    "record_inbound_turn",
    "resume_session",
]


async def _apply_transition(
    *,
    session: ConversationSession,
    event: ConversationEvent,
    repository: CommunicationRepository,
    correlation_id: UUID,
    closed_at: datetime | None = None,
) -> ConversationSession:
    from_state = session.state
    to_state = transition(from_state, event)
    outbox_event = OutboxEvent(
        subject="communication.session.state_changed",
        payload=CommunicationSessionStateChangedPayload(
            session_id=session.session_id,
            from_state=from_state,
            to_state=to_state,
            changed_at=datetime.now(UTC),
        ).model_dump(mode="json"),
        correlation_id=correlation_id,
    )
    updated = await repository.update_session_state(
        session.session_id, state=to_state.value, closed_at=closed_at, outbox_event=outbox_event
    )
    return updated


async def create_session(
    *,
    user_id: UUID,
    channel: ChannelType,
    device_id: UUID,
    repository: CommunicationRepository,
    world_model_port: WorldModelPort,
    correlation_id: UUID,
) -> ConversationSession:
    """Design doc Sec8.7 -- one World Model context call, at session
    creation only (never per turn)."""
    snapshot = await world_model_port.get_context(user_id=user_id, correlation_id=correlation_id)
    session = ConversationSession(
        user_id=user_id,
        channel=channel,
        device_id=device_id,
        state=ConversationState.IDLE,
        objective=snapshot.objective if snapshot is not None else None,
    )
    created = await repository.create_session(session)
    await repository.enqueue_outbox(
        OutboxEvent(
            subject="communication.session.created",
            payload=CommunicationSessionCreatedPayload(
                session_id=created.session_id,
                user_id=created.user_id,
                channel=created.channel,
                device_id=created.device_id,
                created_at=created.created_at,
            ).model_dump(mode="json"),
            correlation_id=correlation_id,
        )
    )
    return created


async def record_inbound_turn(
    *,
    session: ConversationSession,
    content: str,
    repository: CommunicationRepository,
    correlation_id: UUID,
) -> tuple[ConversationSession, ConversationTurn]:
    """Design doc Sec0.4's explicit trigger + Sec6's "Determine Intent"
    pass-through: `Idle`/`Waiting` -> `Listening` (the trigger) ->
    `Thinking` (content already captured by the time this is called),
    publishing `communication.turn.received` for Reasoning Engine."""
    session = await _apply_transition(
        session=session,
        event=ConversationEvent.TRIGGER,
        repository=repository,
        correlation_id=correlation_id,
    )
    session = await _apply_transition(
        session=session,
        event=ConversationEvent.CAPTURED,
        repository=repository,
        correlation_id=correlation_id,
    )

    turn = ConversationTurn(
        session_id=session.session_id,
        direction=TurnDirection.INBOUND,
        content=content,
        channel=session.channel,
    )
    outbox_event = OutboxEvent(
        subject="communication.turn.received",
        payload=CommunicationTurnReceivedPayload(
            session_id=session.session_id,
            turn_id=turn.turn_id,
            user_id=session.user_id,
            content=content,
            channel=session.channel,
            created_at=turn.created_at,
        ).model_dump(mode="json"),
        correlation_id=correlation_id,
    )
    saved_turn = await repository.append_turn(turn, outbox_event=outbox_event)
    return session, saved_turn


async def mark_content_ready(
    *, session: ConversationSession, repository: CommunicationRepository, correlation_id: UUID
) -> ConversationSession:
    """`Thinking -> Speaking` -- called once the intent gate (Sec7) has a
    validated response ready to deliver."""
    return await _apply_transition(
        session=session,
        event=ConversationEvent.CONTENT_READY,
        repository=repository,
        correlation_id=correlation_id,
    )


async def mark_delivered(
    *, session: ConversationSession, repository: CommunicationRepository, correlation_id: UUID
) -> ConversationSession:
    """`Speaking -> Waiting` -- called once the intent gate has delivered
    the response to the Channel Adapter."""
    return await _apply_transition(
        session=session,
        event=ConversationEvent.DELIVERED,
        repository=repository,
        correlation_id=correlation_id,
    )


async def mark_barge_in(
    *, session: ConversationSession, repository: CommunicationRepository, correlation_id: UUID
) -> ConversationSession:
    """`Speaking -> Listening` -- design doc Sec4's unconditional barge-in
    stop (Master Blueprint Sec13.4)."""
    return await _apply_transition(
        session=session,
        event=ConversationEvent.BARGE_IN,
        repository=repository,
        correlation_id=correlation_id,
    )


class InvalidCloseStateError(ValueError):
    """Design doc Sec3.1's diagram defines exactly one close edge,
    `Waiting -> Completed` -- closing from any other state is not a
    documented transition this phase. Forcing close from an arbitrary state
    is a reasonable future extension, not implemented here without a
    documented transition to implement it against."""


async def close_session(
    *, session: ConversationSession, repository: CommunicationRepository, correlation_id: UUID
) -> ConversationSession:
    if session.state is not ConversationState.WAITING:
        raise InvalidCloseStateError(
            f"Cannot close session {session.session_id} from state "
            f"{session.state.value!r}; only {ConversationState.WAITING.value!r} "
            "sessions can close (design doc Sec3.1)."
        )
    closed_at = datetime.now(UTC)
    updated = await _apply_transition(
        session=session,
        event=ConversationEvent.CLOSE,
        repository=repository,
        correlation_id=correlation_id,
        closed_at=closed_at,
    )
    await repository.enqueue_outbox(
        OutboxEvent(
            subject="communication.session.completed",
            payload=CommunicationSessionCompletedPayload(
                session_id=updated.session_id,
                user_id=updated.user_id,
                objective=updated.objective,
                turn_count=len(updated.turns),
                closed_at=closed_at,
            ).model_dump(mode="json"),
            correlation_id=correlation_id,
        )
    )
    return updated


async def pause_session(
    *, session: ConversationSession, repository: CommunicationRepository, correlation_id: UUID
) -> ConversationSession:
    return await _apply_transition(
        session=session,
        event=ConversationEvent.PAUSE,
        repository=repository,
        correlation_id=correlation_id,
    )


async def recover_session_to_paused(
    *, session: ConversationSession, repository: CommunicationRepository, correlation_id: UUID
) -> ConversationSession:
    """Design doc Sec3.5's restart recovery -- a direct write, not FSM-
    validated through `state_machine.transition()`: every non-terminal
    session becomes `Paused` after a process restart, regardless of which
    state it was in when the process stopped, since no channel connection
    can possibly be live yet at this point in startup. Still publishes
    `communication.session.state_changed` -- the Dashboard's data source
    must reflect this transition too, even though it was not triggered by
    a live `ConversationEvent`."""
    if session.state is ConversationState.PAUSED:
        return session
    outbox_event = OutboxEvent(
        subject="communication.session.state_changed",
        payload=CommunicationSessionStateChangedPayload(
            session_id=session.session_id,
            from_state=session.state,
            to_state=ConversationState.PAUSED,
            changed_at=datetime.now(UTC),
        ).model_dump(mode="json"),
        correlation_id=correlation_id,
    )
    return await repository.update_session_state(
        session.session_id, state=ConversationState.PAUSED.value, outbox_event=outbox_event
    )


async def resume_session(
    *, session: ConversationSession, repository: CommunicationRepository, correlation_id: UUID
) -> ConversationSession:
    return await _apply_transition(
        session=session,
        event=ConversationEvent.RESUME,
        repository=repository,
        correlation_id=correlation_id,
    )
