"""A real Event Bus round-trip through `main.py`'s served `action.execute`
RPC (TDD 3D §5) -- mirrors `capability-engine`'s own
`test_events_capability_resolve_and_invoke.py` convention exactly (the
closest, most recent precedent in this codebase).

`app.state.bus`'s own `publishable_subjects` (`events/published.py`)
deliberately do not include `action.execute` -- this engine only ever
*serves* that subject, never calls it on itself. A second `BoundEventBus`,
wrapping the exact same underlying in-memory bus instance, stands in for
the kind of external caller (Phase 3E's future Kernel Scheduler) whose own
`published.py` would legitimately list it."""

from __future__ import annotations

from uuid import uuid4

from nova_action_engine.config import Settings
from nova_action_engine.main import create_app
from nova_contracts import ActionExecuteRequestPayload, ActionResultPayload, Capability
from nova_eventbus_sdk import BoundEventBus

from tests.fakes.capability_port import FakeCapabilityPort
from tests.fakes.communication_port import FakeCommunicationPort
from tests.fakes.identity_port import FakeIdentityPort
from tests.fakes.repository import FakeActionRepository


def _capability(**overrides: object) -> Capability:
    from datetime import UTC, datetime

    defaults: dict[str, object] = {
        "id": uuid4(),
        "name": "filesystem",
        "description": "Read, write, and list files.",
        "category": "filesystem",
        "version": "1.0.0",
        "required_permissions": ["filesystem:read"],
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "execution_adapter": "filesystem",
        "health_status": "healthy",
        "installed_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Capability(**defaults)  # type: ignore[arg-type]


def _caller_bus(app):  # type: ignore[no-untyped-def]
    return BoundEventBus(
        app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
        engine_name="test-caller-engine",
        publishable_subjects=frozenset({"action.execute"}),
        subscribable_subjects=frozenset(),
    )


async def test_action_execute_round_trips_a_successful_action(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    capability_port = FakeCapabilityPort()
    capability = _capability()
    capability_port.capabilities_by_name["filesystem"] = capability
    capability_port.queue_invoke_result(capability.id, "read", ("success", {"content": "hi"}, None))
    identity_port = FakeIdentityPort()
    request = ActionExecuteRequestPayload(
        action_id=uuid4(),
        action_type="filesystem",
        priority="normal",
        source="test-suite",
        requested_by=uuid4(),
        execution_target="filesystem",
        parameters={"operation": "read", "path": "/tmp/note.txt"},
        verification_method="adapter_confirmation",
        requesting_engine="test-caller-engine",
        correlation_id=uuid4(),
    )
    identity_port.confidence_by_user[request.requested_by] = 1.0
    app = create_app(
        Settings(),
        repository=FakeActionRepository(),
        capability_port=capability_port,
        communication_port=FakeCommunicationPort(),
        identity_port=identity_port,
    )

    async with app.router.lifespan_context(app):
        caller_bus = _caller_bus(app)
        reply_envelope = await caller_bus.request(
            "action.execute", request, source_engine="test-caller-engine"
        )
        reply = ActionResultPayload.model_validate(reply_envelope.payload)

    assert reply.status == "completed"
    assert reply.result == {"content": "hi"}


async def test_action_execute_reports_a_structured_failure_for_an_unknown_capability(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    identity_port = FakeIdentityPort()
    request = ActionExecuteRequestPayload(
        action_id=uuid4(),
        action_type="filesystem",
        priority="normal",
        source="test-suite",
        requested_by=uuid4(),
        execution_target="nonexistent",
        parameters={"operation": "read"},
        verification_method="adapter_confirmation",
        requesting_engine="test-caller-engine",
        correlation_id=uuid4(),
    )
    identity_port.confidence_by_user[request.requested_by] = 1.0
    app = create_app(
        Settings(),
        repository=FakeActionRepository(),
        capability_port=FakeCapabilityPort(),
        communication_port=FakeCommunicationPort(),
        identity_port=identity_port,
    )

    async with app.router.lifespan_context(app):
        caller_bus = _caller_bus(app)
        reply_envelope = await caller_bus.request(
            "action.execute", request, source_engine="test-caller-engine"
        )
        reply = ActionResultPayload.model_validate(reply_envelope.payload)

    assert reply.status == "failed"
    assert reply.error is not None and "not found" in reply.error


async def test_action_execute_denies_when_identity_confidence_signal_is_absent(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """No `confidence_by_user` entry seeded -- `FakeIdentityPort.get_confidence`
    returns `None`, exercising ADR-032's fail-closed default end-to-end
    through the real served RPC."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    request = ActionExecuteRequestPayload(
        action_id=uuid4(),
        action_type="filesystem",
        priority="normal",
        source="test-suite",
        requested_by=uuid4(),
        execution_target="filesystem",
        parameters={"operation": "read"},
        verification_method="adapter_confirmation",
        requesting_engine="test-caller-engine",
        correlation_id=uuid4(),
    )
    app = create_app(
        Settings(),
        repository=FakeActionRepository(),
        capability_port=FakeCapabilityPort(),
        communication_port=FakeCommunicationPort(),
        identity_port=FakeIdentityPort(),
    )

    async with app.router.lifespan_context(app):
        caller_bus = _caller_bus(app)
        reply_envelope = await caller_bus.request(
            "action.execute", request, source_engine="test-caller-engine"
        )
        reply = ActionResultPayload.model_validate(reply_envelope.payload)

    assert reply.status == "denied"
    assert reply.error == "identity_confidence_denied"
