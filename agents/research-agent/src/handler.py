"""Research Agent -- implements the Agent SDK's `AgentHandler` Protocol
(docs/architecture/12-agent-architecture.md §4). Phase 3's deliberately
minimal scope (TDD 3E §9): "Given `AgentContext.task.objective`, consults
`relevant_memory`/`relevant_knowledge` (already pre-scoped) and calls
`ai-model-orchestration-engine` to produce a structured finding."

Brought up and validated first, alone, per the roadmap's own step 4 --
proving the full Kernel Scheduler -> Supervisor -> instance loop before
`coding-agent`/`qa-agent`/`architect-agent`/`documentation-agent` exist.

**Constructor convention, disclosed.** `agent-os/kernel`'s own
`InprocessExecutionBackend` constructs `Handler(agent_instance_id=...,
model_gateway=...)` as keyword-only, defaulted arguments -- both default to
`None` so `agent-os/registry`'s own install-time On Load smoke test
(`handler_class()`, zero arguments) still succeeds; `execute()` is the one
method that actually needs `model_gateway` populated, and it is always
populated by the time a real Kernel dispatch calls it. See
`agent-os/kernel/src/nova_agent_os_kernel/domain/execution_backend.py`'s
own module docstring for the full disclosure.

`on_assign`'s `task` parameter is typed `TaskNodeSnapshot` (`nova_contracts`),
not planning-engine's own domain `TaskNode` doc 12 §4 names -- the same
domain-vs-wire-payload split already applied to `AgentContext.task`
(`nova_contracts.entities`, Phase 3E Milestone 1): a cross-engine consumer
gets the published wire snapshot, never another engine's internal domain
type (ADR-004).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from nova_agent_sdk import (
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
    ContextComponentPayload,
    GenerateRequestPayload,
    ResourceUsage,
    TaskNodeSnapshot,
)

__all__ = ["Handler"]

_INSTRUCTION = (
    "Research the given objective using the supplied context and produce a "
    "concise, structured finding: what you found, and how confident you are."
)


def _component(source: str, text: str, *, priority: int) -> ContextComponentPayload:
    """Mirrors `planning-engine`'s own `decomposition.py::_component` helper
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


class Handler(AgentHandler):
    def __init__(
        self,
        *,
        agent_instance_id: UUID | None = None,
        model_gateway: ModelGatewayPort | None = None,
    ) -> None:
        self._agent_instance_id = agent_instance_id
        self._model_gateway = model_gateway
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
        if self._agent_instance_id is None:
            raise RuntimeError("execute() called on an instance with no agent_instance_id")

        request = GenerateRequestPayload(
            context=_build_prompt_context(self._task, self._context),
            task_type="research_finding",
            requesting_engine="research-agent",
            correlation_id=self._context.correlation_id,
        )
        try:
            reply = await self._model_gateway.generate(request)
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

        if reply.finish_reason == "error":
            self._tasks_failed += 1
            return AgentResult(
                agent_instance_id=self._agent_instance_id,
                task_node_id=self._task.id,
                status="failure",
                output={"error": reply.error or "model generation failed"},
                confidence=None,
                self_validation_passed=False,
                correlation_id=self._context.correlation_id,
            )

        self._tasks_completed += 1
        return AgentResult(
            agent_instance_id=self._agent_instance_id,
            task_node_id=self._task.id,
            status="success",
            output={"finding": reply.text},
            confidence=reply.structural_confidence,
            self_validation_passed=True,
            correlation_id=self._context.correlation_id,
        )

    async def on_pause(self) -> None:
        pass

    async def on_resume(self) -> None:
        pass

    async def self_validate(self, result: AgentResult) -> ValidationOutcome:
        """`requires_peer_review=False` unconditionally -- TDD 3E §9 names
        no reviewer category for `research-agent` (only `coding-agent`,
        reviewed by `architect-agent`, has a peer-review pairing in Phase
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
        """`HEALTH_PING` only -- research-agent has no peer-review role and
        receives no `PEER_REVIEW_REQUEST`/`CONFLICT_ESCALATION` traffic in
        Phase 3 (mirrors `EngineeringSupervisorHandler`'s own precedent)."""
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
