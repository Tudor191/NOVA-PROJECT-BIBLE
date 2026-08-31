"""Basic handler lifecycle test: a toy, fully-conforming `AgentHandler`
implementation walked through the doc 12 §5 sequence
(on_load -> on_assign -> execute -> self_validate -> health_check ->
metrics_snapshot -> on_unload), proving the Protocol is actually usable
end-to-end, not just structurally declarable."""

from __future__ import annotations

from uuid import uuid4

from nova_agent_sdk import (
    AgentContext,
    AgentHandler,
    AgentHealth,
    AgentManifest,
    AgentMetrics,
    AgentResult,
    ValidationOutcome,
)
from nova_contracts import (
    CapabilityHandle,
    KnowledgeReference,
    MemoryReference,
    PermissionSet,
    ResourceUsage,
    RiskLevel,
    TaskNodeSnapshot,
    WorldModelSnapshot,
)


class _ToyHandler(AgentHandler):
    def __init__(self) -> None:
        self.loaded_manifest: AgentManifest | None = None
        self.assigned_task: TaskNodeSnapshot | None = None
        self._tasks_completed = 0

    async def on_load(self, manifest: AgentManifest) -> None:
        self.loaded_manifest = manifest

    async def on_unload(self) -> None:
        self.loaded_manifest = None

    async def on_assign(self, task: TaskNodeSnapshot, context: AgentContext) -> None:
        self.assigned_task = task

    async def execute(self) -> AgentResult:
        assert self.assigned_task is not None
        self._tasks_completed += 1
        return AgentResult(
            agent_instance_id=uuid4(),
            task_node_id=self.assigned_task.id,
            status="success",
            output={"summary": "toy work complete"},
            confidence=0.9,
            self_validation_passed=True,
            correlation_id=uuid4(),
        )

    async def on_pause(self) -> None:
        pass

    async def on_resume(self) -> None:
        pass

    async def self_validate(self, result: AgentResult) -> ValidationOutcome:
        return ValidationOutcome(passed=result.status == "success", requires_peer_review=False)

    async def health_check(self) -> AgentHealth:
        return AgentHealth(
            status="healthy",
            latency_ms=5.0,
            error_rate=0.0,
            resource_usage=ResourceUsage(cpu_percent=1.0, memory_mb=64.0),
        )

    async def on_message(self, message: object) -> None:
        return None

    def metrics_snapshot(self) -> AgentMetrics:
        return AgentMetrics(
            tasks_completed=self._tasks_completed,
            tasks_failed=0,
            average_duration_ms=10.0,
            average_confidence=0.9,
            resource_efficiency=0.95,
        )


def _manifest() -> AgentManifest:
    return AgentManifest.model_validate(
        {
            "id": "toy-agent",
            "version": "0.1.0",
            "category": "qa",
            "display_name": "Toy Agent",
            "supported_execution_backends": ["inprocess"],
            "resource_profile": {"cpu": "standard", "memory": "standard", "gpu": "none"},
            "health_check": {"interval_seconds": 30},
            "compatibility": {"min_kernel_version": "0.1.0"},
        }
    )


def _context(task: TaskNodeSnapshot) -> AgentContext:
    return AgentContext(
        task=task,
        world_model_slice=WorldModelSnapshot(user_id=uuid4()),
        relevant_memory=[MemoryReference(memory_id=uuid4(), summary="prior run")],
        relevant_knowledge=[KnowledgeReference(node_id="kn-1", summary="relevant doc")],
        granted_permissions=PermissionSet(granted=["filesystem:write:project-scope"]),
        granted_capabilities=[
            CapabilityHandle(capability_id=uuid4(), name="git", execution_adapter="git")
        ],
        correlation_id=uuid4(),
    )


async def test_toy_handler_satisfies_the_agent_handler_protocol() -> None:
    assert isinstance(_ToyHandler(), AgentHandler)


async def test_full_lifecycle_walk() -> None:
    handler = _ToyHandler()
    manifest = _manifest()
    task = TaskNodeSnapshot(
        id=uuid4(),
        objective="prove the SDK lifecycle works",
        effort_hours=1.0,
        confidence=0.8,
        risk=RiskLevel.LOW,
        status="ready",
    )

    await handler.on_load(manifest)
    assert handler.loaded_manifest == manifest

    await handler.on_assign(task, _context(task))
    assert handler.assigned_task == task

    result = await handler.execute()
    assert result.status == "success"
    assert result.task_node_id == task.id

    outcome = await handler.self_validate(result)
    assert outcome.passed is True

    health = await handler.health_check()
    assert health.status == "healthy"

    metrics = handler.metrics_snapshot()
    assert metrics.tasks_completed == 1

    await handler.on_unload()
    assert handler.loaded_manifest is None
