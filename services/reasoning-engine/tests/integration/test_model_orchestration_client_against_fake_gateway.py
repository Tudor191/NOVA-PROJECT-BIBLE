"""Proof-of-adoption for `nova_testkit.FakeModelGateway`
(docs/design/nova-testkit/technical-implementation-plan.md §11 task 2): the
real, unmodified `ModelOrchestrationClient` -- production code, not a fake or a
mock -- talks to `fake_model_gateway` over the real `event_bus` fixture,
proving the fake is a drop-in for the real `ai_model.generate.request` event
contract, not merely "returns some payload" (§13's verification bar).
"""

from uuid import uuid4

from nova_contracts import GenerateRequestPayload
from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus
from nova_reasoning_engine.clients.model_orchestration_client import ModelOrchestrationClient
from nova_testkit import FakeModelGateway


async def test_real_client_generates_against_fake_gateway(
    event_bus: InMemoryEventBus, fake_model_gateway: FakeModelGateway
) -> None:
    client = ModelOrchestrationClient(event_bus)

    reply = await client.generate(
        GenerateRequestPayload(
            context=[], requesting_engine="reasoning-engine", correlation_id=uuid4()
        )
    )

    assert reply.text == "This is a fake response."
    assert reply.finish_reason == "stop"
    assert reply.error is None
    assert fake_model_gateway.calls == ["ai_model.generate.request"]


async def test_real_client_surfaces_fake_gateway_failure(event_bus: InMemoryEventBus) -> None:
    gateway = FakeModelGateway(should_fail=True)
    await gateway.start(event_bus)
    try:
        client = ModelOrchestrationClient(event_bus)

        reply = await client.generate(
            GenerateRequestPayload(
                context=[], requesting_engine="reasoning-engine", correlation_id=uuid4()
            )
        )

        assert reply.finish_reason == "error"
        assert reply.error == "FakeModelGateway configured to fail"
    finally:
        await gateway.stop()
