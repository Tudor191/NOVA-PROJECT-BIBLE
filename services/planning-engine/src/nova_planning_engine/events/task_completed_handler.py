"""`agent_os.task.completed` subscribed handler (TDD 3E §4/§12) --
`05-tdd-3b-planning-engine.md` §6.1's own named, deferred subscription:
"`planning-engine` subscribes to mutate the corresponding `TaskNode.status`
... this subscription cannot be exercised in real conditions until TDD 3E
ships." `agent-os/kernel`'s own milestone-2 slice built the publisher side
(`nova_contracts.events.agent_os.AgentOsTaskCompletedPayload`'s own
docstring: "`planning-engine`'s own consumption of this subject is
intentionally not built by this change... wiring the consumer side is
`planning-engine`'s separate, disclosed follow-up") -- this module is that
follow-up.

Fire-and-forget subscription (`bus.subscribe`, not `bus.serve`) -- Kernel
never waits on this handler; `agent_os.task.completed` is already a fully
reported, terminal event regardless of what planning-engine does with it,
mirroring `make_reasoning_process_completed_handler`'s own fire-and-forget
treatment of `reasoning.process.completed`.

Reuses the existing `planning.task_graph.created` publish path (already
enqueued via the transactional outbox by every other graph mutation in
this engine) to trigger redispatch -- no new event, no new RPC. Kernel's
own Scheduler (`dispatch_ready_nodes`) already dispatches every
`status == "ready"` node in whatever `TaskGraphSnapshot` it receives, so
republishing the graph with exactly the affected node reset to `"ready"`
(every other node's status left untouched) is sufficient by itself to
trigger the normal Kernel redispatch flow.
"""

from __future__ import annotations

from fastapi import FastAPI
from nova_contracts import AgentOsTaskCompletedPayload, EventEnvelope
from nova_observability import get_logger

from nova_planning_engine.domain.ports import OutboxEvent
from nova_planning_engine.domain.task_completion import should_reset_to_ready
from nova_planning_engine.events.snapshot import task_graph_created_payload

__all__ = ["make_agent_os_task_completed_handler"]

logger = get_logger("planning-engine.events.task_completed_handler")


def make_agent_os_task_completed_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> None:
        state = app.state
        payload = AgentOsTaskCompletedPayload.model_validate(envelope.payload)

        found = await state.repository.find_node(payload.task_node_id)
        if found is None:
            logger.warning(
                "agent_os.task.completed for unknown task_node -- no persisted graph "
                "contains it, nothing to reset",
                extra={"task_node_id": str(payload.task_node_id), "outcome": payload.outcome},
            )
            return
        _graph, node = found

        if not should_reset_to_ready(outcome=payload.outcome, current_status=node.status):
            logger.info(
                "agent_os.task.completed outcome=%r for task_node %s -- no reset needed "
                "(current_status=%r)",
                payload.outcome,
                payload.task_node_id,
                node.status,
            )
            return

        def _build_outbox_event(updated_graph):  # type: ignore[no-untyped-def]
            created_payload = task_graph_created_payload(
                updated_graph, correlation_id=payload.correlation_id
            )
            return OutboxEvent(
                subject="planning.task_graph.created",
                payload=created_payload.model_dump(mode="json"),
                correlation_id=payload.correlation_id,
            )

        await state.repository.reset_node_status(
            node.id, status="ready", outbox_event_builder=_build_outbox_event
        )

        state.metrics.planning_task_node_reset_to_ready_total.add(1, {"outcome": payload.outcome})
        logger.info(
            "agent_os.task.completed outcome=%r -- reset task_node %s to ready for redispatch",
            payload.outcome,
            payload.task_node_id,
        )

    return handle
