"""`SupervisorClient` -- `domain.ports.SupervisorPort` implementation,
calling the disclosed `agent_os.supervisor.restart_plan.request` RPC (see
`nova_contracts.events.agent_os`'s own module docstring). Mirrors
`reasoning-engine`'s own `ModelOrchestrationClient` structure exactly.

`restart_strategy` is hardcoded to `one_for_one` -- TDD 3E §7's own default
for every category not otherwise configured; Phase 3 configures no
`one_for_all`/`rest_for_one` groupings for any of the five agents (only
`coding-agent`'s own peer-review pairing, not a restart-strategy grouping,
is named). `started_order` is derived from `AgentInstance.started_at`
(oldest first) -- `agent_os/supervisors`' own `SupervisedInstance` tracks
this as a monotonic sequence number, but Kernel's own `AgentInstance` has no
such field; `started_at` ordering is the smallest, disclosed translation
at this RPC boundary.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from nova_contracts import (
    AgentOsRestartPlanReplyPayload,
    AgentOsRestartPlanRequestPayload,
    SupervisedInstanceSnapshot,
)

from nova_agent_os_kernel.domain.models import AgentInstance
from nova_agent_os_kernel.domain.ports import EventPublisher

__all__ = ["SupervisorClient"]

SOURCE_ENGINE = "kernel"
DEFAULT_TIMEOUT_MS = 5000
_DEFAULT_RESTART_STRATEGY = "one_for_one"


class SupervisorClient:
    def __init__(
        self, event_publisher: EventPublisher, *, timeout_ms: int = DEFAULT_TIMEOUT_MS
    ) -> None:
        self._event_publisher = event_publisher
        self._timeout_ms = timeout_ms

    async def plan_restart(
        self,
        *,
        failed_instance_id: UUID,
        category: str,
        siblings: list[AgentInstance],
        correlation_id: UUID | None = None,
    ) -> list[UUID]:
        cid = correlation_id or uuid4()
        ordered = sorted(siblings, key=lambda s: s.started_at)
        wire_siblings = [
            SupervisedInstanceSnapshot(
                id=sibling.id,
                category=sibling.category,
                restart_strategy=_DEFAULT_RESTART_STRATEGY,
                started_order=index,
                status=sibling.status,
            )
            for index, sibling in enumerate(ordered)
        ]

        envelope = await self._event_publisher.request(
            "agent_os.supervisor.restart_plan.request",
            AgentOsRestartPlanRequestPayload(
                failed_instance_id=failed_instance_id,
                restart_strategy=_DEFAULT_RESTART_STRATEGY,
                siblings=wire_siblings,
                requesting_engine=SOURCE_ENGINE,
                correlation_id=cid,
            ),
            source_engine=SOURCE_ENGINE,
            correlation_id=cid,
            timeout_ms=self._timeout_ms,
        )
        parsed = AgentOsRestartPlanReplyPayload.model_validate(envelope.payload)
        return parsed.restart_instance_ids
