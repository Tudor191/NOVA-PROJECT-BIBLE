"""QA Agent -- implements the Agent SDK's `AgentHandler` Protocol
(docs/architecture/12-agent-architecture.md §4). TDD 3E §9's exact Phase 3
scope: "Invokes `action-engine`'s `terminal` capability to run a test
suite; `AgentResult.status` reflects pass/fail directly, not interpreted."

**"Not interpreted," disclosed.** `action-engine`'s own `terminal` adapter
(`capability-engine/adapters/terminal_adapter.py`) runs the subprocess and
reports `ActionResultPayload.status="completed"` whenever the subprocess
itself ran to completion or timeout -- a nonzero exit code is *not* an
action-engine failure, it is the test suite's own verdict, returned inside
`result["exit_code"]`. "Not interpreted" therefore means: this Handler
reads `result["exit_code"]` directly (`0` -> pass, anything else, including
a timeout with no exit code -- -> fail) and does **not** parse `stdout`/
`stderr` content, apply any heuristic, or call a model to decide whether
the suite passed. `reply.status != "completed"` (the action itself never
ran -- e.g. denied, sandbox violation) is reported as a Handler-level
`AgentResult.status="failure"`, the same "infrastructure failure vs. the
scripted result itself" split `coding-agent`'s own `execute()` already
establishes.

**"Scripted," disclosed.** Like `coding-agent`'s own fixed action
construction, the command run here is deterministic -- a fixed
`pytest -q` invocation, never derived from free-text parsing of
`task.objective` (TDD 3E §9's own "no agent does open-ended, unscoped
work" principle, table footnote).

**No peer-review role, no direct Coding/Architect Agent interaction,
disclosed.** TDD 3E §9's own agent table gives `qa-agent` no
`peer_reviewer_category` (only `coding-agent`'s own manifest declares
one, reviewed by `architect-agent`) and describes no Agent-Mailbox
interaction with either `coding-agent` or `architect-agent` -- unlike doc
12 §9's own broader, aspirational Part-4 framing ("Coding Agent's output
reviewed by an Architect agent instance and a QA agent instance"), TDD 3E
§9's own Phase-3 scope narrows this to the single architect pairing
already implemented by `coding-agent`'s own slice (see that package's
README). Any relationship between a `qa-agent` task and a `coding-agent`
task in Phase 3 is therefore expressed the same way any two dependent
Task Graph nodes are -- `TaskNodeSnapshot.depends_on` (`planning-engine`'s
own, pre-existing mechanism, TDD 3B) -- never a new Agent Mailbox message
type or a second peer-review round. This Handler does not need to know
`coding-agent` exists.

Constructor convention: see `agents/research-agent/src/handler.py`'s own
docstring for the full disclosure of the shared three-keyword-argument
convention (`agent_instance_id`, `model_gateway`, `action_port`) every
Handler class accepts. This agent uses `action_port`, like `coding-agent`;
`model_gateway` is accepted but unused.
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

_VERIFICATION_METHOD = "exit_code == 0 in the action's own result payload"


def _build_action_request(
    *, requested_by: UUID, correlation_id: UUID
) -> ActionExecuteRequestPayload:
    """Deterministic, scripted (no LLM, no free-text parsing of
    `task.objective`) -- always runs the same fixed `pytest -q` command,
    taking no input from the assigned `TaskNodeSnapshot` at all (unlike
    `coding-agent`'s own `_build_action_request`, which keys its output
    path on `task.id`/`task.objective` -- there is nothing task-specific
    to run a fixed test suite command)."""
    return ActionExecuteRequestPayload(
        action_id=uuid4(),
        action_type="terminal",
        priority=ActionPriority.NORMAL,
        source="qa-agent",
        requested_by=requested_by,
        execution_target="terminal",
        parameters={"operation": "execute", "executable": "pytest", "args": ["-q"]},
        verification_method=_VERIFICATION_METHOD,
        requesting_engine="qa-agent",
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

        result = reply.result or {}
        exit_code = result.get("exit_code")
        passed = exit_code == 0

        if not passed:
            self._tasks_failed += 1
            return AgentResult(
                agent_instance_id=self._agent_instance_id,
                task_node_id=self._task.id,
                status="failure",
                output=result,
                confidence=1.0,
                self_validation_passed=False,
                correlation_id=self._context.correlation_id,
            )

        self._tasks_completed += 1
        return AgentResult(
            agent_instance_id=self._agent_instance_id,
            task_node_id=self._task.id,
            status="success",
            output=result,
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
        agent table gives `qa-agent` no reviewer category (only
        `coding-agent`, reviewed by `architect-agent`, has one in Phase
        3)."""
        return ValidationOutcome(
            passed=result.status == "success",
            requires_peer_review=False,
            reason=None if result.status == "success" else result.output.get("error"),
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
        """`HEALTH_PING` only -- `qa-agent` has no peer-review role in
        Phase 3 (mirrors `research-agent`'s own precedent)."""
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
