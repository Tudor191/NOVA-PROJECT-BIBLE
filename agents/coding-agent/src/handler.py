"""Coding Agent -- implements the Agent SDK's `AgentHandler` Protocol
(docs/architecture/12-agent-architecture.md §4). TDD 3E §9's exact scope:
"Invokes `action-engine` (via `action.execute`, 3D) using granted
`filesystem`/`terminal`/`git` capabilities to make a scripted code
change."

**"Scripted," disclosed.** Like `research-agent`'s own fixed `_INSTRUCTION`
constant, this agent's own "code change" is a deterministic, non-interpretive
transformation of already-structured fields (`task.id`, `task.objective`) --
never free-text parsing of the objective for a target path, and no LLM call.
This mirrors `qa-agent`'s own TDD 3E §9 treatment ("not interpreted") and the
project's own "no agent in Phase 3 does open-ended, unscoped work" principle
(TDD 3E §9, table footnote). It writes one record file per task under a
fixed `coding-agent-output/` project-relative path via a `"write"`
`action.execute` filesystem operation -- the actual write is performed (or
simulated, in tests) by `action-engine`'s own pipeline via the injected
`ActionPort`, never by this Handler directly touching the filesystem.

**Peer review, disclosed.** `self_validate()` returns
`requires_peer_review=True` on a successful result -- TDD 3E §9's own
`coding-agent`/`architect-agent` pairing, made machine-readable via this
package's own `agent.yaml`'s `peer_reviewer_category: architect` (disclosed
`nova_agent_sdk.AgentManifest` field; see that module's own docstring for
the full disclosure of how the Kernel Scheduler acts on it). This Handler
itself has no reviewer-side role -- `on_message()` still only answers
`HEALTH_PING`, identically to `research-agent`'s own precedent; being
reviewed and reviewing are different roles, and this package only ever
plays the former in Phase 3.

Constructor convention: see `agents/research-agent/src/handler.py`'s own
docstring for the full disclosure of the shared three-keyword-argument
convention (`agent_instance_id`, `model_gateway`, `action_port`) every
Handler class now accepts. This agent is the first to actually use
`action_port`; `model_gateway` is accepted but unused (symmetric with
`research-agent`'s own unused-but-accepted `action_port`).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from nova_agent_sdk import (
    ActionPort,
    AgentContext,
    AgentHandler,
    AgentHealth,
    AgentManifest,
    AgentMessage,
    AgentMetrics,
    ModelGatewayPort,
    ValidationOutcome,
)
from nova_contracts import (
    ActionExecuteRequestPayload,
    ActionPriority,
    AgentMessageType,
    AgentResult,
    ResourceUsage,
    TaskNodeSnapshot,
)

__all__ = ["Handler"]

_VERIFICATION_METHOD = "action-engine reports ActionResultPayload.status == 'completed'"


def _build_action_request(
    task: TaskNodeSnapshot, *, requested_by: UUID, correlation_id: UUID
) -> ActionExecuteRequestPayload:
    """Deterministic, scripted (no LLM, no free-text parsing) -- writes one
    fixed-format record file per task under a fixed project-relative path,
    keyed only by the task's own structured `id`/`objective` fields."""
    path = f"coding-agent-output/{task.id}.md"
    content = f"# Task: {task.objective}\n\nScripted change committed by coding-agent.\n"
    return ActionExecuteRequestPayload(
        action_id=uuid4(),
        action_type="filesystem",
        priority=ActionPriority.NORMAL,
        source="coding-agent",
        requested_by=requested_by,
        execution_target="filesystem",
        parameters={"operation": "write", "path": path, "content": content},
        verification_method=_VERIFICATION_METHOD,
        requesting_engine="coding-agent",
        correlation_id=correlation_id,
    )


class Handler(AgentHandler):
    def __init__(
        self,
        *,
        agent_instance_id: UUID | None = None,
        model_gateway: ModelGatewayPort | None = None,
        action_port: ActionPort | None = None,
    ) -> None:
        self._agent_instance_id = agent_instance_id
        self._model_gateway = model_gateway
        self._action_port = action_port
        self._loaded = False
        self._task: TaskNodeSnapshot | None = None
        self._context: AgentContext | None = None
        self._tasks_completed = 0
        self._tasks_failed = 0

    async def on_load(self, manifest: AgentManifest) -> None:
        self._loaded = True

    async def on_unload(self) -> None:
        self._loaded = False

    async def on_assign(self, task: TaskNodeSnapshot, context: AgentContext) -> None:
        self._task = task
        self._context = context

    async def execute(self) -> AgentResult:
        if self._task is None or self._context is None:
            raise RuntimeError("execute() called before on_assign()")
        if self._action_port is None:
            raise RuntimeError("execute() called on an instance with no action_port")
        if self._agent_instance_id is None:
            raise RuntimeError("execute() called on an instance with no agent_instance_id")

        request = _build_action_request(
            self._task,
            requested_by=self._agent_instance_id,
            correlation_id=self._context.correlation_id,
        )
        try:
            reply = await self._action_port.execute(request)
        except Exception as exc:  # noqa: BLE001 -- reported as a failed AgentResult, not raised
            self._tasks_failed += 1
            return AgentResult(
                agent_instance_id=self._agent_instance_id,
                task_node_id=self._task.id,
                status="failure",
                output={"error": str(exc)},
                confidence=None,
                self_validation_passed=False,
                correlation_id=self._context.correlation_id,
            )

        if reply.status != "completed":
            self._tasks_failed += 1
            return AgentResult(
                agent_instance_id=self._agent_instance_id,
                task_node_id=self._task.id,
                status="failure",
                output={"error": reply.error or f"action ended in status {reply.status!r}"},
                confidence=None,
                self_validation_passed=False,
                correlation_id=self._context.correlation_id,
            )

        self._tasks_completed += 1
        return AgentResult(
            agent_instance_id=self._agent_instance_id,
            task_node_id=self._task.id,
            status="success",
            output={"change": reply.result or {}, "action_id": str(request.action_id)},
            confidence=1.0,
            self_validation_passed=True,
            correlation_id=self._context.correlation_id,
        )

    async def on_pause(self) -> None:
        pass

    async def on_resume(self) -> None:
        pass

    async def self_validate(self, result: AgentResult) -> ValidationOutcome:
        """`requires_peer_review=True` iff the primary result succeeded --
        TDD 3E §9's `coding-agent`/`architect-agent` pairing. A failed
        result has nothing for `architect-agent` to review."""
        passed = result.status == "success"
        return ValidationOutcome(
            passed=passed,
            requires_peer_review=passed,
            reason=None if passed else result.output.get("error"),
        )

    async def health_check(self) -> AgentHealth:
        return AgentHealth(
            status="healthy" if self._loaded else "unhealthy",
            latency_ms=0.0,
            error_rate=(
                0.0
                if self._tasks_completed + self._tasks_failed == 0
                else self._tasks_failed / (self._tasks_completed + self._tasks_failed)
            ),
            resource_usage=ResourceUsage(cpu_percent=0.0, memory_mb=0.0),
        )

    async def on_message(self, message: AgentMessage) -> AgentMessage | None:
        """`HEALTH_PING` only -- this agent is reviewed by `architect-agent`,
        it does not itself review anyone (mirrors `research-agent`'s own
        precedent; the reviewer role is `architect-agent`'s alone)."""
        if message.message_type is AgentMessageType.HEALTH_PING:
            health = await self.health_check()
            return AgentMessage(
                message_type=AgentMessageType.HEALTH_PING,
                from_instance_id=self._agent_instance_id or uuid4(),
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
