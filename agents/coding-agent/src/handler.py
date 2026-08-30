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

**A code change is not a change until it is committed (decision D5).** This
Handler issues **three** `action.execute` requests in order -- filesystem
write, `git add`, `git commit` -- so a completed task leaves a real commit in
the target repository rather than an uncommitted working-tree edit. Each is a
separate `Action` with its own id, risk classification and audit trail, which
is what `action-engine`'s own per-Action pipeline is built around; `git` is
reached as `action_type="terminal"` plus `execution_target="git"`, the
representation `ActionType`'s own docstring mandates ("'Git' is not a
Bible-named Action Type -- it is a roadmap-level adapter layered on top of
Terminal/Filesystem Actions... never a third type value").

Steps 2 and 3 carry `depends_on` pointing at the previous step's `action_id`.
`action-engine` persists that field but does not currently gate on it, and
ordering here is guaranteed by awaiting each step before starting the next --
the field is set because it is true and makes the causal chain visible in the
persisted `Action` rows, not because anything enforces it.

**Non-zero exit codes are failures here, not upstream.** `git` exiting
non-zero is a *successful invocation of git* as far as `capability-engine`
and `action-engine` are concerned: TDD 3C §8 specifies "adapter fails at
invocation time (e.g., git command exits non-zero) -> structured failure
returned to the caller", so the reply carries `status="completed"` with
`result["exit_code"] != 0`. Interpreting that is the caller's job, and this
Handler does it for both git steps -- exactly the convention `qa-agent`
already established for `pytest` (`exit_code == 0 in the action's own result
payload`). Without that check a failed commit would be reported to the
Supervisor as a successful code change.

**No target-repository field, no new configuration.** Neither git step sends
`repo_root`, so `GitAdapter` falls back to its capability's own declared
`required_resources[0]` -- `Settings.sandbox_filesystem_root`, which decision
D7 already designated the target repository root. The subprocess environment
is unchanged from Slice 3 (a single `PATH`); `git add` and `git commit` need
no `HOME`, verified against real git rather than assumed, provided the target
repository carries a local `user.name`/`user.email` as D5 requires its
fixture to configure.

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
_GIT_VERIFICATION_METHOD = (
    "action-engine reports ActionResultPayload.status == 'completed' "
    "and the git subprocess exited 0"
)


def output_path_for(task: TaskNodeSnapshot) -> str:
    """The one project-relative path this agent writes for a given task.

    Exported so a test can assert against the real path rather than
    re-deriving the format string and silently drifting from it."""
    return f"coding-agent-output/{task.id}.md"


def commit_message_for(task: TaskNodeSnapshot) -> str:
    """Deterministic commit subject. `task.objective` is interpolated, never
    parsed, and reaches `git` as a single `execvp` argument via
    `asyncio.create_subprocess_exec` (never a shell), so no quoting or
    injection concern arises from its content."""
    return f"coding-agent: {task.objective}"


def _build_write_request(
    task: TaskNodeSnapshot, *, requested_by: UUID, correlation_id: UUID
) -> ActionExecuteRequestPayload:
    """Step 1. Deterministic, scripted (no LLM, no free-text parsing) --
    writes one fixed-format record file per task under a fixed
    project-relative path, keyed only by the task's own structured
    `id`/`objective` fields."""
    content = f"# Task: {task.objective}\n\nScripted change committed by coding-agent.\n"
    return ActionExecuteRequestPayload(
        action_id=uuid4(),
        action_type="filesystem",
        priority=ActionPriority.NORMAL,
        source="coding-agent",
        requested_by=requested_by,
        execution_target="filesystem",
        parameters={
            "operation": "write",
            "path": output_path_for(task),
            "content": content,
        },
        verification_method=_VERIFICATION_METHOD,
        requesting_engine="coding-agent",
        correlation_id=correlation_id,
    )


