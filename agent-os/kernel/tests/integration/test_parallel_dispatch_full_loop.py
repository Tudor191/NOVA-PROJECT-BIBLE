"""Real parallel dispatch through a real Kernel `create_app()` -- the same
"real Scheduler, real `RegistryClient` RPC, real `InprocessExecutionBackend`,
real Agent Package Handler" shape `test_full_loop_research_agent.py`
establishes, extended to two independent `"ready"` nodes and asserting they
genuinely overlap.

This is the integration-level counterpart to `tests/unit/test_scheduler.py`'s
own barrier tests. The unit tests prove `dispatch_ready_nodes`' own
concurrency in isolation; this one proves the property survives the whole
real path -- `planning.task_graph.created` arriving on a real bus, a real
`RegistryClient` RPC per node, two real `research-agent` Handler instances,
and two real `agent_os.task.completed` publications.

**Where the overlap is observed.** The `ModelGatewayPort` injected into the
real `InprocessExecutionBackend` is the one component both instances pass
through while doing their real work, so it is where a rendezvous can be
placed without touching production code. `research-agent`'s own real
`execute()` calls it exactly once (see that package's own handler), so a
two-party `asyncio.Barrier` there releases only when both real instances are
simultaneously inside `execute()`. Under a sequential dispatch loop the
first instance would wait for a participant that can never arrive.

Stand-ins are the same three this file's sibling full-loop tests already
use, for the same reasons: a `BoundEventBus` standing in for
`agent-os/registry`'s served RPC, one standing in for `planning-engine` as
the real publisher/consumer, and `FakeModelGatewayPort` for
`ai-model-orchestration-engine` (ADR-020's channel is proven separately by
`reasoning-engine`'s own client test).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from nova_agent_os_kernel.config import Settings
from nova_agent_os_kernel.domain.execution_backend import InprocessExecutionBackend
from nova_agent_os_kernel.main import create_app
from nova_contracts import (
    AgentOsFindHealthyPackageReplyPayload,
    AgentOsFindHealthyPackageRequestPayload,
    AgentOsTaskCompletedPayload,
    AgentPackageSnapshot,
    EventEnvelope,
    GenerateReplyPayload,
    GenerateRequestPayload,
    PlanningTaskGraphCreatedPayload,
    TaskGraphSnapshot,
    TaskNodeSnapshot,
)
from nova_eventbus_sdk import BoundEventBus
from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus

from tests.fakes.repository import FakeKernelRepository

_REPO_ROOT = Path(__file__).resolve().parents[4]


class _RendezvousModelGateway:
    """A real `ModelGatewayPort` implementation whose `generate()` blocks
    until `parties` instances are inside it at once.

    `research-agent`'s own `execute()` awaits exactly one `generate()` call,
    so arriving here means that instance is genuinely mid-execution. The
    barrier therefore releases only when every expected instance is
    concurrently in flight -- which a sequential dispatch loop can never
    achieve."""

    def __init__(self, *, parties: int, timeout: float = 5.0) -> None:
        self._barrier = asyncio.Barrier(parties)
        self._timeout = timeout
        self.concurrent_peak = 0
        self._in_flight = 0

    async def generate(self, request: GenerateRequestPayload) -> GenerateReplyPayload:
        self._in_flight += 1
        self.concurrent_peak = max(self.concurrent_peak, self._in_flight)
        try:
            async with asyncio.timeout(self._timeout):
                await self._barrier.wait()
        finally:
            self._in_flight -= 1
        return GenerateReplyPayload(
            text="Token-bucket rate limiting is the standard approach.",
            input_tokens=42,
            output_tokens=17,
            finish_reason="stop",
            structural_confidence=0.9,
            model_id=uuid4(),
            provider="fake",
        )


def _research_package_snapshot() -> AgentPackageSnapshot:
    """Matches, field-for-field, what Registry's own real install pipeline
    produces for `agents/research-agent/agent.yaml` -- independently proven
    by `agent-os/registry`'s own `test_real_research_agent_installs.py`."""
    return AgentPackageSnapshot(
        id=uuid4(),
        category="research",
        version="0.1.0",
        manifest_json={
            "id": "research-agent",
            "version": "0.1.0",
            "category": "research",
            "display_name": "Research Agent",
            "required_capabilities": [],
            "required_permissions": [],
            "supported_execution_backends": ["inprocess"],
            "resource_profile": {"cpu": "standard", "memory": "standard", "gpu": "none"},
            "health_check": {"interval_seconds": 30},
            "compatibility": {"min_kernel_version": "0.1.0"},
        },
        health_status="healthy",
    )


