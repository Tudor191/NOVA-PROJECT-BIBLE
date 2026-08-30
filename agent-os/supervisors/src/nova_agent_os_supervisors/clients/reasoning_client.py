"""`ReasoningClient` -- `domain.ports.ReasoningPort` implementation,
calling `reasoning.reason.request` (TDD 3E §7's "existing RPC"). Mirrors
`communication-engine`'s own `clients/reasoning_client.py` field-for-field
(same RPC, same request/reply shape); the only difference is the
narrower, Supervisor-local `ReasoningOutcome` return type (`domain/ports.py`).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from nova_contracts import ReasoningReplyPayload, ReasoningRequestPayload

from nova_agent_os_supervisors.domain.ports import EventPublisher, ReasoningOutcome

__all__ = ["ReasoningClient"]

SOURCE_ENGINE = "supervisors"


class ReasoningClient:
    def __init__(self, event_publisher: EventPublisher, *, timeout_ms: int = 10000) -> None:
        self._event_publisher = event_publisher
        self._timeout_ms = timeout_ms

    async def reason(
        self, *, objective_text: str, user_id: UUID, correlation_id: UUID | None = None
    ) -> ReasoningOutcome:
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
        return ReasoningOutcome(
            outcome=parsed.outcome.value,
            chosen_description=parsed.chosen_description,
            confidence_score=parsed.confidence_score,
        )
