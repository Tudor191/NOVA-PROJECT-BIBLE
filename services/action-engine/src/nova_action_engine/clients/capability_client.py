"""`CapabilityClient` -- `domain.ports.CapabilityPort` implementation,
calling `capability-engine`'s already-shipped `capability.resolve.request`/
`capability.invoke.request` RPCs (TDD 3C §4, Fork 3C-1/3D-1's resolution).
Resolution is always by `name` (approved,
`docs/design/phase-3/13-3d-action-engine-research.md` §5.1) -- never by
`capability_id`, which `action-engine` has no way to know in advance.

`TimeoutError` propagates uncaught -- `domain/pipeline.py` is the one
place that decides how to react (e.g. failing the action, never silently
retrying), mirroring every other client's documented convention in this
project.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from nova_action_engine.domain.ports import CapabilityInvokeOutcome, EventPublisher
from nova_contracts import (
    Capability,
    CapabilityInvokeReplyPayload,
    CapabilityInvokeRequestPayload,
    CapabilityResolveReplyPayload,
    CapabilityResolveRequestPayload,
)

__all__ = ["CapabilityClient"]

SOURCE_ENGINE = "action-engine"


class CapabilityClient:
    def __init__(self, event_publisher: EventPublisher, *, timeout_ms: int = 2000) -> None:
        self._event_publisher = event_publisher
        self._timeout_ms = timeout_ms

    async def resolve(
        self, *, name: str, correlation_id: UUID | None = None
    ) -> Capability | None:
        reply = await self._event_publisher.request(
            "capability.resolve.request",
            CapabilityResolveRequestPayload(
                name=name,
                requesting_engine=SOURCE_ENGINE,
                correlation_id=correlation_id or uuid4(),
            ),
            source_engine=SOURCE_ENGINE,
            correlation_id=correlation_id,
            timeout_ms=self._timeout_ms,
        )
        parsed = CapabilityResolveReplyPayload.model_validate(reply.payload)
        return parsed.capability if parsed.found else None

    async def invoke(
        self,
        *,
        capability_id: UUID,
        operation: str,
        parameters: dict,
        correlation_id: UUID | None = None,
    ) -> tuple[CapabilityInvokeOutcome, dict | None, str | None]:
        reply = await self._event_publisher.request(
            "capability.invoke.request",
            CapabilityInvokeRequestPayload(
                capability_id=capability_id,
                operation=operation,
                parameters=parameters,
                requesting_engine=SOURCE_ENGINE,
                correlation_id=correlation_id or uuid4(),
            ),
            source_engine=SOURCE_ENGINE,
            correlation_id=correlation_id,
            timeout_ms=self._timeout_ms,
        )
        parsed = CapabilityInvokeReplyPayload.model_validate(reply.payload)
        return parsed.outcome, parsed.result, parsed.error
