"""`communication.intent.deliver.request`, `communication.session.create.
request`, and `communication.session.close.request` served RPC handlers
(docs/design/phase-2d/01-communication-engine.md Sec7, Sec8.2, Sec11, Sec12)
-- the Event Bus counterparts to the `api/sessions.py` HTTP endpoints, and
the one path any content-source engine (Reasoning Engine, and later
Planning/agents) actually uses to reach the `communication.intent` gate.

`deliver_content_to_session` (below) is that same delivery logic, extracted
into a plain, directly-callable function so `conversation_orchestration.
handle_conversation_turn` (docs/design/phase-2d/
05-conversation-intelligence-closure.md Sec5.3, Priority 3) can reuse it
in-process, without a redundant Event-Bus round trip back to this same
engine's own served RPC for a call that never leaves this process. A pure
extraction: `make_intent_deliver_handler` now only parses the wire payload,
looks up the session, and maps the result back onto the reply contract --
the delivery behavior itself, and every existing test asserting it, is
unchanged.

`make_addressee_signal_handler` (docs/design/phase-2d/
04-conversation-intelligence.md Sec4/Sec10) is a genuine publish/subscribe
handler, not a served RPC -- it never returns a reply. It computes and
records every fusion decision, and -- since Phase 2D-C Closure Priority 4 --
also attempts to activate a live listening session on a `high` outcome, via
`conversation_orchestration.maybe_activate_listening`. That function is
imported inside `handle()` below, not at module scope: `conversation_
orchestration` itself imports `deliver_content_to_session` from this same
module, so a top-level import here would be circular.
"""

from __future__ import annotations

import contextlib
from uuid import UUID

from fastapi import FastAPI
from nova_contracts import (
    CommunicationIntentDeliverReplyPayload,
    CommunicationIntentDeliverRequestPayload,
    CommunicationSessionCloseReplyPayload,
    CommunicationSessionCloseRequestPayload,
    CommunicationSessionCreateReplyPayload,
    CommunicationSessionCreateRequestPayload,
    EventEnvelope,
    PerceptionAddresseeSignalCandidatePayload,
)
from nova_contracts.events.perception import GazeDirection

from nova_communication_engine.domain import clarification, conversation_memory, session_lifecycle
from nova_communication_engine.domain.addressee_fusion import (
    FusionSignals,
    confidence_tier_label,
    fuse,
)
from nova_communication_engine.domain.intent_gate import IntentDeliveryOutcome, deliver_intent
from nova_communication_engine.domain.models import ConversationDecisionTrace, ConversationSession
from nova_communication_engine.domain.state_machine import InvalidTransitionError

__all__ = [
    "deliver_content_to_session",
    "make_addressee_signal_handler",
    "make_intent_deliver_handler",
    "make_session_close_handler",
    "make_session_create_handler",
]


async def deliver_content_to_session(
    app: FastAPI,
    *,
    session: ConversationSession,
    content: str,
    correlation_id: UUID,
    confidence_tier: str = "unknown",
    memory_annotations: list[dict[str, str]] | None = None,
) -> IntentDeliveryOutcome:
    """The full Sec7/Sec9 delivery sequence any content-source engine's
    candidate utterance goes through, whether it arrives over the bus as
    `communication.intent.deliver.request` or, as of Priority 3, from this
    engine's own `conversation_orchestration` after a synchronous reasoning
    RPC returns: apply any memory annotations, transition the session
    `Thinking -> Speaking`, deliver through the intent gate, transition
    `Speaking -> Waiting`, offer an interruption resume if one was pending,
    and record metrics."""
    state = app.state

    # Sec9 (04-conversation-intelligence.md): store whatever this
    # content-source engine optionally categorized, before anything about
    # delivery itself is decided -- this engine never infers a category, it
    # only records what it's told.
    if memory_annotations:
        updated_memory = conversation_memory.apply_memory_annotations(
            session.conversation_memory, annotations=memory_annotations
        )
        session = await state.repository.update_conversation_memory(
            session.session_id, memory=updated_memory
        )

    pending_resume_offer = session.interrupted_content

    try:
        session = await session_lifecycle.mark_content_ready(
            session=session, repository=state.repository, correlation_id=correlation_id
        )
    except InvalidTransitionError as exc:
        return IntentDeliveryOutcome(
            delivered=False,
            personality_validated=False,
            rejection_reason=f"invalid_session_state: {exc}",
        )

    adapter = state.session_registry.get_adapter(session.session_id)
    barge_in_signal = state.session_registry.get_barge_in_signal(session.session_id)

    outcome = await deliver_intent(
        session=session,
        content=content,
        confidence_tier=confidence_tier,
        channel_adapter=adapter,
        personality_port=state.personality_port,
        model_orchestration_port=state.model_orchestration_port,
        repository=state.repository,
        barge_in_signal=barge_in_signal,
        correlation_id=correlation_id,
    )

    if outcome.rejection_reason != "barged_in":
        # A rejected or failed delivery still transitions Speaking ->
        # Waiting (design doc Sec3.1 defines no recovery edge for a failed
        # delivery) -- the alternative, a session stuck in Speaking forever,
        # would be a materially worse defect. The "barged_in" case is
        # excluded: `api/websocket.py`'s concurrent audio-chunk handler
        # already transitioned Speaking -> Listening by the time this
        # returns.
        with contextlib.suppress(InvalidTransitionError):
            await session_lifecycle.mark_delivered(
                session=session, repository=state.repository, correlation_id=correlation_id
            )
        if outcome.delivered and pending_resume_offer is not None:
            # Sec5.1/Sec6.2: the turn that interrupted a prior response has
            # now itself been answered -- offer to resume, reusing the
            # Clarification Engine's `pending_questions` field (Sec6.2's own
            # framing: a resume offer is structurally a pending question),
            # then clear the flag so it is offered exactly once.
            await state.repository.set_pending_questions(
                session.session_id,
                questions=[clarification.resume_offer(objective=session.objective)],
            )
            await state.repository.set_interrupted_content(session.session_id, content=None)

    state.metrics.intent_deliveries_total.add(
        1, {"outcome": "delivered" if outcome.delivered else "rejected"}
    )
    if outcome.degraded:
        state.metrics.personality_rpc_degraded_total.add(1)
    if outcome.rejection_reason == "barged_in":
        state.metrics.barge_ins_total.add(1)

    return outcome


