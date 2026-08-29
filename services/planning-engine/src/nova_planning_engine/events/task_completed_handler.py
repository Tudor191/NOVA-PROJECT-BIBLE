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
republishing the graph with exactly the affected nodes' statuses changed
(every other node left untouched) is sufficient by itself to trigger the
normal Kernel dispatch flow.

**Scope, widened from restart-resume to the full TaskNode lifecycle.**
This handler originally only reset interrupted/failed work to `"ready"`.
It now applies every transition
`domain/task_completion.py::resolve_transitions` returns -- crucially
including `"success"` -> `"completed"` plus the promotion of dependents
that completion unblocks, which is what lets a multi-node Task Graph
advance past its first layer at all. See that module's docstring for the
outcome table and for the explicit, disclosed Phase 3 decision that
`outcome="failure"` is terminal.

The completion and the promotions it causes are applied as **one**
`apply_transitions` call, not several: a half-advanced graph must never be
observable, and the accompanying republish must describe the graph after
the whole advancement, never during it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from nova_contracts import AgentOsTaskCompletedPayload, EventEnvelope
from nova_observability import get_logger

from nova_planning_engine.domain.models import TaskNodeStatus
from nova_planning_engine.domain.ports import OutboxEvent
from nova_planning_engine.domain.task_completion import resolve_transitions
from nova_planning_engine.events.snapshot import task_graph_created_payload

if TYPE_CHECKING:
    from uuid import UUID

    from nova_planning_engine.observability import PlanningEngineMetrics

__all__ = ["make_agent_os_task_completed_handler"]

logger = get_logger("planning-engine.events.task_completed_handler")


def _record_metrics(
    metrics: PlanningEngineMetrics,
    *,
    outcome: str,
    transitions: list[tuple[UUID, TaskNodeStatus]],
) -> None:
    """One counter per transition kind, labelled by the `outcome` that
    produced it -- so "how often does a node end terminally failed" and
    "how much work does a completion unblock" are both directly
    answerable, not inferred from a single undifferentiated counter."""
    for _node_id, status in transitions:
        if status == "completed":
            metrics.planning_task_node_completed_total.add(1)
        elif status == "failed":
            metrics.planning_task_node_failed_total.add(1, {"outcome": outcome})
        elif status == "ready":
            metrics.planning_task_node_promoted_total.add(1, {"outcome": outcome})


def make_agent_os_task_completed_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> None:
        state = app.state
        payload = AgentOsTaskCompletedPayload.model_validate(envelope.payload)

        found = await state.repository.find_node(payload.task_node_id)
        if found is None:
            logger.warning(
                "agent_os.task.completed for unknown task_node -- no persisted graph "
                "contains it, nothing to advance",
                extra={"task_node_id": str(payload.task_node_id), "outcome": payload.outcome},
            )
            return
        graph, node = found

        transitions = resolve_transitions(
            outcome=payload.outcome, task_node_id=payload.task_node_id, nodes=graph.nodes
        )
        if not transitions:
            # An unrecognised outcome, or a redelivery against an already-
            # terminal node. Processed successfully with no state change --
            # never an error, and never an enqueued republish that could
            # advance nothing.
            logger.info(
                "agent_os.task.completed outcome=%r for task_node %s -- no transition "
                "applies (current_status=%r)",
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

        await state.repository.apply_transitions(
            graph.id, transitions, outbox_event_builder=_build_outbox_event
        )

        _record_metrics(state.metrics, outcome=payload.outcome, transitions=transitions)
        logger.info(
            "agent_os.task.completed outcome=%r -- applied %d TaskNode transition(s) to "
            "task_graph %s",
            payload.outcome,
            len(transitions),
            graph.id,
            extra={
                "task_node_id": str(payload.task_node_id),
                "transitions": [
                    {"task_node_id": str(node_id), "status": status}
                    for node_id, status in transitions
                ],
            },
        )

    return handle
