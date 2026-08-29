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
`assigned_agent_category` at all, is a disclosed, logged no-op -- this
Scheduler is generic per doc 12 §7 ("does not know what a Coding Agent
does"), so it does not special-case any agent category.

**Peer review, disclosed addition (coding-agent slice).** A successful
primary result whose `ValidationOutcome.requires_peer_review` is `True`
now triggers a review round before `agent_os.task.completed` is
published: the Scheduler reads the dispatched package's own
`AgentManifest.peer_reviewer_category` (disclosed addition,
`agent-os/sdk/python`), resolves a healthy reviewer package via the same
`RegistryPort` used for the primary dispatch, and delivers a
`PEER_REVIEW_REQUEST` via the execution backend's own `spawn_and_review()`
(see `domain/execution_backend.py`'s own module docstring for why this,
not a live Agent Mailbox `send()`, is how Phase 3's synchronous backend
delivers it). The raw outcome -- not a Kernel-computed verdict -- is
reported to the Supervisor (`SupervisorPort.record_peer_review()`), which
owns the accept/reject classification and Decision Memory recording (doc
12 §9), matching this module's own established "Kernel does dispatch
mechanics, the Supervisor owns restart/review policy" split. A `rejected`
verdict republishes as `outcome="needs_revision"` (`AgentResult.status`'s
own vocabulary, TDD 3E §12); `approved`/`not_required`/`timed_out` all
finalize as `"success"` -- TDD 3E §12's own "Supervisor proceeds with the
primary result" language for a timed-out or missing reviewer, extended
here to also cover "no `architect-agent` package installed yet," the
concrete case this project's own roadmap sequencing (`coding-agent` before
`architect-agent`) produces. No agent's manifest declares
`peer_reviewer_category` other than `coding-agent`'s own -- every other
Phase 3 agent's dispatch is entirely unaffected by this addition.

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
from typing import Literal
from uuid import UUID, uuid4

