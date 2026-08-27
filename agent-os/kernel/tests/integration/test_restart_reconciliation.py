"""A real `create_app()` restart round-trip through `main.py`'s own
lifespan-startup reconciliation call (TDD 3E §4/§12) -- strengthens
`tests/unit/test_reconciliation.py`'s own pure-function coverage of
`reconcile_running_instances` with proof that a genuine Kernel process
restart (a fresh `create_app()`, entering its `lifespan` context exactly as
the real ASGI server does on boot) actually calls it and actually publishes
`agent_os.task.completed` onto the real (in-memory) Event Bus -- not just
that the pure function itself behaves correctly in isolation.

Mirrors `test_full_loop_documentation_agent.py`'s own "shared
`InMemoryEventBus`, `get_event_bus` monkeypatched, external stand-in
`BoundEventBus`" convention, with one difference: the external observer
here must `connect()` and subscribe *before* entering the app's own
`lifespan_context`, since reconciliation runs synchronously during lifespan
startup (before `yield`), not in response to a later-published event.

`services/planning-engine/tests/integration/
test_events_agent_os_task_completed.py`'s own
`test_kernel_restart_then_planning_resume_round_trip` is the "resume" half
of this same restart-resume chain, constructing the identical payload
shape this test proves Kernel really publishes -- the two together, never
importing each other's production code (ADR-004), prove the full chain."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from nova_agent_os_kernel.config import Settings
from nova_agent_os_kernel.domain.models import AgentInstance
from nova_agent_os_kernel.main import create_app
from nova_contracts import AgentOsTaskCompletedPayload, EventEnvelope
from nova_eventbus_sdk import BoundEventBus
from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus

from tests.fakes.repository import FakeKernelRepository


async def test_a_real_kernel_restart_publishes_interrupted_for_every_running_instance(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    shared_bus = InMemoryEventBus()
    monkeypatch.setattr("nova_agent_os_kernel.main.get_event_bus", lambda: shared_bus)

    orphaned_task_node_id = uuid4()
    repository = FakeKernelRepository()
    orphaned_instance = await repository.insert(
        AgentInstance(
            id=uuid4(),
            agent_package_id=uuid4(),
            category="coding",
            execution_backend="inprocess",
            status="running",
            assigned_task_node_id=orphaned_task_node_id,
            started_at=datetime.now(UTC),
        )
    )

    observer = BoundEventBus(
        shared_bus,
        engine_name="test-observer",
        publishable_subjects=frozenset(),
        subscribable_subjects=frozenset({"agent_os.task.completed"}),
    )
    await observer.connect()

    captured: list[EventEnvelope] = []

    async def _capture(envelope: EventEnvelope) -> None:
        captured.append(envelope)

    await observer.subscribe("agent_os.task.completed", _capture)

    app = create_app(Settings(), repository=repository)

    # Reconciliation runs synchronously during lifespan startup, before
    # `yield` -- entering this context manager *is* "restarting Kernel."
    async with app.router.lifespan_context(app):
        pass

    assert len(captured) == 1
    payload = AgentOsTaskCompletedPayload.model_validate(captured[0].payload)
    assert payload.task_node_id == orphaned_task_node_id
    assert payload.agent_instance_id == orphaned_instance.id
    assert payload.outcome == "interrupted"
    assert payload.result is None

    reconciled = await repository.find_by_id(orphaned_instance.id)
    assert reconciled is not None
    assert reconciled.status == "failed"


async def test_a_real_kernel_restart_is_a_no_op_when_nothing_was_running(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    shared_bus = InMemoryEventBus()
    monkeypatch.setattr("nova_agent_os_kernel.main.get_event_bus", lambda: shared_bus)

    repository = FakeKernelRepository()
    await repository.insert(
        AgentInstance(
            id=uuid4(),
            agent_package_id=uuid4(),
            category="coding",
            execution_backend="inprocess",
            status="completed",
            assigned_task_node_id=uuid4(),
            started_at=datetime.now(UTC),
        )
    )

    observer = BoundEventBus(
        shared_bus,
        engine_name="test-observer",
        publishable_subjects=frozenset(),
        subscribable_subjects=frozenset({"agent_os.task.completed"}),
    )
    await observer.connect()
    captured: list[EventEnvelope] = []

    async def _capture(envelope: EventEnvelope) -> None:
        captured.append(envelope)

    await observer.subscribe("agent_os.task.completed", _capture)

    app = create_app(Settings(), repository=repository)
    async with app.router.lifespan_context(app):
        pass

    assert captured == []
