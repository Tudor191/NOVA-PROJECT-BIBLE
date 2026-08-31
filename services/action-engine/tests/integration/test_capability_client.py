"""`clients.capability_client.CapabilityClient` (TDD 3D §2, Fork 3C-1/3D-1)
-- a real Event Bus round trip through `capability.resolve.request`/
`capability.invoke.request`, mirroring `capability-engine`'s own
`test_communication_client.py` convention: an in-process stand-in for
`capability-engine`'s own network position *serves* both RPCs for real
over the in-memory Event Bus, and this engine's own (non-fake)
`CapabilityClient`, constructed by `create_app` with no override, calls
them directly."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from nova_action_engine.config import Settings
from nova_action_engine.main import create_app
from nova_contracts import (
    Capability,
    CapabilityInvokeReplyPayload,
    CapabilityInvokeRequestPayload,
    CapabilityResolveReplyPayload,
    CapabilityResolveRequestPayload,
)
from nova_eventbus_sdk import BoundEventBus

from tests.fakes.communication_port import FakeCommunicationPort
from tests.fakes.identity_port import FakeIdentityPort
from tests.fakes.repository import FakeActionRepository


def _capability(**overrides: object) -> Capability:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "name": "git",
        "description": "Version control operations.",
        "category": "development",
        "version": "1.0.0",
        "required_permissions": ["git:read"],
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "execution_adapter": "git",
        "health_status": "healthy",
        "installed_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Capability(**defaults)  # type: ignore[arg-type]


def _capability_serving_bus(app):  # type: ignore[no-untyped-def]
    return BoundEventBus(
        app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
        engine_name="capability-engine",
        publishable_subjects=frozenset(),
        subscribable_subjects=frozenset(
            {"capability.resolve.request", "capability.invoke.request"}
        ),
    )


def _harness_app(**overrides: object):  # type: ignore[no-untyped-def]
    return create_app(
        Settings(),
        repository=FakeActionRepository(),
        communication_port=FakeCommunicationPort(),
        identity_port=FakeIdentityPort(),
        **overrides,  # type: ignore[arg-type]
    )


async def test_a_real_resolve_call_reaches_a_real_resolve_by_name_rpc_round_trip(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = _harness_app()
    capability = _capability()

    async with app.router.lifespan_context(app):
        received: list[CapabilityResolveRequestPayload] = []
        serving_bus = _capability_serving_bus(app)

        async def _serve_resolve(envelope):  # type: ignore[no-untyped-def]
            payload = CapabilityResolveRequestPayload.model_validate(envelope.payload)
            received.append(payload)
            return CapabilityResolveReplyPayload(found=True, capability=capability)

        await serving_bus.serve(
            "capability.resolve.request", _serve_resolve, source_engine="capability-engine"
        )

        result = await app.state.capability_port.resolve(name="git")

        assert result == capability
        assert len(received) == 1
        assert received[0].name == "git"
        assert received[0].capability_id is None


async def test_a_real_invoke_call_reaches_a_real_invoke_rpc_round_trip(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = _harness_app()

    async with app.router.lifespan_context(app):
        received: list[CapabilityInvokeRequestPayload] = []
        serving_bus = _capability_serving_bus(app)

        async def _serve_invoke(envelope):  # type: ignore[no-untyped-def]
            payload = CapabilityInvokeRequestPayload.model_validate(envelope.payload)
            received.append(payload)
            return CapabilityInvokeReplyPayload(outcome="success", result={"content": "hi"})

        await serving_bus.serve(
            "capability.invoke.request", _serve_invoke, source_engine="capability-engine"
        )

        capability_id = uuid4()
        outcome, result, error = await app.state.capability_port.invoke(
            capability_id=capability_id, operation="read", parameters={"path": "/tmp/x"}
        )

        assert outcome == "success"
        assert result == {"content": "hi"}
        assert error is None
        assert len(received) == 1
        assert received[0].capability_id == capability_id
        assert received[0].requesting_engine == "action-engine"
