"""Fakes for this engine's `domain/ports.py` Protocols -- never call a real
model (mirrors `nova_reasoning_engine.tests.fakes.ports.
FakeModelOrchestrationPort` exactly, the established precedent for this
same port)."""

from __future__ import annotations

from uuid import uuid4

from nova_contracts import GenerateReplyPayload, GenerateRequestPayload

__all__ = ["FakeModelOrchestrationPort"]


class FakeModelOrchestrationPort:
    """Returns a caller-configured `GenerateReplyPayload` (or a default
    empty-tool-call reply) -- never calls a real model."""

    def __init__(self, reply: GenerateReplyPayload | None = None) -> None:
        self.reply = reply
        self.requests: list[GenerateRequestPayload] = []

    async def generate(self, request: GenerateRequestPayload) -> GenerateReplyPayload:
        self.requests.append(request)
        if self.reply is not None:
            return self.reply
        return GenerateReplyPayload(
            text="",
            input_tokens=10,
            output_tokens=0,
            finish_reason="stop",
            structural_confidence=0.9,
            model_id=uuid4(),
            provider="fake",
        )