def make_intent_deliver_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> CommunicationIntentDeliverReplyPayload:
        state = app.state
        payload = CommunicationIntentDeliverRequestPayload.model_validate(envelope.payload)

        session = await state.repository.get_session(payload.session_id)
        if session is None:
            return CommunicationIntentDeliverReplyPayload(
                delivered=False, personality_validated=False, rejection_reason="session_not_found"
            )

        outcome = await deliver_content_to_session(
            app,
            session=session,
            content=payload.content,
            confidence_tier=payload.confidence_tier,
            memory_annotations=payload.memory_annotations,
            correlation_id=payload.correlation_id,
        )

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


def make_addressee_signal_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    """Sec4/Sec10 -- consumes `perception.addressee_signal.candidate`,
    computes the fusion outcome, and records a `ConversationDecisionTrace`
    for every candidate signal (Sec15's observability requirement; Master
    Blueprint Risk Sec11.2's calibration-data collection). Since Phase 2D-C
    Closure Priority 4, a `tier == "high"` outcome (equivalently,
    `action == "activated"` -- `domain/addressee_fusion.py::fuse`'s single
    threshold branch makes the two checks equivalent by construction) also
    calls `maybe_activate_listening` to resolve `payload.user_id` to a live
    session and, if exactly one eligible one is connected, trigger it.
    World Model corroboration (`domain/addressee_fusion.py::
    corroborate_identity_confidence`) remains unwired here regardless: it
    needs an independent World Model call this handler does not make,
    unaffected by Priority 4's own, narrower use of `user_id` (session
    resolution only, not an identity-confidence claim -- see
    `PerceptionAddresseeSignalCandidatePayload`'s own docstring)."""

    async def handle(envelope: EventEnvelope) -> None:
        from nova_communication_engine.conversation_orchestration import (
            maybe_activate_listening,
        )

        state = app.state
        payload = PerceptionAddresseeSignalCandidatePayload.model_validate(envelope.payload)

        signals = FusionSignals(
            wake_word_matched=payload.wake_word_matched,
            wake_word_confidence=payload.wake_word_confidence,
            identity_id=payload.identity_id,
            identity_confidence=payload.identity_confidence,
            gaze_toward_device=payload.gaze_direction == GazeDirection.TOWARD_DEVICE,
            session_active=payload.session_active,
        )
        outcome = fuse(signals)

        await state.repository.create_decision_trace(
            ConversationDecisionTrace(
                session_id=None,
                decision_type="addressee_fusion",
                inputs=payload.model_dump(mode="json"),
                confidence=outcome.score,
                confidence_tier=confidence_tier_label(outcome.score),
                outcome=outcome.action,
                reason=f"score={outcome.score:.3f} against weights",
            )
        )
        state.metrics.addressee_fusion_total.add(1, {"outcome": outcome.action})

        if outcome.tier == "high":
            await maybe_activate_listening(
                app, user_id=payload.user_id, correlation_id=envelope.correlation_id
            )

    return handle
