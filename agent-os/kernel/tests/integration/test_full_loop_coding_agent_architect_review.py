"""End-to-end proof of a **real** peer-review round: a real Kernel
`create_app()` dispatches through the real `agents/coding-agent/src/handler.py`
Handler, then a real Supervisors `create_app()` runs a real peer-review
round through the real `agents/architect-agent/src/handler.py` Handler --
closes the loop `test_full_loop_coding_agent_peer_review.py`'s own
"no healthy architect-agent candidate" edge case left open, and is the
concrete instance of TDD 3E §14's acceptance criterion 1 ("at least one
real peer-review round (`architect-agent` reviewing `coding-agent`'s
output)").

Same structure and stand-in conventions as
`test_full_loop_coding_agent_peer_review.py` -- real Kernel + real
Supervisors bound to the same shared in-memory bus, a Registry stand-in
answering the real `RegistryClient` RPC -- except this Registry stand-in
now resolves **both** `category="coding"` and `category="architect"` to
their real, installed package snapshots (independently proven by
`agent-os/registry`'s own `test_real_coding_agent_installs.py` and
`test_real_architect_agent_installs.py`), so `spawn_and_review()` actually
constructs and drives a real `architect-agent` Handler instance instead of
finding no candidate.

Only the approve path is exercised here: `coding-agent`'s own `execute()`
always sets `self_validation_passed` equal to `status == "success"` (see
that Handler's own source) -- there is no way for the *real* coding-agent
Handler to produce a self-inconsistent result, which is exactly the only
input `architect-agent`'s own scripted rule rejects (see
`agents/architect-agent/src/handler.py`'s own `_review()`). The reject
path is therefore proven directly against a hand-built, self-inconsistent
`AgentResult` fixture instead -- `tests/unit/test_execution_backend.py`'s
own `test_spawn_and_review_produces_a_real_rejected_verdict_...` and
`agents/architect-agent/tests/test_handler.py`'s own
`test_peer_review_request_rejects_...` tests -- since no real Phase 3
agent can organically produce the input that verdict requires.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from nova_agent_os_kernel.config import Settings
from nova_agent_os_kernel.domain.execution_backend import InprocessExecutionBackend
from nova_agent_os_kernel.main import create_app
from nova_agent_os_supervisors.main import create_app as create_supervisors_app
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


class _UnusedModelGatewayPort:
    """Neither `coding-agent`'s nor `architect-agent`'s own `execute()`/
    `on_message()` call `model_gateway` -- this stand-in exists only to
    satisfy `InprocessExecutionBackend`'s own constructor type, and raises
    if that assumption ever stops holding."""

    async def generate(self, request: GenerateRequestPayload) -> GenerateReplyPayload:
        raise AssertionError("neither coding-agent nor architect-agent calls model_gateway")


class _RecordingDecisionMemoryPort:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def record(
        self,
        *,
        objective: str,
        alternatives: list[str],
        chosen_alternative: str,
        reasoning: str,
        correlation_id: UUID,
    ) -> None:
        self.calls.append({"objective": objective, "correlation_id": correlation_id})


def _coding_agent_package_snapshot() -> AgentPackageSnapshot:
    """Matches, field-for-field, what Registry's own real install pipeline
    produces for `agents/coding-agent/agent.yaml`, independently proven by
    `agent-os/registry`'s own `test_real_coding_agent_installs.py`."""
    return AgentPackageSnapshot(
        id=uuid4(),
        category="coding",
        version="0.1.0",
        manifest_json={
            "id": "coding-agent",
            "version": "0.1.0",
            "category": "coding",
            "display_name": "Coding Agent",
            "required_capabilities": ["git", "filesystem", "terminal"],
            "required_permissions": ["filesystem:write:project-scope", "terminal:execute"],
            "supported_execution_backends": ["inprocess"],
            "resource_profile": {"cpu": "standard", "memory": "standard", "gpu": "none"},
            "health_check": {"interval_seconds": 30},
            "compatibility": {"min_kernel_version": "0.1.0"},
            "peer_reviewer_category": "architect",
        },
        health_status="healthy",
    )


def _architect_agent_package_snapshot() -> AgentPackageSnapshot:
    """Matches, field-for-field, what Registry's own real install pipeline
    produces for `agents/architect-agent/agent.yaml`, independently proven
    by `agent-os/registry`'s own `test_real_architect_agent_installs.py`."""
    return AgentPackageSnapshot(
        id=uuid4(),
        category="architect",
        version="0.1.0",
        manifest_json={
            "id": "architect-agent",
            "version": "0.1.0",
            "category": "architect",
            "display_name": "Architect Agent",
            "required_capabilities": [],
            "required_permissions": [],
            "supported_execution_backends": ["inprocess"],
            "resource_profile": {"cpu": "standard", "memory": "standard", "gpu": "none"},
            "health_check": {"interval_seconds": 30},
            "compatibility": {"min_kernel_version": "0.1.0"},
        },
        health_status="healthy",
    )


async def test_full_loop_architect_agent_really_reviews_and_approves_coding_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    shared_bus = InMemoryEventBus()
    monkeypatch.setattr("nova_agent_os_kernel.main.get_event_bus", lambda: shared_bus)
    monkeypatch.setattr("nova_agent_os_supervisors.main.get_event_bus", lambda: shared_bus)

    coding_package = _coding_agent_package_snapshot()
    architect_package = _architect_agent_package_snapshot()
    packages_by_category = {
        coding_package.category: coding_package,
        architect_package.category: architect_package,
    }

    kernel_repository = FakeKernelRepository()
    primary_user_id = uuid4()
    action_port = _FakeActionPort(
        reply=ActionResultPayload(
            action_id=uuid4(), status="completed", result={"content": "written"}, error=None
        )
    )
    execution_backend = InprocessExecutionBackend(
        agents_root=_REPO_ROOT / "agents",
        model_gateway=_UnusedModelGatewayPort(),
        action_port=action_port,
    )

    kernel_app = create_app(
        Settings(primary_user_id=primary_user_id),
        repository=kernel_repository,
        execution_backend=execution_backend,
    )
    decision_memory = _RecordingDecisionMemoryPort()
    supervisors_app = create_supervisors_app(decision_memory_port=decision_memory)

    async with (
        kernel_app.router.lifespan_context(kernel_app),
        supervisors_app.router.lifespan_context(supervisors_app),
    ):
        # Stand-in for `agent-os/registry`: answers the real Kernel's real
        # `RegistryClient` RPC for both `category="coding"` (the primary
        # dispatch) and `category="architect"` (the reviewer resolution),
        # each with its own real, installed package snapshot.
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
            package = packages_by_category.get(payload.category)
            return AgentOsFindHealthyPackageReplyPayload(package=package)

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
            objective="Add a rate-limiting middleware to the API gateway",
            depends_on=[],
            assigned_agent_category="coding",
            effort_hours=2.0,
            confidence=0.7,
            risk="moderate",
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
        assert completed_payload.result["peer_validation"] == "approved"

        persisted = await kernel_repository.find_by_id(completed_payload.agent_instance_id)
        assert persisted is not None
        assert persisted.status == "completed"
        assert persisted.category == "coding"
        assert persisted.assigned_task_node_id == node.id
        assert persisted.agent_package_id == coding_package.id

        assert len(decision_memory.calls) == 1
        assert decision_memory.calls[0]["correlation_id"] == correlation_id