def _node(objective: str) -> TaskNodeSnapshot:
    return TaskNodeSnapshot(
        id=uuid4(),
        objective=objective,
        depends_on=[],
        assigned_agent_category="research",
        effort_hours=1.0,
        confidence=0.7,
        risk="low",
        status="ready",
    )


async def test_two_independent_nodes_really_execute_concurrently_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    shared_bus = InMemoryEventBus()
    monkeypatch.setattr("nova_agent_os_kernel.main.get_event_bus", lambda: shared_bus)

    package = _research_package_snapshot()
    repository = FakeKernelRepository()
    model_gateway = _RendezvousModelGateway(parties=2)
    execution_backend = InprocessExecutionBackend(
        agents_root=_REPO_ROOT / "agents", model_gateway=model_gateway
    )

    app = create_app(
        Settings(primary_user_id=uuid4()),
        repository=repository,
        execution_backend=execution_backend,
    )

    async with app.router.lifespan_context(app):
        registry_stand_in = BoundEventBus(
            shared_bus,
            engine_name="registry",
            publishable_subjects=frozenset(),
            subscribable_subjects=frozenset({"agent_os.registry.find_healthy_package.request"}),
        )
        await registry_stand_in.connect()

        async def _answer(envelope: EventEnvelope) -> AgentOsFindHealthyPackageReplyPayload:
            AgentOsFindHealthyPackageRequestPayload.model_validate(envelope.payload)
            return AgentOsFindHealthyPackageReplyPayload(package=package)

        await registry_stand_in.serve(
            "agent_os.registry.find_healthy_package.request", _answer, source_engine="registry"
        )

        planning_stand_in = BoundEventBus(
            shared_bus,
            engine_name="planning-engine",
            publishable_subjects=frozenset({"planning.task_graph.created"}),
            subscribable_subjects=frozenset({"agent_os.task.completed"}),
        )
        await planning_stand_in.connect()

        completed: list[EventEnvelope] = []

        async def _capture(envelope: EventEnvelope) -> None:
            completed.append(envelope)

        await planning_stand_in.subscribe("agent_os.task.completed", _capture)

        left = _node("Research rate limiting approaches")
        right = _node("Research caching approaches")
        graph = TaskGraphSnapshot(
            id=uuid4(),
            root_objective="Investigate two independent areas",
            nodes=[left, right],
            critical_path=[left.id],
        )
        correlation_id = uuid4()
        await planning_stand_in.publish(
            EventEnvelope(
                subject="planning.task_graph.created",
                source_engine="planning-engine",
                correlation_id=correlation_id,
                payload=PlanningTaskGraphCreatedPayload(
                    graph=graph, correlation_id=correlation_id
                ).model_dump(mode="json"),
            )
        )

        # Both real agent instances were inside their own real `execute()`
        # at the same moment -- the barrier could not have released
        # otherwise, and a sequential loop would have timed out here.
        assert model_gateway.concurrent_peak == 2

        # Per-node isolation survives the real path: one completion event
        # each, correctly attributed, both successful.
        assert len(completed) == 2
        payloads = [
            AgentOsTaskCompletedPayload.model_validate(envelope.payload)
            for envelope in completed
        ]
        assert {payload.task_node_id for payload in payloads} == {left.id, right.id}
        assert all(payload.outcome == "success" for payload in payloads)

        # Two distinct instances, each pinned to its own node and its own
        # package row, each ending terminal -- never left "running".
        assert len({payload.agent_instance_id for payload in payloads}) == 2
        for payload in payloads:
            row = await repository.find_by_id(payload.agent_instance_id)
            assert row is not None
            assert row.status == "completed"
            assert row.agent_package_id == package.id
            assert row.assigned_task_node_id == payload.task_node_id
        assert await repository.list_by_status("running") == []
