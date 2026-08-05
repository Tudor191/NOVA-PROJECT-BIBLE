"""A deterministic, in-memory `ModelConnector` -- no network, no provider SDK.
Used by integration tests and, per design doc §19, as the connector every
domain test and the ADR-023 compliance suite runs against to prove the rest of
the engine (and every other connector) behaves identically regardless of which
connector is in use (SAD 06 §6's `test_connector_swap.py` requirement).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from nova_ai_model_orchestration_engine.domain.models import (
    ConnectorHealth,
    GenerateChunk,
    GenerateRequest,
    GenerateResult,
    ToolCall,
)
from nova_ai_model_orchestration_engine.domain.ports import NotSupportedError

__all__ = ["FakeConnector"]


class FakeConnector:
    connector_type = "fake"

    def __init__(
        self,
        *,
        response_text: str = "This is a fake response.",
        should_fail: bool = False,
        supports_embedding: bool = True,
        available: bool = True,
    ) -> None:
        self.response_text = response_text
        self.should_fail = should_fail
        self.supports_embedding = supports_embedding
        self.available = available
        self.calls = 0

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        self.calls += 1
        if self.should_fail:
            raise RuntimeError("FakeConnector configured to fail")
        tool_calls = [
            ToolCall(id=f"call_{i}", tool_name=tool.name, arguments={})
            for i, tool in enumerate(request.tools)
        ]
        return GenerateResult(
            text=self.response_text,
            tool_calls=tool_calls,
            input_tokens=sum(c.token_estimate for c in request.context),
            output_tokens=len(self.response_text.split()),
            finish_reason="tool_calls" if tool_calls else "stop",
            structural_confidence=1.0,
        )

    async def stream(self, request: GenerateRequest) -> AsyncIterator[GenerateChunk]:
        if self.should_fail:
            raise RuntimeError("FakeConnector configured to fail")
        words = self.response_text.split()
        for word in words:
            yield GenerateChunk(delta_text=word + " ")
        yield GenerateChunk(finished=True, finish_reason="stop")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.supports_embedding:
            raise NotSupportedError(self.connector_type, "embedding")
        # Deterministic, content-derived "embedding" -- not semantically
        # meaningful, but stable across calls for the same input, which is all
        # a fake needs to be for testing.
        return [[float(len(t)), float(sum(ord(c) for c in t) % 997)] for t in texts]

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(available=self.available, latency_ms=1.0, error_rate=0.0)
