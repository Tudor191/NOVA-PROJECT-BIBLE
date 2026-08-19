"""`IdentityClient` -- `domain.ports.IdentityPort` implementation, calling
`world_model.context.request` and reading `ContextReplyPayload.present_identities`
(TDD 3D §7, ADR-032). The first consumer of this field for authorization
purposes in this codebase -- no prior port/client precedent exists to
mirror beyond the general `WorldModelClient` request shape every other
engine already uses (`docs/design/phase-3/13-3d-action-engine-research.md`
§5.4/§4.4).

Per ADR-032 point 3, `action-engine` never performs identity recognition
itself -- this only reads `perception-engine`'s (via World Model's)
already-scored `PresentIdentityPayload.confidence` for the identity
matching `Action.requested_by`. Returns `None` (never raises) on timeout,
`degraded` replies, or when no matching identity is present --
`domain/pipeline.py`'s ADR-032 gate treats `None` as zero confidence,
fail-closed (TDD 3D §10)."""

from __future__ import annotations

from uuid import UUID

from nova_action_engine.domain.ports import EventPublisher
from nova_contracts import ContextReplyPayload, ContextRequestPayload

__all__ = ["IdentityClient"]

SOURCE_ENGINE = "action-engine"


class IdentityClient:
    def __init__(self, event_publisher: EventPublisher, *, timeout_ms: int = 2000) -> None:
        self._event_publisher = event_publisher
        self._timeout_ms = timeout_ms

    async def get_confidence(
        self, *, user_id: UUID, correlation_id: UUID | None = None
    ) -> float | None:
        try:
            reply = await self._event_publisher.request(
                "world_model.context.request",
                ContextRequestPayload(user_id=user_id),
                source_engine=SOURCE_ENGINE,
                correlation_id=correlation_id,
                timeout_ms=self._timeout_ms,
            )
        except TimeoutError:
            return None
        parsed = ContextReplyPayload.model_validate(reply.payload)
        if parsed.degraded:
            return None
        for identity in parsed.present_identities:
            if identity.identity_id == user_id:
                return identity.confidence
        return None
