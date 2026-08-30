"""`ActionClient` -- `nova_agent_sdk.ActionPort` implementation, injected
into a spawned instance's own `Handler.__init__` by
`InprocessExecutionBackend` (see that module's own docstring for the
constructor convention). Mirrors `ModelGatewayClient`'s own structure
exactly -- the RPC (`action.execute`) is identical regardless of which
engine calls it.
"""

from __future__ import annotations

from nova_contracts import ActionExecuteRequestPayload, ActionResultPayload

from nova_agent_os_kernel.domain.ports import EventPublisher

__all__ = ["ActionClient"]

SOURCE_ENGINE = "kernel"
DEFAULT_TIMEOUT_MS = 30_000


class ActionClient:
    def __init__(
        self, event_publisher: EventPublisher, *, timeout_ms: int = DEFAULT_TIMEOUT_MS
    ) -> None:
        self._event_publisher = event_publisher
        self._timeout_ms = timeout_ms

    async def execute(self, request: ActionExecuteRequestPayload) -> ActionResultPayload:
        envelope = await self._event_publisher.request(
            "action.execute",
            request,
            source_engine=SOURCE_ENGINE,
            correlation_id=request.correlation_id,
            timeout_ms=self._timeout_ms,
        )
        return ActionResultPayload.model_validate(envelope.payload)
