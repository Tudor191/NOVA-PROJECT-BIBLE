"""TDD 3E §14 acceptance criterion #3, Kernel side: a real `create_app()`
dispatches against `coding-agent@1.1.0`, a Registry stand-in then begins
answering with `1.2.0` (the observable effect of a hot install, with **no
Kernel restart** -- the same `create_app()` and the same `lifespan_context`
stay open across both dispatches), and a second dispatch pins itself to
`1.2.0` while the first instance's row stays permanently pinned to
`1.1.0`'s package UUID.

**Scope, stated plainly (doc 16 §2, `docs/design/phase-3/
16-3e-hot-load-design-decision.md`): this is version pinning and
scheduling hot-load, NOT simultaneous execution of different bytecode
versions.** Phase 3's `InprocessExecutionBackend` resolves handler code by
the manifest's own `id` alone (`agents/coding-agent/src/handler.py` -- one
file per package, no per-version directory exists in this monorepo) and
runs an instance's entire lifecycle synchronously inside `spawn()`, so two
code bodies for one category can never execute concurrently in Phase 3.
Both dispatches below therefore run the *same* real `handler.py`; what
differs, and what criterion #3 actually turns on, is which
`agent_package` row each resulting `agent_instance` is pinned to via
`agent_package_id`.

Mirrors `test_full_loop_coding_agent_peer_review.py`'s own stand-in
conventions exactly -- a second `BoundEventBus` on the same underlying
`InMemoryEventBus` answers the Registry RPC, a third stands in for
`planning-engine`. The Registry stand-in's own reply is switched between
dispatches, which is precisely what a real hot install of `1.2.0` would
change about Registry's answers (proven independently, against the real
selection policy and the real served RPC, in `agent-os/registry`'s own
`tests/unit/test_selection.py` and
`tests/integration/test_events_find_healthy_package_request.py`)."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

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
    async def execute(self, request: ActionExecuteRequestPayload) -> ActionResultPayload:
        return ActionResultPayload(
            action_id=uuid4(), status="completed", result={"committed": True}, error=None
        )


class _FakeModelGatewayPort:
    async def generate(self, request: GenerateRequestPayload) -> GenerateReplyPayload:
        return GenerateReplyPayload(
            text="def add(a, b):\n    return a + b\n",
            input_tokens=20,
            output_tokens=15,
            finish_reason="stop",
            structural_confidence=0.9,
            model_id=uuid4(),
            provider="fake",
        )


def _coding_package(version: str) -> AgentPackageSnapshot:
    """Field-for-field what Registry's own real install pipeline produces
    for `agents/coding-agent/agent.yaml`, with `version` varied -- the one
    field a hot install of a new version actually changes. `peer_reviewer_category`
    is deliberately omitted so neither dispatch triggers a peer-review
    round; this test is about version pinning, and the peer-review path is
    already covered by `test_full_loop_coding_agent_architect_review.py`."""
    return AgentPackageSnapshot(
        id=uuid4(),
        category="coding",
        version=version,
        manifest_json={
            "id": "coding-agent",
            "version": version,
            "category": "coding",
            "display_name": "Coding Agent",
            "required_capabilities": ["filesystem"],
            "required_permissions": ["filesystem:write:project-scope"],
            "supported_execution_backends": ["inprocess"],
            "resource_profile": {"cpu": "standard", "memory": "standard", "gpu": "none"},
            "health_check": {"interval_seconds": 30},
            "compatibility": {"min_kernel_version": "0.1.0"},
        },
        health_status="healthy",
    )


def _task_node() -> TaskNodeSnapshot:
    return TaskNodeSnapshot(
        id=uuid4(),
        objective="Implement the add() helper",
        depends_on=[],
        assigned_agent_category="coding",
        effort_hours=1.0,
        confidence=0.8,
        risk="low",
        status="ready",
    )


async def test_hot_load_pins_each_instance_to_the_version_it_dispatched_against(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    shared_bus = InMemoryEventBus()
    monkeypatch.setattr("nova_agent_os_kernel.main.get_event_bus", lambda: shared_bus)

    v110 = _coding_package("1.1.0")
    v120 = _coding_package("1.2.0")
    # What Registry currently answers with. A real hot install of 1.2.0 is
    # exactly what flips this -- Registry's own selection policy then
    # returns the newest healthy row (proven in that component's own tests).
    served: dict[str, AgentPackageSnapshot] = {"package": v110}

    kernel_repository = FakeKernelRepository()
    execution_backend = InprocessExecutionBackend(
        agents_root=_REPO_ROOT / "agents",
        model_gateway=_FakeModelGatewayPort(),
        action_port=_FakeActionPort(),
    )
    kernel_app = create_app(
        Settings(primary_user_id=uuid4()),
        repository=kernel_repository,
        execution_backend=execution_backend,
    )

    # One Kernel process, one lifespan, spanning BOTH dispatches -- the
    # "without a kernel restart" half of criterion #3.
    async with kernel_app.router.lifespan_context(kernel_app):
        registry_stand_in = BoundEventBus(
            shared_bus,
            engine_name="registry",
            publishable_subjects=frozenset(),
            subscribable_subjects=frozenset({"agent_os.registry.find_healthy_package.request"}),
        )
        await registry_stand_in.connect()

        async def _answer(envelope: EventEnvelope) -> AgentOsFindHealthyPackageReplyPayload:
            payload = AgentOsFindHealthyPackageRequestPayload.model_validate(envelope.payload)
            if payload.category != "coding":
                return AgentOsFindHealthyPackageReplyPayload(package=None)
            return AgentOsFindHealthyPackageReplyPayload(package=served["package"])

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
        completed: list[AgentOsTaskCompletedPayload] = []

        async def _capture(envelope: EventEnvelope) -> None:
            completed.append(AgentOsTaskCompletedPayload.model_validate(envelope.payload))

        await planning_stand_in.subscribe("agent_os.task.completed", _capture)

        async def _dispatch(node: TaskNodeSnapshot) -> None:
            graph = TaskGraphSnapshot(
                id=uuid4(),
                root_objective="Ship the helper",
                nodes=[node],
                critical_path=[node.id],
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

        # --- Dispatch 1: only 1.1.0 is installed --------------------------
        first_node = _task_node()
        await _dispatch(first_node)

        assert len(completed) == 1
        first_instance_id = completed[0].agent_instance_id
        first_instance = await kernel_repository.find_by_id(first_instance_id)
        assert first_instance is not None
        assert first_instance.agent_package_id == v110.id

        # Snapshot the first instance's row before the hot install, so the
        # "never mutated" assertion below compares against real prior state.
        first_instance_before: dict = first_instance.model_dump(mode="json")

        # --- Hot install of 1.2.0: no Kernel restart, no app rebuild -----
        served["package"] = v120

        # --- Dispatch 2: 1.2.0 is now the selected version ----------------
        second_node = _task_node()
        await _dispatch(second_node)

        assert len(completed) == 2
        second_instance_id = completed[1].agent_instance_id
        second_instance = await kernel_repository.find_by_id(second_instance_id)
        assert second_instance is not None

    # New dispatch selects 1.2.0.
    assert second_instance.agent_package_id == v120.id
    assert second_instance.assigned_task_node_id == second_node.id

    # The pre-existing instance is still pinned to 1.1.0 -- never migrated,
    # never re-resolved, never invalidated by the newer install.
    reread_first = await kernel_repository.find_by_id(first_instance_id)
    assert reread_first is not None
    assert reread_first.agent_package_id == v110.id
    assert reread_first.model_dump(mode="json") == first_instance_before

    # Two distinct instances, two distinct package pins, one Kernel process.
    assert first_instance_id != second_instance_id
    assert isinstance(reread_first.agent_package_id, UUID)
    assert reread_first.agent_package_id != second_instance.agent_package_id


async def test_a_dispatch_falls_back_to_the_older_version_registry_still_reports_healthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kernel side of the fallback case: Registry answering with 1.1.0
    (because 1.2.0's own `on_load` failed and left it non-healthy -- that
    selection decision is Registry's own, proven in its own tests) results
    in a dispatch pinned to 1.1.0. Kernel itself is version-agnostic: it
    dispatches whatever healthy package Registry names."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    shared_bus = InMemoryEventBus()
    monkeypatch.setattr("nova_agent_os_kernel.main.get_event_bus", lambda: shared_bus)

    v110 = _coding_package("1.1.0")
    kernel_repository = FakeKernelRepository()
    kernel_app = create_app(
        Settings(primary_user_id=uuid4()),
        repository=kernel_repository,
        execution_backend=InprocessExecutionBackend(
            agents_root=_REPO_ROOT / "agents",
            model_gateway=_FakeModelGatewayPort(),
            action_port=_FakeActionPort(),
        ),
    )

    async with kernel_app.router.lifespan_context(kernel_app):
        registry_stand_in = BoundEventBus(
            shared_bus,
            engine_name="registry",
            publishable_subjects=frozenset(),
            subscribable_subjects=frozenset({"agent_os.registry.find_healthy_package.request"}),
        )
        await registry_stand_in.connect()

        async def _answer(envelope: EventEnvelope) -> AgentOsFindHealthyPackageReplyPayload:
            return AgentOsFindHealthyPackageReplyPayload(package=v110)

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
        completed: list[AgentOsTaskCompletedPayload] = []

        async def _capture(envelope: EventEnvelope) -> None:
            completed.append(AgentOsTaskCompletedPayload.model_validate(envelope.payload))

        await planning_stand_in.subscribe("agent_os.task.completed", _capture)

        node = _task_node()
        graph = TaskGraphSnapshot(
            id=uuid4(), root_objective="Ship it", nodes=[node], critical_path=[node.id]
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

    assert len(completed) == 1
    instance = await kernel_repository.find_by_id(completed[0].agent_instance_id)
    assert instance is not None
    assert instance.agent_package_id == v110.id
