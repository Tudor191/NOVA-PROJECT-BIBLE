"""`planning.task_graph.created` subscription handler -- the Kernel
Scheduler's own trigger (TDD 3E §4 step 1's own precondition). Fire-and-
forget: dispatch failures are already fully handled and reported inside
`domain/scheduler.py::dispatch_ready_nodes` (via `agent_os.task.completed`),
so this handler itself never raises.
"""

from __future__ import annotations

from fastapi import FastAPI
from nova_contracts import EventEnvelope, PlanningTaskGraphCreatedPayload
from nova_observability import get_logger

from nova_agent_os_kernel.domain.scheduler import dispatch_ready_nodes

__all__ = ["make_task_graph_created_handler"]

logger = get_logger("kernel.events.scheduler_handler")


def make_task_graph_created_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> None:
        state = app.state
        payload = PlanningTaskGraphCreatedPayload.model_validate(envelope.payload)

        if state.settings.primary_user_id is None:
            logger.warning(
                "planning.task_graph.created received but AGENT_OS_KERNEL_PRIMARY_USER_ID "
                "is unset -- cannot construct AgentContext.world_model_slice, skipping "
                "dispatch entirely for task_graph %s",
                payload.graph.id,
            )
            return

        dispatched = await dispatch_ready_nodes(
            payload.graph,
            repository=state.repository,
            registry_port=state.registry_port,
            supervisor_port=state.supervisor_port,
            execution_backend=state.execution_backend,
            event_publisher=state.bus,
            primary_user_id=state.settings.primary_user_id,
            correlation_id=payload.correlation_id,
        )
        logger.info(
            "planning.task_graph.created %s -- dispatched %d agent_instance(s)",
            payload.graph.id,
            len(dispatched),
        )

    return handle
