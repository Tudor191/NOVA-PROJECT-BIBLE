"""End-to-end proof of the roadmap's own step-4 precondition
(`docs/roadmap/ENGINEERING_ROADMAP.md`: "`agent-os/sdk` + `agent-os/kernel`
(inprocess backend only) + `agent-os/registry`, validated with a single
trivial agent (`research-agent`) to prove the full loop before adding
more"). A real Kernel `create_app()` -- real Scheduler, real
`RegistryClient` RPC, real `InprocessExecutionBackend` -- is driven by a
real `planning.task_graph.created` event and dispatches through the real
`agents/research-agent/src/handler.py` Handler.

The `agent_os.registry.find_healthy_package.request` RPC is answered by a
second `BoundEventBus` wrapping the *same* underlying `InMemoryEventBus`,
standing in for the real `agent-os/registry` -- this project's own
established "external caller/server stand-in" pattern for a served RPC
(e.g. every engine's own `tests/integration/test_events_*.py`/
`test_*_client.py`; deliberately *not* importing `nova_agent_os_registry`'s
own `domain/` here, matching every existing cross-engine client test in
this codebase, none of which import the counterparty engine's internals --
only `nova_contracts` + `nova_eventbus_sdk` cross a test's own engine
boundary). The reply payload matches exactly what Registry's own real
install of `agents/research-agent` produces, independently proven by
`agent-os/registry`'s own `test_real_research_agent_installs.py`. A third
such bus stands in for `planning-engine`, the real external publisher of
`planning.task_graph.created` (TDD 3B §6.2) and consumer of
`agent_os.task.completed` (TDD 3E §10).

The model-gateway leg uses the same `FakeModelGatewayPort` already proven
against the real `InprocessExecutionBackend` in
`tests/unit/test_execution_backend.py` -- the `ModelGatewayClient` RPC
shape itself is already covered by `reasoning-engine`'s own
`ModelOrchestrationClient` precedent
(`test_model_orchestration_client_against_fake_gateway.py`), so re-proving
it here would only re-test an already-proven boundary, not the new thing
this test exists to prove: Kernel's Scheduler, RegistryClient, and
InprocessExecutionBackend wired together for real.
"""

from __future__ import annotations

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


class _FakeModelGatewayPort:
    def __init__(self, *, reply: GenerateReplyPayload) -> None:
        self._reply = reply

    async def generate(self, request: GenerateRequestPayload) -> GenerateReplyPayload:
        return self._reply


def _package_snapshot() -> AgentPackageSnapshot:
    """Matches, field-for-field, what Registry's own real install pipeline
    produces for `agents/research-agent/agent.yaml`, independently proven
    by `agent-os/registry`'s own `test_real_research_agent_installs.py`
    (`category == "research"`, `version == "0.1.0"`,
    `manifest_json["id"] == "research-agent"`, `health_status ==
    "healthy"`)."""
    return AgentPackageSnapshot(
        id=uuid4(),
        category="research",
        version="0.1.0",
        manifest_json={
            "id": "research-agent",
            "version": "0.1.0",
            "category": "research",
            "display_name": "Research Agent",
            "supported_execution_backends": ["inprocess"],
            "resource_profile": {"cpu": "standard", "memory": "standard", "gpu": "none"},
            "health_check": {"interval_seconds": 30},
            "compatibility": {"min_kernel_version": "0.1.0"},
        },
        health_status="healthy",
    )


async def test_full_loop_dispatches_the_real_research_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    shared_bus = InMemoryEventBus()
    monkeypatch.setattr("nova_agent_os_kernel.main.get_event_bus", lambda: shared_bus)

    package_snapshot = _package_snapshot()

    kernel_repository = FakeKernelRepository()
    primary_user_id = uuid4()
    gateway = _FakeModelGatewayPort(
        reply=GenerateReplyPayload(
            text="Token-bucket rate limiting is the standard approach.",
            input_tokens=10,
            output_tokens=12,
            finish_reason="stop",
            structural_confidence=0.9,
            model_id=uuid4(),
            provider="fake",
        )
    )
    execution_backend = InprocessExecutionBackend(
        agents_root=_REPO_ROOT / "agents", model_gateway=gateway
    )

    kernel_app = create_app(
        Settings(primary_user_id=primary_user_id),
        repository=kernel_repository,
        execution_backend=execution_backend,
    )

    async with kernel_app.router.lifespan_context(kernel_app):
        # Stand-in for `agent-os/registry`: answers the real Kernel's real
        # `RegistryClient` RPC with the exact snapshot Registry's own real
        # install pipeline is independently proven to produce.
        registry_stand_in = BoundEventBus(
            shared_bus,
            engine_name="registry",
            publishable_subjects=frozenset(),
            subscribable_subjects=frozenset(
                {"agent_os.registry.find_healthy_package.request"}
            ),
        )
        await registry_stand_in.connect()

        async def _answer_find_healthy_package(
            envelope: EventEnvelope,
        ) -> AgentOsFindHealthyPackageReplyPayload:
            payload = AgentOsFindHealthyPackageRequestPayload.model_validate(envelope.payload)
            if payload.category != package_snapshot.category:
                return AgentOsFindHealthyPackageReplyPayload(package=None)
            return AgentOsFindHealthyPackageReplyPayload(package=package_snapshot)

        await registry_stand_in.serve(
            "agent_os.registry.find_healthy_package.request",
            _answer_find_healthy_package,
            source_engine="registry",
        )

        # Stand-in for `planning-engine`: the real external publisher of
        # `planning.task_graph.created` and consumer of
        # `agent_os.task.completed`.
        planning_stand_in = BoundEventBus(
            shared_bus,
            engine_name="planning-engine",
            publishable_subjects=frozenset({"planning.task_graph.created"}),
            subscribable_subjects=frozenset({"agent_os.task.completed"}),
        )
        await planning_stand_in.connect()

        completed_events: list[EventEnvelope] = []

        async def _capture(envelope: EventEnvelope) -> None:
            completed_events.append(envelope)

        await planning_stand_in.subscribe("agent_os.task.completed", _capture)

        node = TaskNodeSnapshot(
            id=uuid4(),
            objective="Research rate limiting approaches",
            depends_on=[],
            assigned_agent_category="research",
            effort_hours=1.0,
            confidence=0.7,
            risk="low",
            status="ready",
        )
        graph = TaskGraphSnapshot(
            id=uuid4(),
            root_objective="Investigate rate limiting",
            nodes=[node],
            critical_path=[node.id],
        )
        correlation_id = uuid4()
        graph_payload = PlanningTaskGraphCreatedPayload(graph=graph, correlation_id=correlation_id)

        await planning_stand_in.publish(
            EventEnvelope(
                subject="planning.task_graph.created",
                source_engine="planning-engine",
                correlation_id=correlation_id,
                payload=graph_payload.model_dump(mode="json"),
            )
        )

        assert len(completed_events) == 1
        completed_payload = AgentOsTaskCompletedPayload.model_validate(
            completed_events[0].payload
        )
        assert completed_payload.task_node_id == node.id
        assert completed_payload.outcome == "success"

        persisted = await kernel_repository.find_by_id(completed_payload.agent_instance_id)
        assert persisted is not None
        assert persisted.status == "completed"
        assert persisted.category == "research"
        assert persisted.assigned_task_node_id == node.id
        assert persisted.agent_package_id == package_snapshot.id