def _build_git_request(
    *,
    operation: str,
    args: list[str],
    requested_by: UUID,
    correlation_id: UUID,
    depends_on: list[UUID],
) -> ActionExecuteRequestPayload:
    """Steps 2 and 3. `action_type="terminal"` with
    `execution_target="git"` is the representation `ActionType`'s own
    docstring mandates for a git operation -- git is an adapter over
    Terminal/Filesystem Actions, never a third `ActionType` value.

    No `repo_root` parameter: `GitAdapter` then falls back to its
    capability's declared `required_resources[0]`, which
    `build_builtin_manifests` populates from
    `Settings.sandbox_filesystem_root` -- decision D7's designated target
    repository root. Sending one here would be inventing the
    target-repository contract D7 explicitly rules out."""
    return ActionExecuteRequestPayload(
        action_id=uuid4(),
        action_type="terminal",
        priority=ActionPriority.NORMAL,
        source="coding-agent",
        requested_by=requested_by,
        execution_target="git",
        depends_on=depends_on,
        parameters={"operation": operation, "args": args},
        verification_method=_GIT_VERIFICATION_METHOD,
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

    def _failed(self, output: dict) -> AgentResult:
        """Every failure path produces the same shape, so a caller never has
        to guess which one it is looking at. `self_validation_passed=False`
        keeps a failed change out of the peer-review round (`self_validate`
        only requests review for a successful result)."""
        assert self._task is not None and self._context is not None
        assert self._agent_instance_id is not None
        self._tasks_failed += 1
        return AgentResult(
            agent_instance_id=self._agent_instance_id,
            task_node_id=self._task.id,
            status="failure",
            output=output,
            confidence=None,
            self_validation_passed=False,
            correlation_id=self._context.correlation_id,
        )

    async def _run_step(
        self, step: str, request: ActionExecuteRequestPayload, *, check_exit_code: bool
    ) -> tuple[dict | None, AgentResult | None]:
        """One `action.execute` round trip. Returns `(result, None)` when the
        step genuinely succeeded, or `(None, failure)` when it did not --
        never both, and never a partial success the caller might mistake for
        a completed step.

        Three distinct ways a step can fail, all reported rather than raised:
        the RPC itself raising, `action-engine` reporting a non-`completed`
        status (denied, failed, timed out), and -- for git -- the command
        exiting non-zero while the invocation around it succeeded."""
        assert self._action_port is not None
        try:
            reply = await self._action_port.execute(request)
        except Exception as exc:  # noqa: BLE001 -- reported as a failed AgentResult, not raised
            return None, self._failed(
                {"error": str(exc), "failed_step": step, "action_id": str(request.action_id)}
            )

        if reply.status != "completed":
            return None, self._failed(
                {
                    "error": reply.error or f"action ended in status {reply.status!r}",
                    "failed_step": step,
                    "action_id": str(request.action_id),
                }
            )

        result = reply.result or {}
        if check_exit_code and result.get("exit_code") != 0:
            # TDD 3C §8: a non-zero git exit is a *structured* failure, so it
            # arrives as a completed action. Only the caller can tell that
            # apart from success, and treating it as success would report a
            # commit that never happened.
            return None, self._failed(
                {
                    "error": (
                        f"git {step} exited "
                        f"{result.get('exit_code')!r}: {result.get('stderr', '').strip()}"
                    ),
                    "failed_step": step,
                    "action_id": str(request.action_id),
                    "result": result,
                }
            )
        return result, None

    async def execute(self) -> AgentResult:
        if self._task is None or self._context is None:
            raise RuntimeError("execute() called before on_assign()")
        if self._action_port is None:
            raise RuntimeError("execute() called on an instance with no action_port")
        if self._agent_instance_id is None:
            raise RuntimeError("execute() called on an instance with no agent_instance_id")

        # ADR-032: `requested_by` is the identity `action-engine` gates the
        # action on -- it looks up an identity-confidence signal and a
        # per-user policy for exactly this id (its own `domain/pipeline.py`
        # stage 3). That has to be the real user the work is being done for.
        # This instance's own id is an ephemeral per-dispatch UUID with no
        # identity record and no policy row, so supplying it made every
        # agent-originated action fail closed: absent signal -> confidence
        # 0.0, absent policy -> threshold 1.0, denied. Agent provenance is
        # not lost -- it is carried by `Action.source` ("coding-agent"),
        # which is what that field is for.
        requested_by = self._context.world_model_slice.user_id
        correlation_id = self._context.correlation_id

        # --- Step 1: write the file (D5's own ordering: write, add, commit).
        write_request = _build_write_request(
            self._task, requested_by=requested_by, correlation_id=correlation_id
        )
        write_result, failure = await self._run_step(
            "write", write_request, check_exit_code=False
        )
        if failure is not None:
            return failure

        # --- Step 2: stage exactly the file just written. Never `git add
        # -A`/`.`, which would sweep in unrelated working-tree state this
        # agent did not produce and cannot vouch for.
        add_request = _build_git_request(
            operation="add",
            args=[output_path_for(self._task)],
            requested_by=requested_by,
            correlation_id=correlation_id,
            depends_on=[write_request.action_id],
        )
        _add_result, failure = await self._run_step("add", add_request, check_exit_code=True)
        if failure is not None:
            return failure

        # --- Step 3: commit. `-m <subject>` only -- no `--author`, no
        # `--allow-empty`, nothing that would let this agent commit under an
        # identity the repository did not configure or record a commit with
        # no content.
        commit_request = _build_git_request(
            operation="commit",
            args=["-m", commit_message_for(self._task)],
            requested_by=requested_by,
            correlation_id=correlation_id,
            depends_on=[add_request.action_id],
        )
        commit_result, failure = await self._run_step(
            "commit", commit_request, check_exit_code=True
        )
        if failure is not None:
            return failure

        self._tasks_completed += 1
        return AgentResult(
            agent_instance_id=self._agent_instance_id,
            task_node_id=self._task.id,
            status="success",
            output={
                # `change` keeps its Slice-1..3 meaning (the write step's own
                # result) so nothing downstream that already reads it breaks;
                # `commit` and `action_ids` are additive.
                "change": write_result or {},
                "action_id": str(write_request.action_id),
                "committed_path": output_path_for(self._task),
                "commit_message": commit_message_for(self._task),
                "commit": commit_result or {},
                "action_ids": {
                    "write": str(write_request.action_id),
                    "add": str(add_request.action_id),
                    "commit": str(commit_request.action_id),
                },
            },
            confidence=1.0,
            self_validation_passed=True,
            correlation_id=correlation_id,
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
