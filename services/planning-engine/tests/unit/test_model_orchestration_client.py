"""`ModelOrchestrationClient` unit tests -- mirrors
`nova_reasoning_engine.tests.unit.test_clients`'s identical tests for the
identical adapter, applied to this engine's copy."""

from __future__ import annotations

from uuid import uuid4

import pytest
from nova_contracts import GenerateReplyPayload, GenerateRequestPayload
from nova_planning_engine.clients.model_orchestration_client import ModelOrchestrationClient

from tests.fakes.event_publisher import FakeEventPublisher


async def test_model_orchestration_client_translates_reply() -> None:
    publisher = FakeEventPublisher()
    model_id = uuid4()

    def handler(payload: GenerateRequestPayload) -> GenerateReplyPayload:
        assert payload.requesting_engine == "planning-engine"
        return GenerateReplyPayload(
            text="hello",
            input_tokens=1,
            output_tokens=1,
            finish_reason="stop",
            structural_confidence=1.0,
            model_id=model_id,
            provider="anthropic",
        )

    publisher.register("ai_model.generate.request", handler)
    client = ModelOrchestrationClient(publisher)
    reply = await client.generate(
        GenerateRequestPayload(
            context=[], requesting_engine="planning-engine", correlation_id=uuid4()
        )
    )
    assert reply.model_id == model_id
    assert reply.text == "hello"


async def test_model_orchestration_client_propagates_timeout() -> None:
    client = ModelOrchestrationClient(FakeEventPublisher())
    with pytest.raises(TimeoutError):
        await client.generate(
            GenerateRequestPayload(
                context=[], requesting_engine="planning-engine", correlation_id=uuid4()
            )
        )
