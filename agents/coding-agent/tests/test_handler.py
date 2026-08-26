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
    def __init__(self, *, reply: ActionResultPayload) -> None:
        self._reply = reply
        self.received_requests: list[ActionExecuteRequestPayload] = []

    async def execute(self, request: ActionExecuteRequestPayload) -> ActionResultPayload:
        self.received_requests.append(request)
        return self._reply


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


async def test_on_load_and_health_check_report_healthy() -> None:
    handler = Handler(
        agent_instance_id=uuid4(), action_port=FakeActionPort(reply=_completed_reply())
    )
    health_before = await handler.health_check()
    assert health_before.status == "unhealthy"

    await handler.on_load(_manifest())
    health_after = await handler.health_check()
    assert health_after.status == "healthy"


async def test_execute_without_on_assign_raises() -> None:
    handler = Handler(
        agent_instance_id=uuid4(), action_port=FakeActionPort(reply=_completed_reply())
    )
    await handler.on_load(_manifest())
    with pytest.raises(RuntimeError, match="on_assign"):
        await handler.execute()


async def test_execute_calls_action_port_and_produces_a_successful_agent_result() -> None:
    instance_id = uuid4()
    action_port = FakeActionPort(reply=_completed_reply())
    handler = Handler(agent_instance_id=instance_id, action_port=action_port)
    task = _task()
    context = _context(task)

    await handler.on_load(_manifest())
    await handler.on_assign(task, context)
    result = await handler.execute()

    assert len(action_port.received_requests) == 1
    request = action_port.received_requests[0]
    assert request.action_type == "filesystem"
    assert request.execution_target == "filesystem"
    assert request.parameters["operation"] == "write"
    assert str(task.id) in request.parameters["path"]
    assert request.requesting_engine == "coding-agent"
    assert request.requested_by == instance_id
    assert request.correlation_id == context.correlation_id

    assert result.agent_instance_id == instance_id
    assert result.task_node_id == task.id
    assert result.status == "success"
    assert result.output["change"] == {"content": "written"}
    assert result.confidence == 1.0
    assert result.self_validation_passed is True
    assert result.correlation_id == context.correlation_id


async def test_execute_reports_failure_when_the_action_does_not_complete() -> None:
    action_port = FakeActionPort(reply=_completed_reply(status="failed", error="disk full"))
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
        agent_instance_id=uuid4(), action_port=FakeActionPort(reply=_completed_reply())
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
    action_port = FakeActionPort(reply=_completed_reply(status="failed", error="disk full"))
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
        agent_instance_id=uuid4(), action_port=FakeActionPort(reply=_completed_reply())
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
    action_port = FakeActionPort(reply=_completed_reply())
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
        agent_instance_id=uuid4(), action_port=FakeActionPort(reply=_completed_reply())
    )
    await handler.on_load(_manifest())
    await handler.on_unload()
    health = await handler.health_check()
    assert health.status == "unhealthy"
