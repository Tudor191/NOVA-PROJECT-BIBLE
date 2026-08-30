"""`ModelGatewayClient` -- `nova_agent_sdk.ModelGatewayPort` implementation,
the kernel-mediated adapter behind ADR-020's sole legal channel to any
model, injected into a spawned instance's own `Handler.__init__` by
`InprocessExecutionBackend` (see that module's own docstring for the
constructor convention). Mirrors `reasoning-engine`'s own
`ModelOrchestrationClient` structure exactly -- the RPC (`ai_model.generate.
request`) is identical regardless of which engine calls it.
"""

from __future__ import annotations

from nova_contracts import GenerateReplyPayload, GenerateRequestPayload

from nova_agent_os_kernel.domain.ports import EventPublisher

__all__ = ["ModelGatewayClient"]

SOURCE_ENGINE = "kernel"
DEFAULT_TIMEOUT_MS = 10_000


class ModelGatewayClient:
    def __init__(
        self, event_publisher: EventPublisher, *, timeout_ms: int = DEFAULT_TIMEOUT_MS
    ) -> None:
        self._event_publisher = event_publisher
        self._timeout_ms = timeout_ms

    async def generate(self, request: GenerateRequestPayload) -> GenerateReplyPayload:
        envelope = await self._event_publisher.request(
            "ai_model.generate.request",
            request,
            source_engine=SOURCE_ENGINE,
            correlation_id=request.correlation_id,
            timeout_ms=self._timeout_ms,
        )
        return GenerateReplyPayload.model_validate(envelope.payload)
