"""Documentation Agent -- implements the Agent SDK's `AgentHandler` Protocol
(docs/architecture/12-agent-architecture.md §4). TDD 3E §9's exact Phase 3
scope: "Calls `ai-model-orchestration-engine` to produce documentation
content, writes it via `action-engine`'s `filesystem` capability."

**First (and only) Phase 3 agent to use both ports for real, disclosed.**
Every prior Agent Package used exactly one of `ModelGatewayPort`
(`research-agent`) or `ActionPort` (`coding-agent`, `qa-agent`); TDD 3E
§9's own sentence for `documentation-agent` names both steps explicitly --
generate content, then write it -- so this Handler's `execute()` calls
`self._model_gateway.generate()` first (mirrors `research-agent`'s own
`_build_prompt_context`/`GenerateRequestPayload` construction exactly,
including sourcing `AgentResult.confidence` from
`reply.structural_confidence`), then `self._action_port.execute()` with
the generated text as the write content (mirrors `coding-agent`'s own
`_build_action_request`/`ActionExecuteRequestPayload` construction, minus
`git`/`terminal` -- only `filesystem` is named). No new mechanism is
introduced; this is a direct composition of two already-approved,
already-used ports.

**"Scripted" prompt construction, disclosed.** Like `research-agent`'s own
fixed `_INSTRUCTION` constant, the *how* here is fixed and non-interpretive
-- only the task's own `objective` varies the content produced (TDD 3E
§9's own "no agent does open-ended, unscoped work" table footnote). The
write target is a fixed, deterministic path keyed only by `task.id`
(mirrors `coding-agent`'s own `coding-agent-output/<task-id>.md`
convention), never free-text parsing of the objective for a path.

**No peer-review role, no interaction with other agents, disclosed.**
TDD 3E §9's own agent table gives `documentation-agent` no
`peer_reviewer_category` (only `coding-agent`, reviewed by
`architect-agent`, has one) and describes no Agent-Mailbox interaction
with any other agent. `self_validate()` returns
`requires_peer_review=False` unconditionally, mirroring `research-agent`'s
and `qa-agent`'s own precedent.

Constructor convention: see `agents/research-agent/src/handler.py`'s own
docstring for the full disclosure of the shared three-keyword-argument
convention (`agent_instance_id`, `model_gateway`, `action_port`) every
Handler class accepts. This is the first agent to actually populate and
use both non-`agent_instance_id` arguments.
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
    ContextComponentPayload,
    GenerateRequestPayload,
    ResourceUsage,
    TaskNodeSnapshot,
)

__all__ = ["Handler"]

_INSTRUCTION = (
    "Write clear, concise documentation content for the given objective, "
    "using the supplied context."
)
_VERIFICATION_METHOD = "action-engine reports ActionResultPayload.status == 'completed'"


def _component(source: str, text: str, *, priority: int) -> ContextComponentPayload:
    """Mirrors `research-agent`'s own `handler.py::_component` helper
    exactly -- the established `token_estimate=len(text) // 4` convention
    used everywhere a `ContextComponentPayload` is built in this codebase."""
    return ContextComponentPayload(
        source=source, text=text, token_estimate=len(text) // 4, priority=priority
    )


def _build_prompt_context(
    task: TaskNodeSnapshot, context: AgentContext
) -> list[ContextComponentPayload]:
    components = [_component("objective", task.objective, priority=10)]
    for memory in context.relevant_memory:
        components.append(_component("relevant_memory", memory.summary, priority=5))
    for knowledge in context.relevant_knowledge:
        components.append(_component("relevant_knowledge", knowledge.summary, priority=5))
    components.append(_component("instruction", _INSTRUCTION, priority=10))
    return components


def _build_action_request(
    task: TaskNodeSnapshot, *, content: str, requested_by: UUID, correlation_id: UUID
) -> ActionExecuteRequestPayload:
    """Deterministic, scripted write target -- keyed only by the task's own
    structured `id`, never free-text parsing of `task.objective` (mirrors
    `coding-agent`'s own `_build_action_request`)."""
    path = f"documentation-agent-output/{task.id}.md"
    return ActionExecuteRequestPayload(
        action_id=uuid4(),
        action_type="filesystem",
        priority=ActionPriority.NORMAL,
        source="documentation-agent",
        requested_by=requested_by,
        execution_target="filesystem",
        parameters={"operation": "write", "path": path, "content": content},
        verification_method=_VERIFICATION_METHOD,
        requesting_engine="documentation-agent",
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
        if self._model_gateway is None:
            raise RuntimeError("execute() called on an instance with no model_gateway")
        if self._action_port is None:
            raise RuntimeError("execute() called on an instance with no action_port")
        if self._agent_instance_id is None:
            raise RuntimeError("execute() called on an instance with no agent_instance_id")

        generate_request = GenerateRequestPayload(
            context=_build_prompt_context(self._task, self._context),
            task_type="documentation_content",
            requesting_engine="documentation-agent",
            correlation_id=self._context.correlation_id,
        )
        try:
            generate_reply = await self._model_gateway.generate(generate_request)
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

        if generate_reply.finish_reason == "error":
            self._tasks_failed += 1
            return AgentResult(
                agent_instance_id=self._agent_instance_id,
                task_node_id=self._task.id,
                status="failure",
                output={"error": generate_reply.error or "model generation failed"},
                confidence=None,
                self_validation_passed=False,
                correlation_id=self._context.correlation_id,
            )

        action_request = _build_action_request(
            self._task,
            content=generate_reply.text,
            # ADR-032, same reasoning as `coding-agent`'s own call site.
            # D6 names `coding-agent` and `qa-agent` explicitly; its rule is
            # stated generally ("for agent-originated
            # ActionExecuteRequestPayloads"), and this handler issues one, so
            # it is covered by the rule rather than left as the one agent
            # still denied by the identity gate.
            requested_by=self._context.world_model_slice.user_id,
            correlation_id=self._context.correlation_id,
        )
        try:
            action_reply = await self._action_port.execute(action_request)
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

        if action_reply.status != "completed":
            self._tasks_failed += 1
            return AgentResult(
                agent_instance_id=self._agent_instance_id,
                task_node_id=self._task.id,
                status="failure",
                output={
                    "error": action_reply.error
                    or f"action ended in status {action_reply.status!r}"
                },
                confidence=None,
                self_validation_passed=False,
                correlation_id=self._context.correlation_id,
            )

        self._tasks_completed += 1
        return AgentResult(
            agent_instance_id=self._agent_instance_id,
            task_node_id=self._task.id,
            status="success",
            output={
                "content": generate_reply.text,
                "action_id": str(action_request.action_id),
                "write_result": action_reply.result or {},
            },
            confidence=generate_reply.structural_confidence,
            self_validation_passed=True,
            correlation_id=self._context.correlation_id,
        )

    async def on_pause(self) -> None:
        pass

    async def on_resume(self) -> None:
        pass

    async def self_validate(self, result: AgentResult) -> ValidationOutcome:
        """`requires_peer_review=False` unconditionally -- TDD 3E §9's own
        agent table gives no one the job of reviewing
        `documentation-agent`'s own output in Phase 3."""
        return ValidationOutcome(
            passed=result.status == "success",
            requires_peer_review=False,
            reason=None if result.status == "success" else str(result.output.get("error")),
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
        """`HEALTH_PING` only -- `documentation-agent` has no peer-review
        role in Phase 3 (mirrors `research-agent`'s and `qa-agent`'s own
        precedent)."""
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
