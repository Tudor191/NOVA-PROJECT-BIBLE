"""`EngineeringSupervisorHandler` -- doc 12 §9: "Supervisors are
themselves agents (built against the same Agent SDK, category
`supervisor`)... architecturally they are not privileged kernel code."
Implements `nova_agent_sdk.AgentHandler` for Protocol conformance and
fidelity to that sentence; the Supervisor's own real orchestration work
(restart planning, peer review, conflict resolution) lives in the sibling
`domain/restart.py`/`domain/peer_review.py`/`domain/conflict.py` modules,
called directly by whatever eventually drives dispatch (Kernel's own
Scheduler, not yet built -- see `domain/ports.py`'s disclosure) -- not
funneled through `execute()`, since a Supervisor is not assigned a single
`TaskNode` the way a leaf agent is (it is always-loaded once Kernel
starts, per doc 12 §9's supervision-tree diagram, `NOVA -> Kernel ->
EngSup -> {instances}`).

`on_message` is the one method genuinely exercised as an `AgentHandler`
call: TDD 3E §7/doc 12 §10 have a Supervisor receiving `PEER_REVIEW_RESULT`
and `CONFLICT_ESCALATION`/`HEALTH_PING` traffic from its own children over
the same Agent Mailbox mechanism every other agent uses."""

from __future__ import annotations

from nova_agent_sdk import (
    AgentContext,
    AgentHandler,
    AgentHealth,
    AgentManifest,
    AgentMessage,
    AgentMetrics,
    AgentResult,
    ValidationOutcome,
)
from nova_contracts import AgentMessageType, ResourceUsage

__all__ = ["EngineeringSupervisorHandler"]


class EngineeringSupervisorHandler(AgentHandler):
    """`category="supervisor"` (doc 12 §9). One instance is loaded once,
    for the lifetime of the Kernel process -- `on_load`/`on_unload` are its
    real lifecycle boundary, not per-task `on_assign`/`execute` (which this
    Supervisor never receives; TDD 3E §7 names no Task Graph work assigned
    directly to a Supervisor)."""

    def __init__(self) -> None:
        self._loaded = False
        self._tasks_completed = 0
        self._tasks_failed = 0

    async def on_load(self, manifest: AgentManifest) -> None:
        self._loaded = True

    async def on_unload(self) -> None:
        self._loaded = False

    async def on_assign(self, task: object, context: AgentContext) -> None:
        raise NotImplementedError(
            "engineering Supervisor is never directly assigned a TaskNode (TDD 3E §7)"
        )

    async def execute(self) -> AgentResult:
        raise NotImplementedError(
            "engineering Supervisor has no execute() work of its own (TDD 3E §7) -- "
            "restart/peer-review/conflict orchestration lives in domain/restart.py, "
            "domain/peer_review.py, domain/conflict.py"
        )

    async def on_pause(self) -> None:
        pass

    async def on_resume(self) -> None:
        pass

    async def self_validate(self, result: AgentResult) -> ValidationOutcome:
        raise NotImplementedError("no primary AgentResult of its own to self-validate")

    async def health_check(self) -> AgentHealth:
        return AgentHealth(
            status="healthy" if self._loaded else "unhealthy",
            latency_ms=0.0,
            error_rate=0.0,
            resource_usage=ResourceUsage(cpu_percent=0.0, memory_mb=0.0),
        )

    async def on_message(self, message: AgentMessage) -> AgentMessage | None:
        """Doc 12 §10: `PEER_REVIEW_RESULT`/`CONFLICT_ESCALATION`/
        `HEALTH_PING` reaching the Supervisor from its own children.
        Routing each to the right domain module (matching the reply
        already collected by `domain/peer_review.py`'s own
        `run_peer_review_round`, or triggering `domain/conflict.py`'s
        `resolve_conflict`) is Kernel-dispatch-loop wiring that does not
        exist yet (see `domain/ports.py`'s disclosure) -- this method
        accepts `HEALTH_PING` only, replying with this Supervisor's own
        health, and is a documented no-op for every other message type
        rather than silently dropping it."""
        if message.message_type is AgentMessageType.HEALTH_PING:
            health = await self.health_check()
            return AgentMessage(
                message_type=AgentMessageType.HEALTH_PING,
                from_instance_id=message.to_instance_id,
                to_instance_id=message.from_instance_id or message.to_instance_id,
                payload=health.model_dump(mode="json"),
                correlation_id=message.correlation_id,
            )
        return None

    def metrics_snapshot(self) -> AgentMetrics:
        total = self._tasks_completed + self._tasks_failed
        return AgentMetrics(
            tasks_completed=self._tasks_completed,
            tasks_failed=self._tasks_failed,
            average_duration_ms=0.0,
            average_confidence=1.0 if total == 0 else self._tasks_completed / total,
            resource_efficiency=1.0,
        )
