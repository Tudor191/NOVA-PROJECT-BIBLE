"""`DigitalTwinClient` -- `domain.ports.DigitalTwinPort` implementation,
calling `digital_twin.preferences.get.request` (Phase 2D-D docs/design/
phase-2d/06-personal-companion.md Sec7.2, Fork A) -- an optional,
non-load-bearing dependency, unlike `PersonalityClient`: it is called only
when a caller actually needs pacing/timing data, not on every turn.

`TimeoutError` propagates uncaught, mirroring `PersonalityClient`'s own
documented convention -- this client's own job is only the RPC call and
payload translation; `domain.response_shaping.resolve_response_shaping` is
the one place that catches it and degrades gracefully.
"""

from __future__ import annotations

from uuid import UUID

from nova_contracts import (
    DigitalTwinPreferencesGetReplyPayload,
    DigitalTwinPreferencesGetRequestPayload,
)

from nova_communication_engine.domain.ports import EventPublisher, PreferenceSelection

__all__ = ["DigitalTwinClient"]

SOURCE_ENGINE = "communication-engine"


class DigitalTwinClient:
    def __init__(self, event_publisher: EventPublisher, *, timeout_ms: int = 2000) -> None:
        self._event_publisher = event_publisher
        self._timeout_ms = timeout_ms

    async def get_preferences(
        self, *, user_id: UUID, correlation_id: UUID | None = None
    ) -> PreferenceSelection | None:
        # `DigitalTwinPreferencesGetRequestPayload` carries no `correlation_id`
        # field of its own (unlike `PersonalityStyleSelectRequestPayload` /
        # `ReasoningRequestPayload`) -- the envelope-level `correlation_id`
        # below is the only place it is threaded through.
        reply = await self._event_publisher.request(
            "digital_twin.preferences.get.request",
            DigitalTwinPreferencesGetRequestPayload(user_id=user_id),
            source_engine=SOURCE_ENGINE,
            correlation_id=correlation_id,
            timeout_ms=self._timeout_ms,
        )
        parsed = DigitalTwinPreferencesGetReplyPayload.model_validate(reply.payload)
        if parsed.preferences is None:
            return None
        return PreferenceSelection(
            conversation_pacing=parsed.preferences.get("conversation_pacing"),
            habit_timing_hint=parsed.preferences.get("habit_timing_hint"),
        )
