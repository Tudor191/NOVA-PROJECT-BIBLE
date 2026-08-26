"""Architect Agent -- implements the Agent SDK's `AgentHandler` Protocol
(docs/architecture/12-agent-architecture.md §4). TDD 3E §9's exact Phase 3
scope: "The scripted peer-review reviewer -- consumes `coding-agent`'s
`AgentResult` via `PEER_REVIEW_REQUEST`, produces a structured review
verdict."

**Reviewer, not reviewee, disclosed.** Unlike `research-agent`/`coding-agent`/
`qa-agent`, this package's real Phase 3 work happens in `on_message()`
(the doc-12-sanctioned Agent Mailbox entry point for `PEER_REVIEW_REQUEST`
traffic), not `execute()` -- TDD 3E §9's own agent table gives
`architect-agent` no task-assignment behavior at all. `execute()` is still
implemented, to satisfy `AgentHandler`'s full Protocol shape and Registry's
own "Handler structurally satisfies `AgentHandler`" install check, but it
is a deterministic, disclosed stub: it returns a fixed, successful
`AgentResult` explaining that this package's actual work is peer review.
No Phase 3 Task Graph node is ever assigned `category="architect"`
(`planning-engine`'s own scope, out of this package's control) -- peer
review happens automatically via `agent-os/kernel`'s own
`spawn_and_review()` mechanism, never via a normal Kernel Scheduler
dispatch.

**Delivery mechanism, disclosed (already approved, unchanged here).**
`agent-os/kernel`'s own Scheduler resolves this package via
`coding-agent`'s manifest-declared `peer_reviewer_category: architect`,
then calls `InprocessExecutionBackend.spawn_and_review()`, which
constructs one Handler instance and drives it through
`on_load -> on_message(PEER_REVIEW_REQUEST) -> on_unload` synchronously --
see that module's own docstring for the full disclosure. This Handler
introduces no new mailbox, persistence layer, or peer-review protocol; it
is purely the reviewer-side implementation of the already-implemented
mechanism.

**"Scripted review verdict," disclosed.** Like every other Phase 3 agent
(TDD 3E §9's own "no agent does open-ended, unscoped work" table
footnote), this is a deterministic, non-interpretive check -- no LLM call,
no static analysis, no free-form code-quality judgment. It verifies the
primary result's own self-report is internally consistent
(`status == "success"` and `self_validation_passed is True`) before
agreeing to approve; anything else is rejected (`status="needs_revision"`,
`AgentResult`'s own vocabulary). This mirrors the same "small,
deterministic, minimal classifier, proposed and flagged for future
refinement" disclosure discipline `action-engine`'s own
`domain/risk.py::classify_risk` already establishes -- a genuine
code-quality reviewer is out of Phase 3's scope entirely.

Constructor convention: see `agents/research-agent/src/handler.py`'s own
docstring for the full disclosure of the shared three-keyword-argument
convention (`agent_instance_id`, `model_gateway`, `action_port`) every
Handler class accepts. This agent uses neither `model_gateway` nor
`action_port` -- its review operates only on the `AgentResult` payload
already carried by `PEER_REVIEW_REQUEST`.
"""

from __future__ import annotations

from typing import Literal
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
    AgentMessageType,
    AgentResult,
    ResourceUsage,
    TaskNodeSnapshot,
)

__all__ = ["Handler"]


def _review(primary_result: AgentResult) -> tuple[Literal["success", "needs_revision"], str]:
    """The scripted review rule -- see this module's own docstring for the
    full disclosure of why this, and not a deeper judgment, is Phase 3's
    scope."""
    if primary_result.status == "success" and primary_result.self_validation_passed:
        return "success", "primary result self-reports success and self_validation_passed"
    return "needs_revision", (
        f"primary result status={primary_result.status!r}, "
        f"self_validation_passed={primary_result.self_validation_passed!r}"
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
        """Disclosed stub -- see this module's own docstring: TDD 3E §9
        gives `architect-agent` no task-assignment behavior in Phase 3,
        this package's real work happens in `on_message()`."""
        if self._task is None or self._context is None:
            raise RuntimeError("execute() called before on_assign()")
        if self._agent_instance_id is None:
            raise RuntimeError("execute() called on an instance with no agent_instance_id")

        self._tasks_completed += 1
        return AgentResult(
            agent_instance_id=self._agent_instance_id,
            task_node_id=self._task.id,
            status="success",
            output={
                "note": (
                    "architect-agent's Phase 3 role is peer review via on_message() "
                    "(PEER_REVIEW_REQUEST/PEER_REVIEW_RESULT); it has no direct "
                    "task-assignment behavior, per TDD 3E §9's own agent table"
                )
            },
            confidence=1.0,
            self_validation_passed=True,
            correlation_id=self._context.correlation_id,
        )

    async def on_pause(self) -> None:
        pass

    async def on_resume(self) -> None:
        pass

    async def self_validate(self, result: AgentResult) -> ValidationOutcome:
        """`requires_peer_review=False` unconditionally -- TDD 3E §9's own
        agent table gives no one the job of reviewing `architect-agent`'s
        own output in Phase 3."""
        return ValidationOutcome(
            passed=result.status == "success",
            requires_peer_review=False,
            reason=None if result.status == "success" else str(result.output.get("note")),
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
        """`HEALTH_PING` and `PEER_REVIEW_REQUEST` -- this package's actual
        Phase 3 work. See this module's own docstring for the full
        disclosure of the scripted review rule and the delivery mechanism
        (`InprocessExecutionBackend.spawn_and_review()`, already
        approved/implemented, unchanged here)."""
        if message.message_type is AgentMessageType.HEALTH_PING:
            health = await self.health_check()
            return AgentMessage(
                message_type=AgentMessageType.HEALTH_PING,
                from_instance_id=self._agent_instance_id or uuid4(),
                to_instance_id=message.from_instance_id or message.to_instance_id,
                payload=health.model_dump(mode="json"),
                correlation_id=message.correlation_id,
            )

        if message.message_type is AgentMessageType.PEER_REVIEW_REQUEST:
            primary_result = AgentResult.model_validate(message.payload)
            verdict_status, reason = _review(primary_result)
            self._tasks_completed += 1
            verdict = AgentResult(
                agent_instance_id=self._agent_instance_id or message.to_instance_id,
                task_node_id=primary_result.task_node_id,
                status=verdict_status,
                output={
                    "verdict": verdict_status,
                    "reason": reason,
                    "reviewed_agent_instance_id": str(primary_result.agent_instance_id),
                },
                confidence=1.0,
                self_validation_passed=verdict_status == "success",
                correlation_id=message.correlation_id,
            )
            return AgentMessage(
                message_type=AgentMessageType.PEER_REVIEW_RESULT,
                from_instance_id=self._agent_instance_id or message.to_instance_id,
                to_instance_id=message.from_instance_id or message.to_instance_id,
                payload=verdict.model_dump(mode="json"),
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
