"""The `communication.intent` gate -- ADR-005 enforcement (design doc Sec7).
Every candidate outbound utterance -- generated *content*, from any
content-source engine -- passes through `deliver_intent` before it can
reach a `ChannelAdapter`. This is the only function in this codebase that
delivers generated content (directly, for text, or via `domain.speech.
speak_response` for voice) -- enforced structurally (callers never hold
their own adapter reference for that purpose) and by the import-boundary
linter's engine-independence contract, not merely by convention (design doc
Sec7's closing paragraph).

`api/websocket.py`'s one narrow, documented exception -- a Sec9 transport-
status notice ("voice temporarily unavailable") on a transcribe failure --
delivers directly through the adapter rather than this gate: it is not
generated content requiring personality review, the same way a `Paused`
state transition itself is never personality-gated either.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from nova_communication_engine.domain import speech
from nova_communication_engine.domain.models import (
    ChannelType,
    ConversationSession,
    ConversationState,
    ConversationTurn,
    OutboundMessage,
    OutboundMessageKind,
    TurnDirection,
)
from nova_communication_engine.domain.ports import (
    ChannelAdapter,
    CommunicationRepository,
    ModelOrchestrationPort,
    PersonalityPort,
)

__all__ = ["IntentDeliveryOutcome", "deliver_intent"]


class IntentDeliveryOutcome(BaseModel):
    """`delivered=False` covers three causes, distinguished by
    `rejection_reason` (nova-contracts' `CommunicationIntentDeliverReplyPayload`
    docstring): a personality hard-stop (content must never reach the user,
    02-personality-engine.md Sec8), a delivery-mechanics failure (session
    already completed, no live channel connection), or -- voice only -- a
    barge-in/synthesis failure partway through delivery."""

    delivered: bool
    personality_validated: bool
    degraded: bool = False
    turn_id: UUID | None = None
    rejection_reason: str | None = None


async def deliver_intent(
    *,
    session: ConversationSession,
    content: str,
    confidence_tier: str,
    channel_adapter: ChannelAdapter | None,
    personality_port: PersonalityPort,
    model_orchestration_port: ModelOrchestrationPort,
    repository: CommunicationRepository,
    barge_in_signal: speech.BargeInSignal | None = None,
    correlation_id: UUID | None = None,
) -> IntentDeliveryOutcome:
    # Step 1 (Sec7): schema/session validation.
    if session.state is ConversationState.COMPLETED:
        return IntentDeliveryOutcome(
            delivered=False, personality_validated=False, rejection_reason="session_completed"
        )

    # Step 2 (Sec7): personality validation, with Sec9's documented fallback
    # on RPC failure -- deliver unvalidated content rather than silence.
    personality_validated = True
    degraded = False
    try:
        validation = await personality_port.validate_response(
            content=content,
            confidence_tier=confidence_tier,
            session_id=session.session_id,
            correlation_id=correlation_id,
        )
    except TimeoutError:
        personality_validated = False
        degraded = True
        final_content = content
    else:
        if not validation.passed:
            # 02-personality-engine.md Sec8: a hard-stop violation must
            # never be delivered, even adjusted -- this is the one path
            # Sec9's "deliver with fallback" does not apply to.
            return IntentDeliveryOutcome(
                delivered=False,
                personality_validated=True,
                rejection_reason=validation.rejection_reason or "personality_validation_failed",
            )
        final_content = validation.adjusted_content or content

    # Step 3 (Sec7): delivery, recorded as an outbound ConversationTurn.
    turn = ConversationTurn(
        session_id=session.session_id,
        direction=TurnDirection.OUTBOUND,
        content=final_content,
        channel=session.channel,
        personality_validated=personality_validated,
    )

    if channel_adapter is None:
        await repository.append_turn(turn)
        return IntentDeliveryOutcome(
            delivered=False,
            personality_validated=personality_validated,
            degraded=degraded,
            turn_id=turn.turn_id,
            rejection_reason="no_live_channel_connection",
        )

    if session.channel is ChannelType.VOICE:
        result = await speech.speak_response(
            content=final_content,
            channel_adapter=channel_adapter,
            model_orchestration_port=model_orchestration_port,
            barge_in_signal=barge_in_signal or speech.BargeInSignal(),
        )
        saved_turn = await repository.append_turn(turn)
        if result.barged_in:
            return IntentDeliveryOutcome(
                delivered=result.delivered_chunks > 0,
                personality_validated=personality_validated,
                degraded=degraded,
                turn_id=saved_turn.turn_id,
                rejection_reason="barged_in",
            )
        if result.delivered_chunks < result.total_chunks:
            return IntentDeliveryOutcome(
                delivered=result.delivered_chunks > 0,
                personality_validated=personality_validated,
                degraded=degraded,
                turn_id=saved_turn.turn_id,
                rejection_reason="synthesis_failed",
            )
        return IntentDeliveryOutcome(
            delivered=True,
            personality_validated=personality_validated,
            degraded=degraded,
            turn_id=saved_turn.turn_id,
        )

    await channel_adapter.deliver(
        OutboundMessage(kind=OutboundMessageKind.TEXT, content=final_content)
    )
    saved_turn = await repository.append_turn(turn)
    return IntentDeliveryOutcome(
        delivered=True,
        personality_validated=personality_validated,
        degraded=degraded,
        turn_id=saved_turn.turn_id,
    )
