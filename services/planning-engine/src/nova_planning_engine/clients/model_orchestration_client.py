"""`ModelOrchestrationClient` -- `domain.ports.ModelOrchestrationPort`
implementation, the concrete adapter behind ADR-020's sole legal channel to
any model: `ai_model.generate.request`, served by the AI Model
Orchestration Engine (Phase 2A). Used only by `domain/decomposition.py` --
no other module in this engine calls a model. Identical pattern to
`reasoning-engine`'s own `clients/model_orchestration_client.py` -- the
established precedent this engine's decomposition research
(`docs/design/phase-3/11-3b-decomposition-architecture-research.md` §6)
confirmed should be reused rather than re-invented.

A longer default timeout than a bounded lookup RPC would use: generation
calls can legitimately take several seconds, the same rationale
`reasoning-engine`'s own client documents for its identical default.
"""

from __future__ import annotations

from nova_contracts import GenerateReplyPayload, GenerateRequestPayload

from nova_planning_engine.domain.ports import EventPublisher

__all__ = ["ModelOrchestrationClient"]

SOURCE_ENGINE = "planning-engine"
DEFAULT_TIMEOUT_MS = 10_000


class ModelOrchestrationClient:
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
