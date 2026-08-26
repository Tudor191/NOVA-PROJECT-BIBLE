"""End-to-end proof of the documentation-agent slice: a real Kernel
`create_app()` (real Scheduler, real `RegistryClient` RPC, real
`InprocessExecutionBackend`) dispatches through the real
`agents/documentation-agent/src/handler.py` Handler -- mirrors
`test_full_loop_qa_agent.py`'s own structure and stand-in conventions
exactly, using both a `FakeModelGatewayPort` and a `FakeActionPort`
(documentation-agent's own `execute()` uses both, TDD 3E §9's own sentence
names both steps: generate content, then write it).

No Supervisors app is involved here, identical to `qa-agent`'s own
full-loop test -- `documentation-agent`'s manifest declares no
`peer_reviewer_category` (TDD 3E §9's own agent table gives it no
reviewer/reviewee role), so `dispatch_task_node()` never calls
`SupervisorPort.record_peer_review()` for a successful dispatch."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from nova_agent_os_kernel.config import Settings
from nova_agent_os_kernel.domain.execution_backend import InprocessExecutionBackend
from nova_agent_os_kernel.main import create_app
from nova_contracts import (
    ActionExecuteRequestPayload,
    ActionResultPayload,
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


class _FakeActionPort:
    def __init__(self, *, reply: ActionResultPayload) -> None:
        self._reply = reply

    async def execute(self, request: ActionExecuteRequestPayload) -> ActionResultPayload:
        return self._reply


class _FakeModelGatewayPort:
    def __init__(self, *, reply: GenerateReplyPayload) -> None:
        self._reply = reply

    async def generate(self, request: GenerateRequestPayload) -> GenerateReplyPayload:
        return self._reply


def _package_snapshot() -> AgentPackageSnapshot:
    """Matches, field-for-field, what Registry's own real install pipeline
    produces for `agents/documentation-agent/agent.yaml`, independently
    proven by `agent-os/registry`'s own
    `test_real_documentation_agent_installs.py`."""
    return AgentPackageSnapshot(
        id=uuid4(),
        category="documentation",
        version="0.1.0",
        manifest_json={
            "id": "documentation-agent",
            "version": "0.1.0",
            "category": "documentation",
            "display_name": "Documentation Agent",
            "required_capabilities": ["filesystem"],
            "required_permissions": ["filesystem:write:project-scope"],
            "supported_execution_backends": ["inprocess"],
            "resource_profile": {"cpu": "standard", "memory": "standard", "gpu": "none"},
            "health_check": {"interval_seconds": 30},
            "compatibility": {"min_kernel_version": "0.1.0"},
        },
        health_status="healthy",
    )


async def test_full_loop_dispatches_the_real_documentation_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    shared_bus = InMemoryEventBus()
    monkeypatch.setattr("nova_agent_os_kernel.main.get_event_bus", lambda: shared_bus)

    package_snapshot = _package_snapshot()

    kernel_repository = FakeKernelRepository()
    primary_user_id = uuid4()
    action_port = _FakeActionPort(
        reply=ActionResultPayload(
            action_id=uuid4(), status="completed", result={"content": "written"}, error=None
        )
    )
    gateway = _FakeModelGatewayPort(
        reply=GenerateReplyPayload(
            text="# Rate Limiting\n\nConfigure `max_requests`.",
            input_tokens=20,
            output_tokens=15,
            finish_reason="stop",
            structural_confidence=0.9,
            model_id=uuid4(),
            provider="fake",
        )
    )
    execution_backend = InprocessExecutionBackend(
        agents_root=_REPO_ROOT / "agents",
        model_gateway=gateway,
        action_port=action_port,
    )

    kernel_app = create_app(
        Settings(primary_user_id=primary_user_id),
        repository=kernel_repository,
        execution_backend=execution_backend,
    )

    async with kernel_app.router.lifespan_context(kernel_app):
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
            objective="Document the rate-limiting middleware's configuration options",
            depends_on=[],
            assigned_agent_category="documentation",
            effort_hours=1.0,
            confidence=0.8,
            risk="low",
            status="ready",
        )
        graph = TaskGraphSnapshot(
            id=uuid4(),
            root_objective="Ship rate limiting",
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
        assert completed_payload.result is not None
        assert completed_payload.result["output"]["content"] == (
            "# Rate Limiting\n\nConfigure `max_requests`."
        )
        assert "peer_validation" not in completed_payload.result

        persisted = await kernel_repository.find_by_id(completed_payload.agent_instance_id)
        assert persisted is not None
        assert persisted.status == "completed"
        assert persisted.category == "documentation"
        assert persisted.assigned_task_node_id == node.id
        assert persisted.agent_package_id == package_snapshot.id
