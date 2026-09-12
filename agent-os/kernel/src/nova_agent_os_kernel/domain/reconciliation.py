"""Kernel restart reconciliation (TDD 3E §4, §12) -- the one piece of
Scheduler-adjacent behavior this milestone's minimal, health-only Kernel
skeleton does implement, because doc 12 §12's own failure table treats it
as a Kernel-startup correctness property, not a dispatch feature: "Kernel
process itself restarts | §4's `agent_instance` reconciliation -- every
`"running"` row is re-queued." No `planning.task_graph.created` consumption
or dispatch-loop behavior is implemented here (explicitly out of scope for
this slice).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from nova_contracts import AgentOsTaskCompletedPayload, EventEnvelope

from nova_agent_os_kernel.domain.activity import AgentActivityKind, new_activity
from nova_agent_os_kernel.domain.ports import EventPublisher, KernelRepository

__all__ = ["reconcile_running_instances"]


async def reconcile_running_instances(
    repository: KernelRepository,
    event_publisher: EventPublisher,
    *,
    source_engine: str = "kernel",
) -> list[UUID]:
    """Every `agent_instance` row still `status="running"` at Kernel
    startup had its actual `inprocess` asyncio task die with the previous
    Kernel process -- there is no `AgentResult` to report, only the fact
    that the assignment was lost. Each such row is marked `"failed"` here
    (agent-instance-level bookkeeping) and, for any row that had an
    assigned `TaskNode`, `agent_os.task.completed` is published with
    `outcome="interrupted"` so `planning-engine` can revert that
    `TaskNode` to `"ready"` for redispatch, never left `"running"` forever
    (TDD 3E §4). `planning-engine`'s own consumption of this subject is a
    separate, disclosed follow-up (TDD 3B §6.1's own "real code, no real
    caller yet" idiom) -- publishing here is still meaningful and testable
    in isolation before that consumer exists.

    Returns the ids of every instance reconciled, for the caller (`main.py`
    startup) to log.

    **Agent activity, wired in Phase 4C milestone 4C.2d.** Each reconciled row
    also records one `interrupted` activity, written **in the same transaction
    as the `"failed"` transition** it describes -- an instance cannot be
    marked interrupted without the record of why, and cannot carry that record
    without the transition.

    `correlation_id` follows decision **B2**: the activity reuses *the exact
    UUID the published `agent_os.task.completed` carries*, so the row and the
    event are joinable on it. The payload is therefore built before the
    transition and read back from, rather than the id being minted twice or
    minted here and copied -- there is one `uuid4()` call per reconciled
    instance, in the same condition as before, and the published event is
    unchanged.

    An orphan with **no** `assigned_task_node_id` publishes no event, so no
    correlation id exists and the activity stores `NULL`. That asymmetry is
    the honest answer: minting an id for the column alone would manufacture
    provenance linking nothing, which `domain/activity.py` rules out.
    """
    orphaned = await repository.list_by_status("running")
    reconciled_instance_ids: list[UUID] = []
    for instance in orphaned:
        task_node_id = instance.assigned_task_node_id
        payload = (
            AgentOsTaskCompletedPayload(
                task_node_id=task_node_id,
                agent_instance_id=instance.id,
                outcome="interrupted",
                correlation_id=uuid4(),
            )
            if task_node_id is not None
            else None
        )

        detail: dict = {"reason": "kernel_restart"}
        if task_node_id is not None:
            detail["task_node_id"] = str(task_node_id)

        await repository.update_status(
            instance.id,
            status="failed",
            activity=new_activity(
                agent_instance_id=instance.id,
                kind=AgentActivityKind.INTERRUPTED,
                correlation_id=payload.correlation_id if payload is not None else None,
                detail=detail,
            ),
        )

        if payload is not None:
            await event_publisher.publish(
                EventEnvelope(
                    subject="agent_os.task.completed",
                    source_engine=source_engine,
                    correlation_id=payload.correlation_id,
                    payload=payload.model_dump(mode="json"),
                )
            )
        reconciled_instance_ids.append(instance.id)
    return reconciled_instance_ids
