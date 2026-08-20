"""`planning.decompose.request` request/reply RPC handler (TDD 3B §6.2, doc
12 §11) -- `phase-3b-planning-persistence` precursor. Its only real caller
(an `agent-os` Supervisor) does not exist until TDD 3E; this engine defines
and serves the RPC now, tested via the established "second `BoundEventBus`
as external caller" pattern (Phase 2D-D precedent), per TDD 3B §12.

"Mutation, not regeneration" (TDD 3B §4): appends the model's newly
proposed child `TaskNode`s to the already-persisted graph containing the
target node, recomputes `critical_path`, and republishes
`planning.task_graph.created` (§6.2's own "creation *and* major mutation"
wording) -- the target node's own row is never deleted or replaced.
"""

from __future__ import annotations

from fastapi import FastAPI
from nova_contracts import (
    EventEnvelope,
    PlanningDecomposeReplyPayload,
    PlanningDecomposeRequestPayload,
)
from nova_observability import get_logger

from nova_planning_engine.domain.decomposition import DecompositionError, decompose_node
from nova_planning_engine.domain.ports import OutboxEvent
from nova_planning_engine.events.snapshot import node_snapshot, task_graph_created_payload

__all__ = ["make_decompose_request_handler"]

logger = get_logger("planning-engine.events.decompose_handler")

_SOURCE_ENGINE = "planning-engine"


class TaskNodeNotFoundError(Exception):
    """Raised when `task_node_id` matches no node in any persisted graph --
    a distinct condition from "already minimal" (the node exists but the
    model proposed no further breakdown)."""


def make_decompose_request_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> PlanningDecomposeReplyPayload:
        state = app.state
        payload = PlanningDecomposeRequestPayload.model_validate(envelope.payload)

        found = await state.repository.find_node(payload.task_node_id)
        if found is None:
            raise TaskNodeNotFoundError(f"task_node {payload.task_node_id} does not exist")
        graph, target_node = found

        try:
            new_nodes = await decompose_node(
                node=target_node,
                model_port=state.model_orchestration_port,
                requesting_engine=_SOURCE_ENGINE,
                correlation_id=payload.correlation_id,
            )
        except DecompositionError as exc:
            logger.warning(
                "planning.decompose.request decomposition failed, treating as already minimal",
                extra={"task_node_id": str(payload.task_node_id), "reason": exc.reason},
            )
            new_nodes = []

        if not new_nodes:
            state.metrics.planning_decompose_request_served_total.add(
                1, {"already_minimal": "true"}
            )
            state.metrics.planning_decompose_request_already_minimal_total.add(1)
            logger.info(
                "planning.decompose.request served -- already minimal",
                extra={"task_node_id": str(payload.task_node_id)},
            )
            return PlanningDecomposeReplyPayload(already_minimal=True)

        def _build_outbox_event(updated_graph):  # type: ignore[no-untyped-def]
            created_payload = task_graph_created_payload(
                updated_graph, correlation_id=payload.correlation_id
            )
            return OutboxEvent(
                subject="planning.task_graph.created",
                payload=created_payload.model_dump(mode="json"),
                correlation_id=payload.correlation_id,
            )

        updated_graph = await state.repository.append_nodes(
            graph.id, new_nodes, outbox_event_builder=_build_outbox_event
        )

        state.metrics.planning_task_graph_mutated_total.add(1)
        state.metrics.planning_decompose_request_served_total.add(
            1, {"already_minimal": "false"}
        )
        state.metrics.planning_critical_path_length.record(len(updated_graph.critical_path))
        logger.info(
            "planning.decompose.request served",
            extra={
                "task_node_id": str(payload.task_node_id),
                "task_graph_id": str(graph.id),
                "new_node_count": len(new_nodes),
            },
        )

        new_node_ids = {node.id for node in new_nodes}
        reply_nodes = [node for node in updated_graph.nodes if node.id in new_node_ids]
        return PlanningDecomposeReplyPayload(
            already_minimal=False, new_nodes=[node_snapshot(node) for node in reply_nodes]
        )

    return handle
