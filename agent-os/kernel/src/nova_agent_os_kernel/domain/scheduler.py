"""Kernel Scheduler (TDD 3E §4, doc 12 §7) -- disclosed implementation:
this milestone's own `events/subscribed.py` docstring flagged
`planning.task_graph.created` consumption and dispatch-loop behavior as "not
implemented here." This module is that follow-up.

For each `TaskNodeSnapshot` in a published `TaskGraphSnapshot` with
`status == "ready"` and `assigned_agent_category` set: (1) query Registry
for a healthy candidate package in that category (`RegistryPort`); (2)
build the instance's `AgentContext`; (3) dispatch via the (Phase 3, sole)
`inprocess` backend (`AgentExecutionBackend`); (4) persist an
`agent_instance` row; (5) on failure, ask the owning Supervisor for a
restart plan (`SupervisorPort`, TDD 3E §12's failure table) and retry
**once**, bounded -- no unbounded restart loop. Publishes
`agent_os.task.completed` either way.

A `TaskNode` with no healthy candidate in Registry, or no
`assigned_agent_category` at all, is a disclosed, logged no-op -- Phase 3
ships exactly one Agent Package category that can ever resolve
(`research-agent`); the other four Phase 3E TDD §9 categories are not yet
built, and this Scheduler is generic per doc 12 §7 ("does not know what a
Coding Agent does"), so it does not special-case any of them.

**`AgentContext` construction, disclosed.** TDD 3E §4's own Kernel
Scheduler design describes registry-query/score/backend-select/dispatch
only -- it names no mechanism for pre-scoping `relevant_memory`/
`relevant_knowledge` (doc 12 §4's own "an agent receives a pre-scoped
`AgentContext`"). No `memory-engine`/`knowledge-engine` RPC integration is
built here -- both lists are empty, real, typed, and disclosed, not a
placeholder hack; `world_model_slice` is likewise never queried from
`world-model-engine`, so `WorldModelSnapshot.degraded=True` is always set
(the same "proceed without... reduced-confidence grounding" semantics
`ContextReplyPayload.degraded` already establishes). `granted_permissions`/
`granted_capabilities` are both empty -- Fork 3C-2's own resolution
already established that `granted_capabilities` has no runtime population
mechanism in Phase 3E, and Phase 3's own Permission Review resolution
(`15-3e-supervisor-reconciliation.md` predecessor, TDD 3E §5/§8a) is
declared-intent-only, matching every other agent-os component's identical
treatment of that same gap.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from nova_agent_sdk import AgentContext
from nova_contracts import (
    AgentOsTaskCompletedPayload,
    EventEnvelope,
    PermissionSet,
    TaskGraphSnapshot,
    TaskNodeSnapshot,
    WorldModelSnapshot,
)
from nova_observability import get_logger

from nova_agent_os_kernel.domain.models import AgentInstance, AgentInstanceHandle
from nova_agent_os_kernel.domain.ports import (
    AgentExecutionBackend,
    EventPublisher,
    KernelRepository,
    RegistryPort,
    SupervisorPort,
)

__all__ = ["dispatch_ready_nodes", "dispatch_task_node"]

logger = get_logger("kernel.scheduler")

_SOURCE_ENGINE = "kernel"


def _build_context(
    node: TaskNodeSnapshot, *, primary_user_id: UUID, correlation_id: UUID
) -> AgentContext:
    return AgentContext(
        task=node,
        world_model_slice=WorldModelSnapshot(user_id=primary_user_id, degraded=True),
        relevant_memory=[],
        relevant_knowledge=[],
        granted_permissions=PermissionSet(granted=[]),
        granted_capabilities=[],
        correlation_id=correlation_id,
    )


async def _publish_task_completed(
    *,
    event_publisher: EventPublisher,
    task_node_id: UUID,
    agent_instance_id: UUID,
    outcome: str,
    result: dict | None,
    correlation_id: UUID,
) -> None:
    payload = AgentOsTaskCompletedPayload(
        task_node_id=task_node_id,
        agent_instance_id=agent_instance_id,
        outcome=outcome,
        result=result,
        correlation_id=correlation_id,
    )
    await event_publisher.publish(
        EventEnvelope(
            subject="agent_os.task.completed",
            source_engine=_SOURCE_ENGINE,
            correlation_id=correlation_id,
            payload=payload.model_dump(mode="json"),
        )
    )


def _handle_outcome(handle: AgentInstanceHandle) -> tuple[bool, str]:
    """`(needs_restart, outcome)` -- `needs_restart` is true only for a
    genuine crash/self-validation failure (TDD 3E §12's "instance crashes
    mid-task" row), never for a normally-produced `"needs_revision"`
    result (a peer-review quality signal, not an instance fault -- no Phase
    3 agent's own scripted behavior produces one, TDD 3E §9, but the
    distinction is preserved for architectural correctness)."""
    if handle.error is not None:
        return True, "failure"
    assert handle.result is not None
    if handle.result.status == "failure" or (
        handle.validation is not None and not handle.validation.passed
    ):
        return True, handle.result.status
    return False, handle.result.status


async def dispatch_task_node(
    node: TaskNodeSnapshot,
    *,
    repository: KernelRepository,
    registry_port: RegistryPort,
    supervisor_port: SupervisorPort,
    execution_backend: AgentExecutionBackend,
    event_publisher: EventPublisher,
    primary_user_id: UUID,
    correlation_id: UUID,
) -> UUID | None:
    """Dispatches one ready `TaskNode`. Returns the final `agent_instance`
    id if a dispatch attempt was made (success or failure), `None` if
    nothing was dispatched at all (no category assigned, or no healthy
    Registry candidate)."""
    if node.assigned_agent_category is None:
        return None
    category = node.assigned_agent_category

    package = await registry_port.find_healthy_package(
        category=category, correlation_id=correlation_id
    )
    if package is None:
        logger.info(
            "no healthy agent_package candidate for category %r -- task_node %s left undispatched",
            category,
            node.id,
        )
        return None

    context = _build_context(node, primary_user_id=primary_user_id, correlation_id=correlation_id)
    handle = await execution_backend.spawn(package, context)
    needs_restart, outcome = _handle_outcome(handle)

    instance = AgentInstance(
        id=handle.instance_id,
        agent_package_id=package.id,
        category=category,
        execution_backend="inprocess",
        status="failed" if needs_restart else "completed",
        assigned_task_node_id=node.id,
        started_at=datetime.now(UTC),
        health_status="unhealthy" if needs_restart else "healthy",
    )
    await repository.insert(instance)

    if not needs_restart:
        await _publish_task_completed(
            event_publisher=event_publisher,
            task_node_id=node.id,
            agent_instance_id=instance.id,
            outcome=outcome,
            result=handle.result.model_dump(mode="json") if handle.result else None,
            correlation_id=correlation_id,
        )
        return instance.id

    restart_ids = await supervisor_port.plan_restart(
        failed_instance_id=instance.id,
        category=category,
        siblings=[instance],
        correlation_id=correlation_id,
    )
    if instance.id not in restart_ids:
        await _publish_task_completed(
            event_publisher=event_publisher,
            task_node_id=node.id,
            agent_instance_id=instance.id,
            outcome=outcome,
            result=handle.result.model_dump(mode="json") if handle.result else None,
            correlation_id=correlation_id,
        )
        return instance.id

    # Bounded, single retry -- never re-consults the Supervisor a second time.
    retry_handle = await execution_backend.spawn(package, context)
    retry_needs_restart, retry_outcome = _handle_outcome(retry_handle)
    retry_instance = AgentInstance(
        id=retry_handle.instance_id,
        agent_package_id=package.id,
        category=category,
        execution_backend="inprocess",
        status="failed" if retry_needs_restart else "completed",
        assigned_task_node_id=node.id,
        started_at=datetime.now(UTC),
        health_status="unhealthy" if retry_needs_restart else "healthy",
    )
    await repository.insert(retry_instance)
    await _publish_task_completed(
        event_publisher=event_publisher,
        task_node_id=node.id,
        agent_instance_id=retry_instance.id,
        outcome=retry_outcome,
        result=retry_handle.result.model_dump(mode="json") if retry_handle.result else None,
        correlation_id=correlation_id,
    )
    return retry_instance.id


async def dispatch_ready_nodes(
    graph: TaskGraphSnapshot,
    *,
    repository: KernelRepository,
    registry_port: RegistryPort,
    supervisor_port: SupervisorPort,
    execution_backend: AgentExecutionBackend,
    event_publisher: EventPublisher,
    primary_user_id: UUID,
    correlation_id: UUID,
) -> list[UUID]:
    """Dispatches every `status == "ready"` node in `graph`. Independent
    nodes are dispatched sequentially here (Phase 3's own `inprocess`
    backend has no concurrency mechanism yet -- doc 12 §7's "Parallel
    dispatch" is `already-designed-for`, not shipped, per doc 12 §15's own
    table); each still gets its own, independent `agent_instance` row and
    completion event."""
    dispatched: list[UUID] = []
    for node in graph.nodes:
        if node.status != "ready":
            continue
        instance_id = await dispatch_task_node(
            node,
            repository=repository,
            registry_port=registry_port,
            supervisor_port=supervisor_port,
            execution_backend=execution_backend,
            event_publisher=event_publisher,
            primary_user_id=primary_user_id,
            correlation_id=correlation_id,
        )
        if instance_id is not None:
            dispatched.append(instance_id)
    return dispatched
