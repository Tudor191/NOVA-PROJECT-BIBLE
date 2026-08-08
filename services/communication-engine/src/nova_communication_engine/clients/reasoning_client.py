"""`ReasoningClient` -- `domain.ports.ReasoningPort` implementation, calling
`reasoning.reason.request` (docs/design/phase-2d/
05-conversation-intelligence-closure.md Sec5.3, Fork #1 -- user-approved
synchronous RPC design, the same pattern this engine already uses for
`personality.style.select.request`/`world_model.context.request`/
`ai_model.transcribe.request`).

`TimeoutError` propagates uncaught -- `conversation_orchestration.
handle_conversation_turn` is the one place that catches it and applies the
degraded-mode fallback; this client's own job is only the RPC call and
payload translation (mirrors `clients/personality_client.py`'s own
documented convention exactly).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from nova_contracts import ReasoningReplyPayload, ReasoningRequestPayload

from nova_communication_engine.domain.ports import EventPublisher, ReasoningOutcomeResult

__all__ = ["ReasoningClient"]

SOURCE_ENGINE = "communication-engine"


class ReasoningClient:
    def __init__(self, event_publisher: EventPublisher, *, timeout_ms: int = 10000) -> None:
        self._event_publisher = event_publisher
        self._timeout_ms = timeout_ms

    async def reason(
        self, *, objective_text: str, user_id: UUID, correlation_id: UUID | None = None
    ) -> ReasoningOutcomeResult:
        reply = await self._event_publisher.request(
            "reasoning.reason.request",
            ReasoningRequestPayload(
                objective_text=objective_text,
                user_id=user_id,
                requesting_engine=SOURCE_ENGINE,
                correlation_id=correlation_id or uuid4(),
            ),
            source_engine=SOURCE_ENGINE,
            correlation_id=correlation_id,
            timeout_ms=self._timeout_ms,
        )
        parsed = ReasoningReplyPayload.model_validate(reply.payload)
        return ReasoningOutcomeResult(
            outcome=parsed.outcome.value,
            content=parsed.chosen_description,
            confidence_score=parsed.confidence_score,
            reasoning_process_id=parsed.reasoning_process_id,
            error=parsed.error,
        )
