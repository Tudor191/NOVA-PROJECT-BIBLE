"""Unit tests for coding-agent's `Handler` (doc 12 §4's `AgentHandler`
Protocol). Fake-backed: a `FakeActionPort` stands in for `agent-os/kernel`'s
own `ActionClient`, the same "domain tested against a fake Port, never a
real Event Bus" discipline every other Phase 3 component's own unit tests
already establish (mirrors `agents/research-agent/tests/test_handler.py`'s
own `FakeModelGatewayPort` precedent exactly).

Deliberately does not exercise `agents/coding-agent/agent.yaml` or the
Registry install pipeline -- that is Registry's own, already-tested
responsibility; these tests exercise `Handler` in isolation, the way
`InprocessExecutionBackend` will actually drive it.
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest
from nova_agent_sdk import AgentContext, AgentManifest
from nova_contracts import (
    ActionExecuteRequestPayload,
    ActionResultPayload,
    AgentMessage,
    AgentMessageType,
    PermissionSet,
    TaskNodeSnapshot,
    WorldModelSnapshot,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from handler import Handler  # noqa: E402


class FakeActionPort:
    """Answers per operation, because `Handler.execute()` now issues three
    actions in order (D5: write, `git add`, `git commit`). A single canned
    reply would let a test pass while the handler sent the wrong request for
    a step, or skipped one entirely.

    Each step's reply can be overridden independently so a failure can be
    injected at exactly one point in the chain, and `raise_on` makes the RPC
    itself blow up for one operation."""

    def __init__(
        self,
        *,
        write_reply: ActionResultPayload | None = None,
        add_reply: ActionResultPayload | None = None,
        commit_reply: ActionResultPayload | None = None,
        raise_on: str | None = None,
    ) -> None:
        self._replies = {
            "write": write_reply or _completed_reply(),
            "add": add_reply or _git_reply(),
            "commit": commit_reply or _git_reply(stdout="[main abc1234] coding-agent: ..."),
        }
        self._raise_on = raise_on
        self.received_requests: list[ActionExecuteRequestPayload] = []

    @property
    def operations(self) -> list[str]:
        return [str(r.parameters.get("operation")) for r in self.received_requests]

    async def execute(self, request: ActionExecuteRequestPayload) -> ActionResultPayload:
        self.received_requests.append(request)
        operation = str(request.parameters.get("operation"))
        if operation == self._raise_on:
            raise RuntimeError(f"event bus unavailable for {operation!r}")
        return self._replies[operation]


def _manifest() -> AgentManifest:
    return AgentManifest.model_validate(
        {
            "id": "coding-agent",
            "version": "0.1.0",
            "category": "coding",
            "display_name": "Coding Agent",
            "required_capabilities": ["git", "filesystem", "terminal"],
            "required_permissions": ["filesystem:write:project-scope", "terminal:execute"],
            "supported_execution_backends": ["inprocess"],
            "resource_profile": {"cpu": "standard", "memory": "standard", "gpu": "none"},
            "health_check": {"interval_seconds": 30},
            "compatibility": {"min_kernel_version": "0.1.0"},
            "peer_reviewer_category": "architect",
        }
    )


def _task() -> TaskNodeSnapshot:
    return TaskNodeSnapshot(
        id=uuid4(),
        objective="Add a rate-limiting middleware to the API gateway",
        depends_on=[],
        assigned_agent_category="coding",
        effort_hours=2.0,
        confidence=0.7,
        risk="moderate",
        status="ready",
    )


def _context(task: TaskNodeSnapshot) -> AgentContext:
    return AgentContext(
        task=task,
        world_model_slice=WorldModelSnapshot(user_id=uuid4(), degraded=True),
        relevant_memory=[],
        relevant_knowledge=[],
        granted_permissions=PermissionSet(granted=[]),
        granted_capabilities=[],
        correlation_id=uuid4(),
    )


def _completed_reply(**overrides: object) -> ActionResultPayload:
    defaults: dict[str, object] = {
        "action_id": uuid4(),
        "status": "completed",
        "result": {"content": "written"},
        "error": None,
    }
    defaults.update(overrides)
    return ActionResultPayload(**defaults)


_GIT_NO_IDENTITY = (
    "Author identity unknown\n\n*** Please tell me who you are.\n"
    "fatal: unable to auto-detect email address"
)
_GIT_NOTHING_STAGED = "On branch master\nnothing to commit, working tree clean\n"


def _git_reply(*, exit_code: int = 0, stdout: str = "", stderr: str = "") -> ActionResultPayload:
    """The shape `capability-engine` really returns for a git invocation:
    `status="completed"` regardless of how git itself exited, with the exit
    code inside `result` (TDD 3C §8's structured failure). A non-zero
    `exit_code` here is a *failed git command reported through a successful
    action* -- precisely the case `Handler` has to catch itself."""
    return ActionResultPayload(
        action_id=uuid4(),
        status="completed",
        result={"exit_code": exit_code, "stdout": stdout, "stderr": stderr, "timed_out": False},
        error=None,
    )


async def test_on_load_and_health_check_report_healthy() -> None:
    handler = Handler(
        agent_instance_id=uuid4(), action_port=FakeActionPort()
    )
    health_before = await handler.health_check()
    assert health_before.status == "unhealthy"

    await handler.on_load(_manifest())
    health_after = await handler.health_check()
    assert health_after.status == "healthy"


async def test_execute_without_on_assign_raises() -> None:
    handler = Handler(
        agent_instance_id=uuid4(), action_port=FakeActionPort()
    )
    await handler.on_load(_manifest())
    with pytest.raises(RuntimeError, match="on_assign"):
        await handler.execute()


async def test_execute_calls_action_port_and_produces_a_successful_agent_result() -> None:
    instance_id = uuid4()
    action_port = FakeActionPort()
    handler = Handler(agent_instance_id=instance_id, action_port=action_port)
    task = _task()
    context = _context(task)

    await handler.on_load(_manifest())
    await handler.on_assign(task, context)
    result = await handler.execute()

    # D5: three actions, in order -- write, then stage, then commit.
    assert action_port.operations == ["write", "add", "commit"]
    request = action_port.received_requests[0]
    assert request.action_type == "filesystem"
    assert request.execution_target == "filesystem"
    assert request.parameters["operation"] == "write"
    assert str(task.id) in request.parameters["path"]
    assert request.requesting_engine == "coding-agent"
    # ADR-032 (D6): the identity `action-engine` gates the action on is the
    # real user from the assigned context -- NOT this instance's own
    # ephemeral id, which has no identity signal and no confidence policy
    # and so would be denied at stage 3. Both halves are asserted: an
    # equality check alone would pass if the handler happened to read some
    # other field that coincidentally held the same value.
    assert request.requested_by == context.world_model_slice.user_id
    assert request.requested_by != instance_id
    # Agent provenance is not lost by that change -- it lives in `source`.
    assert request.source == "coding-agent"
    assert request.correlation_id == context.correlation_id

    assert result.agent_instance_id == instance_id
    assert result.task_node_id == task.id
    assert result.status == "success"
    assert result.output["change"] == {"content": "written"}
    assert result.confidence == 1.0
    assert result.self_validation_passed is True
    assert result.correlation_id == context.correlation_id

    # --- D5: the git half of the same successful execution.
    add, commit = action_port.received_requests[1], action_port.received_requests[2]

    # `ActionType`'s own docstring: git is never a third type value -- it is
    # `terminal` plus an adapter selection.
    assert add.action_type == "terminal"
    assert commit.action_type == "terminal"
    assert add.execution_target == "git"
    assert commit.execution_target == "git"

    # Stages exactly the file written, never `-A`/`.`.
    assert add.parameters["args"] == [f"coding-agent-output/{task.id}.md"]
    # `-m <subject>` only: no `--author`, no `--allow-empty`.
    assert commit.parameters["args"] == ["-m", f"coding-agent: {task.objective}"]

    # D7: no target-repository field is invented; GitAdapter falls back to
    # the capability's own declared root.
    assert "repo_root" not in add.parameters
    assert "repo_root" not in commit.parameters

    # ADR-032 and provenance hold for every step, not just the first.
    assert {r.requested_by for r in action_port.received_requests} == {
        context.world_model_slice.user_id
    }
    assert {r.source for r in action_port.received_requests} == {"coding-agent"}

    # The causal chain is recorded on the actions themselves.
    assert add.depends_on == [request.action_id]
    assert commit.depends_on == [add.action_id]

    assert result.output["committed_path"] == f"coding-agent-output/{task.id}.md"
    assert result.output["commit_message"] == f"coding-agent: {task.objective}"
    assert result.output["commit"]["exit_code"] == 0
    assert result.output["action_ids"] == {
        "write": str(request.action_id),
        "add": str(add.action_id),
        "commit": str(commit.action_id),
    }


async def test_execute_reports_failure_when_the_action_does_not_complete() -> None:
    action_port = FakeActionPort(write_reply=_completed_reply(status="failed", error="disk full"))
    handler = Handler(agent_instance_id=uuid4(), action_port=action_port)
    task = _task()
    context = _context(task)

    await handler.on_load(_manifest())
    await handler.on_assign(task, context)
    result = await handler.execute()

    assert result.status == "failure"
    assert result.output["error"] == "disk full"
    assert result.self_validation_passed is False


async def test_execute_reports_failure_when_the_action_port_raises() -> None:
    class RaisingActionPort:
        async def execute(self, request: ActionExecuteRequestPayload) -> ActionResultPayload:
            raise TimeoutError("no reply within timeout")

    handler = Handler(agent_instance_id=uuid4(), action_port=RaisingActionPort())
    task = _task()
    context = _context(task)

    await handler.on_load(_manifest())
    await handler.on_assign(task, context)
    result = await handler.execute()

    assert result.status == "failure"
    assert "no reply within timeout" in result.output["error"]


async def test_self_validate_requires_peer_review_only_on_success() -> None:
    handler = Handler(
        agent_instance_id=uuid4(), action_port=FakeActionPort()
    )
    task = _task()
    context = _context(task)
    await handler.on_load(_manifest())
    await handler.on_assign(task, context)
    result = await handler.execute()

    outcome = await handler.self_validate(result)
    assert outcome.passed is True
    assert outcome.requires_peer_review is True


async def test_self_validate_does_not_require_peer_review_on_failure() -> None:
    action_port = FakeActionPort(write_reply=_completed_reply(status="failed", error="disk full"))
    handler = Handler(agent_instance_id=uuid4(), action_port=action_port)
    task = _task()
    context = _context(task)
    await handler.on_load(_manifest())
    await handler.on_assign(task, context)
    result = await handler.execute()

    outcome = await handler.self_validate(result)
    assert outcome.passed is False
    assert outcome.requires_peer_review is False


async def test_on_message_replies_to_health_ping_only() -> None:
    handler = Handler(
        agent_instance_id=uuid4(), action_port=FakeActionPort()
    )
    await handler.on_load(_manifest())

    ping = AgentMessage(
        message_type=AgentMessageType.HEALTH_PING,
        from_instance_id=uuid4(),
        to_instance_id=uuid4(),
        payload={},
        correlation_id=uuid4(),
    )
    reply = await handler.on_message(ping)
    assert reply is not None
    assert reply.message_type is AgentMessageType.HEALTH_PING

    peer_review_request = AgentMessage(
        message_type=AgentMessageType.PEER_REVIEW_REQUEST,
        from_instance_id=uuid4(),
        to_instance_id=uuid4(),
        payload={},
        correlation_id=uuid4(),
    )
    assert await handler.on_message(peer_review_request) is None


async def test_metrics_snapshot_tracks_completed_and_failed_tasks() -> None:
    action_port = FakeActionPort()
    handler = Handler(agent_instance_id=uuid4(), action_port=action_port)
    await handler.on_load(_manifest())

    task1 = _task()
    await handler.on_assign(task1, _context(task1))
    await handler.execute()

    metrics = handler.metrics_snapshot()
    assert metrics.tasks_completed == 1
    assert metrics.tasks_failed == 0


async def test_on_unload_marks_the_instance_unhealthy() -> None:
    handler = Handler(
        agent_instance_id=uuid4(), action_port=FakeActionPort()
    )
    await handler.on_load(_manifest())
    await handler.on_unload()
    health = await handler.health_check()
    assert health.status == "unhealthy"


# --- D5 failure handling: a step that does not genuinely succeed must stop
# the chain, and must never be reported to the Supervisor as a code change.


async def test_a_failed_write_never_reaches_git() -> None:
    """The ordering guarantee, not just the failure report: staging or
    committing after a failed write would either error confusingly or commit
    stale content from a previous run."""
    action_port = FakeActionPort(
        write_reply=_completed_reply(status="failed", error="disk full")
    )
    handler = Handler(agent_instance_id=uuid4(), action_port=action_port)
    task = _task()
    await handler.on_load(_manifest())
    await handler.on_assign(task, _context(task))

    result = await handler.execute()

    assert action_port.operations == ["write"]
    assert result.status == "failure"
    assert result.output["failed_step"] == "write"
    assert result.self_validation_passed is False


async def test_a_nonzero_git_add_stops_before_commit() -> None:
    """`git add` failing (a path git will not stage) leaves nothing to
    commit; committing anyway would produce either an error or an empty
    commit presented as a successful change."""
    action_port = FakeActionPort(
        add_reply=_git_reply(exit_code=128, stderr="fatal: pathspec did not match any files")
    )
    handler = Handler(agent_instance_id=uuid4(), action_port=action_port)
    task = _task()
    await handler.on_load(_manifest())
    await handler.on_assign(task, _context(task))

    result = await handler.execute()

    assert action_port.operations == ["write", "add"]
    assert result.status == "failure"
    assert result.output["failed_step"] == "add"
    assert "128" in result.output["error"]


async def test_a_nonzero_git_commit_is_a_failure_despite_a_completed_action() -> None:
    """The defect this check exists to prevent. `action-engine` reports
    `status="completed"` because the *invocation* succeeded (TDD 3C §8), so
    without inspecting `exit_code` this run would be reported as a
    successful code change with no commit behind it.

    Uses git's real "unable to auto-detect email address" output, captured
    from a real `git commit` with no configured identity."""
    action_port = FakeActionPort(
        commit_reply=_git_reply(exit_code=128, stderr=_GIT_NO_IDENTITY)
    )
    handler = Handler(agent_instance_id=uuid4(), action_port=action_port)
    task = _task()
    await handler.on_load(_manifest())
    await handler.on_assign(task, _context(task))

    result = await handler.execute()

    assert action_port.operations == ["write", "add", "commit"]
    assert result.status == "failure"
    assert result.output["failed_step"] == "commit"
    assert result.self_validation_passed is False
    assert "auto-detect email" in result.output["error"]
    assert handler.metrics_snapshot().tasks_completed == 0
    assert handler.metrics_snapshot().tasks_failed == 1


async def test_an_empty_commit_is_a_failure_not_a_silent_success() -> None:
    """git's real exit-1 "nothing to commit, working tree clean" path, which
    is what a repeated run over unchanged content produces."""
    action_port = FakeActionPort(
        commit_reply=_git_reply(exit_code=1, stdout=_GIT_NOTHING_STAGED)
    )
    handler = Handler(agent_instance_id=uuid4(), action_port=action_port)
    task = _task()
    await handler.on_load(_manifest())
    await handler.on_assign(task, _context(task))

    result = await handler.execute()

    assert result.status == "failure"
    assert result.output["failed_step"] == "commit"


async def test_the_rpc_itself_raising_on_a_git_step_is_reported_not_propagated() -> None:
    action_port = FakeActionPort(raise_on="commit")
    handler = Handler(agent_instance_id=uuid4(), action_port=action_port)
    task = _task()
    await handler.on_load(_manifest())
    await handler.on_assign(task, _context(task))

    result = await handler.execute()

    assert result.status == "failure"
    assert result.output["failed_step"] == "commit"
    assert "event bus unavailable" in result.output["error"]


async def test_a_failed_commit_is_not_offered_for_peer_review() -> None:
    """`self_validate` gates the peer-review round on the result it is given,
    so a failed commit must not arrive at `architect-agent` as work to
    review -- the Slice 1-3 peer-review behaviour, still holding."""
    action_port = FakeActionPort(commit_reply=_git_reply(exit_code=128, stderr="boom"))
    handler = Handler(agent_instance_id=uuid4(), action_port=action_port)
    task = _task()
    await handler.on_load(_manifest())
    await handler.on_assign(task, _context(task))

    result = await handler.execute()
    outcome = await handler.self_validate(result)

    assert result.status == "failure"
    assert outcome.requires_peer_review is False
