"""`PersonalityClient` -- `domain.ports.PersonalityPort` implementation,
calling `personality.validate_response.request`/`personality.style.select.
request` (design doc Sec0.5, Sec7 step 2, Sec8.3) -- a real, load-bearing
synchronous dependency from day one, unlike every other upstream port this
engine defines.

`TimeoutError` propagates uncaught -- `domain.intent_gate.deliver_intent`
is the one place that catches it and applies Sec9's documented fallback;
this client's own job is only the RPC call and payload translation.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from nova_contracts import (
    ConfidenceTier,
    PersonalityStyleSelectReplyPayload,
    PersonalityStyleSelectRequestPayload,
    PersonalityValidateResponseReplyPayload,
    PersonalityValidateResponseRequestPayload,
)

from nova_communication_engine.domain.ports import EventPublisher, StyleSelection, ValidationOutcome

__all__ = ["PersonalityClient"]

SOURCE_ENGINE = "communication-engine"


class PersonalityClient:
    def __init__(self, event_publisher: EventPublisher, *, timeout_ms: int = 2000) -> None:
        self._event_publisher = event_publisher
        self._timeout_ms = timeout_ms

    async def validate_response(
        self,
        *,
        content: str,
        confidence_tier: str,
        session_id: UUID,
        correlation_id: UUID | None = None,
    ) -> ValidationOutcome:
        reply = await self._event_publisher.request(
            "personality.validate_response.request",
            PersonalityValidateResponseRequestPayload(
                content=content,
                confidence_tier=ConfidenceTier(confidence_tier),
                session_id=session_id,
                requesting_engine=SOURCE_ENGINE,
                correlation_id=correlation_id or uuid4(),
            ),
            source_engine=SOURCE_ENGINE,
            correlation_id=correlation_id,
            timeout_ms=self._timeout_ms,
        )
        parsed = PersonalityValidateResponseReplyPayload.model_validate(reply.payload)
        rejection_reason = None
        if not parsed.passed and parsed.violations:
            first_violation = parsed.violations[0]
            rejection_reason = f"{first_violation.check_family.value}: {first_violation.detail}"
        return ValidationOutcome(
            passed=parsed.passed,
            adjusted_content=parsed.adjusted_content,
            rejection_reason=rejection_reason,
        )

    async def select_style(
        self,
        *,
        situation_hint: str | None,
        channel: str | None,
        correlation_id: UUID | None = None,
    ) -> StyleSelection:
        reply = await self._event_publisher.request(
            "personality.style.select.request",
            PersonalityStyleSelectRequestPayload(
                situation_hint=situation_hint,
                channel=channel,
                requesting_engine=SOURCE_ENGINE,
                correlation_id=correlation_id or uuid4(),
            ),
            source_engine=SOURCE_ENGINE,
            correlation_id=correlation_id,
            timeout_ms=self._timeout_ms,
        )
        parsed = PersonalityStyleSelectReplyPayload.model_validate(reply.payload)
        return StyleSelection(
            style=parsed.style.value,
            verbosity=parsed.verbosity,
            technical_depth=parsed.technical_depth,
        )
