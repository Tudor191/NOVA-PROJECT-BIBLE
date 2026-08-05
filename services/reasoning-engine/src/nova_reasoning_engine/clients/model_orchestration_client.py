"""`ModelOrchestrationClient` -- `domain.ports.ModelOrchestrationPort`
implementation, the concrete adapter behind ADR-020's sole legal channel to
any model: `ai_model.generate.request`, served by the AI Model Orchestration
Engine (Phase 2A). Used only by `hypothesis_generation.py` (§12) -- no other
module in this engine calls a model.

A longer default timeout than the other clients: generation calls can
legitimately take several seconds at Reasoning Level 2+ (design doc §21),
unlike a bounded lookup RPC.
"""

from __future__ import annotations

from nova_contracts import GenerateReplyPayload, GenerateRequestPayload

from nova_reasoning_engine.domain.ports import EventPublisher

__all__ = ["ModelOrchestrationClient"]

SOURCE_ENGINE = "reasoning-engine"
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