from nova_agent_sdk import AgentContext
from nova_contracts import (
    AgentMessage,
    AgentMessageType,
    AgentOsTaskCompletedPayload,
    AgentPackageSnapshot,
    AgentResult,
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


async def _run_peer_review(
    *,
    primary_result: AgentResult,
    reviewer_category: str,
    registry_port: RegistryPort,
    supervisor_port: SupervisorPort,
    execution_backend: AgentExecutionBackend,
    correlation_id: UUID,
) -> Literal["approved", "rejected", "timed_out", "not_required"]:
    """One peer-review round for a successful primary result whose package
    declares `peer_reviewer_category` -- see this module's own docstring
    for the full disclosure. `reviewer_available=False` covers both "no
    healthy reviewer package installed" and "the reviewer's own
    `on_message()` raised/returned no `PEER_REVIEW_RESULT`"."""
    reviewer_package = await registry_port.find_healthy_package(
        category=reviewer_category, correlation_id=correlation_id
    )
    reviewer_result: AgentResult | None = None
    reviewer_available = False

    if reviewer_package is not None:
        request = AgentMessage(
            message_type=AgentMessageType.PEER_REVIEW_REQUEST,
            from_instance_id=primary_result.agent_instance_id,
            to_instance_id=uuid4(),
            payload=primary_result.model_dump(mode="json"),
            correlation_id=correlation_id,
        )
        reply = await execution_backend.spawn_and_review(reviewer_package, request)
        if reply is not None and reply.message_type is AgentMessageType.PEER_REVIEW_RESULT:
            reviewer_result = AgentResult.model_validate(reply.payload)
            reviewer_available = True

    return await supervisor_port.record_peer_review(
        primary_result=primary_result,
        reviewer_category=reviewer_category,
        reviewer_result=reviewer_result,
        reviewer_available=reviewer_available,
        correlation_id=correlation_id,
    )


async def _finalize_outcome(
    *,
    node: TaskNodeSnapshot,
    instance: AgentInstance,
    handle: AgentInstanceHandle,
    outcome: str,
    package: AgentPackageSnapshot,
    registry_port: RegistryPort,
    supervisor_port: SupervisorPort,
    execution_backend: AgentExecutionBackend,
    event_publisher: EventPublisher,
    correlation_id: UUID,
) -> None:
    """Publishes `agent_os.task.completed`, first running a peer-review
    round (see this module's own docstring) when `outcome == "success"`
    and the dispatched package declares `peer_reviewer_category`. A
    `rejected` verdict republishes as `outcome="needs_revision"`; every
    other verdict (`approved`/`not_required`/`timed_out`) finalizes as
    `"success"`, matching TDD 3E §12's own non-fatal treatment of a
    missing or unresponsive reviewer."""
    result_dict = handle.result.model_dump(mode="json") if handle.result is not None else None
    final_outcome = outcome

    reviewer_category = package.manifest_json.get("peer_reviewer_category")
    if outcome == "success" and handle.result is not None and reviewer_category is not None:
        peer_validation = await _run_peer_review(
            primary_result=handle.result,
            reviewer_category=reviewer_category,
            registry_port=registry_port,
            supervisor_port=supervisor_port,
            execution_backend=execution_backend,
            correlation_id=correlation_id,
        )
        final_outcome = "needs_revision" if peer_validation == "rejected" else "success"
        if result_dict is not None:
            result_dict = {**result_dict, "peer_validation": peer_validation}

    await _publish_task_completed(
        event_publisher=event_publisher,
        task_node_id=node.id,
        agent_instance_id=instance.id,
        outcome=final_outcome,
        result=result_dict,
        correlation_id=correlation_id,
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


async def _spawn_tracked(
    package: AgentPackageSnapshot,
    context: AgentContext,
    *,
    node: TaskNodeSnapshot,
    category: str,
    repository: KernelRepository,
    execution_backend: AgentExecutionBackend,
) -> tuple[AgentInstanceHandle, AgentInstance]:
    """Runs one instance through the backend with its `agent_instance` row
    persisted as `"running"` **before** `spawn()` is awaited, then updated to
    its terminal status afterwards.

    Writing the row first is what makes TDD 3E §4's restart reconciliation
    actually reachable: it re-queues "every `agent_instance` row still marked
    `status="running"`" on Kernel startup, but until now no row was ever
    written in that state -- `spawn()` is synchronous, so rows were inserted
    already terminal and a Kernel killed mid-dispatch left nothing to
    recover. The instance id is minted by the backend, so the row is created
    from `spawn()`'s own handle; to have the id before the work starts, the
    backend now mints it up front (`AgentExecutionBackend.next_instance_id`)
    and `spawn()` reuses it.

    A crash between the two writes leaves exactly the row reconciliation is
    designed to find -- `"running"` with an `assigned_task_node_id` -- which
    is the correct, recoverable outcome rather than a lost assignment."""
    instance_id = execution_backend.next_instance_id()
    instance = AgentInstance(
        id=instance_id,
        agent_package_id=package.id,
        category=category,
        execution_backend="inprocess",
        status="running",
        assigned_task_node_id=node.id,
        started_at=datetime.now(UTC),
        health_status="unknown",
    )
    await repository.insert(instance)

    handle = await execution_backend.spawn(package, context, instance_id=instance_id)
    needs_restart, _outcome = _handle_outcome(handle)

    terminal_status = "failed" if needs_restart else "completed"
    terminal_health = "unhealthy" if needs_restart else "healthy"
    await repository.update_status(
        instance.id, status=terminal_status, health_status=terminal_health
    )
    return handle, instance.model_copy(
        update={"status": terminal_status, "health_status": terminal_health}
    )


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
    handle, instance = await _spawn_tracked(
        package,
        context,
        node=node,
        category=category,
        repository=repository,
        execution_backend=execution_backend,
    )
    needs_restart, outcome = _handle_outcome(handle)

    if not needs_restart:
        await _finalize_outcome(
            node=node,
            instance=instance,
            handle=handle,
            outcome=outcome,
            package=package,
            registry_port=registry_port,
            supervisor_port=supervisor_port,
            execution_backend=execution_backend,
            event_publisher=event_publisher,
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
        await _finalize_outcome(
            node=node,
            instance=instance,
            handle=handle,
            outcome=outcome,
            package=package,
            registry_port=registry_port,
            supervisor_port=supervisor_port,
            execution_backend=execution_backend,
            event_publisher=event_publisher,
            correlation_id=correlation_id,
        )
        return instance.id

    # Bounded, single retry -- never re-consults the Supervisor a second time.
    retry_handle, retry_instance = await _spawn_tracked(
        package,
        context,
        node=node,
        category=category,
        repository=repository,
        execution_backend=execution_backend,
    )
    _retry_needs_restart, retry_outcome = _handle_outcome(retry_handle)
    await _finalize_outcome(
        node=node,
        instance=retry_instance,
        handle=retry_handle,
        outcome=retry_outcome,
        package=package,
        registry_port=registry_port,
        supervisor_port=supervisor_port,
        execution_backend=execution_backend,
        event_publisher=event_publisher,
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
