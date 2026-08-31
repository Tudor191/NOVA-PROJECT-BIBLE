"""`agent_os.supervisor.restart_plan.request` RPC handler -- serves the
Kernel Scheduler's own "owning Supervisor applies its configured restart
strategy" step (TDD 3E §12's failure table, doc 12 §9). Disclosed addition:
this Supervisor shipped with an empty `SUBSCRIBABLE_SUBJECTS` (no live RPC
surface at all); this is the smallest wire shape letting Kernel actually
call the already-built `domain/restart.py::plan_restart()` for a real
failure, crossing the wire because ADR-004 forbids Kernel from importing
`nova_agent_os_supervisors` internals directly. See
`nova_contracts.events.agent_os`'s own module docstring for the full
disclosure of this RPC pair.

Translates the wire-shaped `SupervisedInstanceSnapshot` list into
`domain.models.SupervisedInstance` at this boundary -- the same wire-
payload-to-domain-type translation pattern used everywhere else in this
codebase (e.g. `KnowledgeReference` built from a `knowledge.retrieve.reply`
at its own RPC boundary).
"""

from __future__ import annotations

from fastapi import FastAPI
from nova_contracts import (
    AgentOsRestartPlanReplyPayload,
    AgentOsRestartPlanRequestPayload,
    EventEnvelope,
)

from nova_agent_os_supervisors.domain.models import RestartStrategy, SupervisedInstance
from nova_agent_os_supervisors.domain.restart import plan_restart

__all__ = ["make_restart_plan_handler"]


def make_restart_plan_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> AgentOsRestartPlanReplyPayload:
        payload = AgentOsRestartPlanRequestPayload.model_validate(envelope.payload)

        siblings = [
            SupervisedInstance(
                id=sibling.id,
                category=sibling.category,
                restart_strategy=RestartStrategy(sibling.restart_strategy),
                started_order=sibling.started_order,
                status=sibling.status,
            )
            for sibling in payload.siblings
        ]

        restart_ids = plan_restart(
            strategy=RestartStrategy(payload.restart_strategy),
            failed_instance_id=payload.failed_instance_id,
            siblings=siblings,
        )
        return AgentOsRestartPlanReplyPayload(restart_instance_ids=restart_ids)

    return handle
