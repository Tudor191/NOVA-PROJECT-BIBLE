"""Unit tests for documentation-agent's `Handler` (doc 12 §4's
`AgentHandler` Protocol). Fake-backed: a `FakeModelGatewayPort` (mirrors
`agents/research-agent/tests/test_handler.py`'s own precedent) and a
`FakeActionPort` (mirrors `agents/coding-agent/tests/test_handler.py`'s own
precedent) stand in for the real RPCs, the same "domain tested against a
fake Port, never a real Event Bus" discipline every other Phase 3
component's own unit tests already establish.

Deliberately does not exercise `agents/documentation-agent/agent.yaml` or
the Registry install pipeline -- that is Registry's own, already-tested
responsibility; these tests exercise `Handler` in isolation, the way
`InprocessExecutionBackend` will actually drive it.
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from nova_agent_sdk import ActionPort, AgentContext, AgentManifest, ModelGatewayPort
from nova_contracts import (
    ActionExecuteRequestPayload,
    ActionResultPayload,
    AgentMessage,
    AgentMessageType,
    GenerateReplyPayload,
    GenerateRequestPayload,
    PermissionSet,
    TaskNodeSnapshot,
    WorldModelSnapshot,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from handler import Handler  # noqa: E402


class FakeModelGatewayPort:
    def __init__(self, *, reply: GenerateReplyPayload) -> None:
        self._reply = reply
        self.received_requests: list[GenerateRequestPayload] = []

    async def generate(self, request: GenerateRequestPayload) -> GenerateReplyPayload:
        self.received_requests.append(request)
        return self._reply


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
            "id": "documentation-agent",
            "version": "0.1.0",
            "category": "documentation",
            "display_name": "Documentation Agent",
            "required_capabilities": ["filesystem"],
            "required_permissions": ["filesystem:write:project-scope"],
            "supported_execution_backends": ["inprocess"],
            "resource_profile": {"cpu": "standard", "memory": "standard", "gpu": "none"},
            "health_check": {"interval_seconds": 30},
            "compatibility": {"min_kernel_version": "0.1.0"},
        }
    )


def _task() -> TaskNodeSnapshot:
    return TaskNodeSnapshot(
        id=uuid4(),
        objective="Document the rate-limiting middleware's configuration options",
        depends_on=[],
        assigned_agent_category="documentation",
        effort_hours=1.0,
        confidence=0.8,
        risk="low",
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


def _success_generate_reply(**overrides: object) -> GenerateReplyPayload:
    defaults: dict[str, object] = {
        "text": "# Rate Limiting\n\nConfigure `max_requests` and `window_seconds`.",
        "input_tokens": 40,
        "output_tokens": 25,
        "finish_reason": "stop",
        "structural_confidence": 0.88,
        "model_id": uuid4(),
        "provider": "fake",
    }
    defaults.update(overrides)
    return GenerateReplyPayload(**defaults)


def _completed_action_reply(**overrides: object) -> ActionResultPayload:
    defaults: dict[str, object] = {
        "action_id": uuid4(),
        "status": "completed",
        "result": {"content": "written"},
        "error": None,
    }
    defaults.update(overrides)
    return ActionResultPayload(**defaults)


def _handler(
    *,
    model_gateway: ModelGatewayPort | None = None,
    action_port: ActionPort | None = None,
    agent_instance_id: UUID | None = None,
) -> Handler:
    return Handler(
        agent_instance_id=agent_instance_id or uuid4(),
        model_gateway=model_gateway or FakeModelGatewayPort(reply=_success_generate_reply()),
        action_port=action_port or FakeActionPort(reply=_completed_action_reply()),
    )


async def test_on_load_and_health_check_report_healthy() -> None:
    handler = _handler()
    health_before = await handler.health_check()
    assert health_before.status == "unhealthy"

    await handler.on_load(_manifest())
    health_after = await handler.health_check()
    assert health_after.status == "healthy"


async def test_execute_without_on_assign_raises() -> None:
    handler = _handler()
    await handler.on_load(_manifest())
    with pytest.raises(RuntimeError, match="on_assign"):
        await handler.execute()


async def test_execute_calls_model_gateway_then_action_port_and_succeeds() -> None:
    instance_id = uuid4()
    gateway = FakeModelGatewayPort(reply=_success_generate_reply())
    action_port = FakeActionPort(reply=_completed_action_reply())
    handler = Handler(agent_instance_id=instance_id, model_gateway=gateway, action_port=action_port)
    task = _task()
    context = _context(task)

    await handler.on_load(_manifest())
    await handler.on_assign(task, context)
    result = await handler.execute()

    assert len(gateway.received_requests) == 1
    assert gateway.received_requests[0].requesting_engine == "documentation-agent"
    assert gateway.received_requests[0].correlation_id == context.correlation_id
    assert any(c.source == "objective" for c in gateway.received_requests[0].context)

    assert len(action_port.received_requests) == 1
    action_request = action_port.received_requests[0]
    assert action_request.action_type == "filesystem"
    assert action_request.parameters["operation"] == "write"
    assert str(task.id) in action_request.parameters["path"]
    assert action_request.parameters["content"] == _success_generate_reply().text
    assert action_request.requesting_engine == "documentation-agent"
    # ADR-032 (D6) -- see `coding-agent`'s own equivalent assertion.
    assert action_request.requested_by == context.world_model_slice.user_id
    assert action_request.requested_by != instance_id
    assert action_request.source == "documentation-agent"

    assert result.agent_instance_id == instance_id
    assert result.task_node_id == task.id
    assert result.status == "success"
    assert result.output["content"] == _success_generate_reply().text
    assert result.confidence == 0.88
    assert result.self_validation_passed is True
    assert result.correlation_id == context.correlation_id


async def test_execute_reports_failure_when_the_model_gateway_returns_an_error() -> None:
    gateway = FakeModelGatewayPort(
        reply=_success_generate_reply(finish_reason="error", error="upstream provider unavailable")
    )
    action_port = FakeActionPort(reply=_completed_action_reply())
    handler = _handler(model_gateway=gateway, action_port=action_port)
    task = _task()
    context = _context(task)

    await handler.on_load(_manifest())
    await handler.on_assign(task, context)
    result = await handler.execute()

    assert result.status == "failure"
    assert result.output["error"] == "upstream provider unavailable"
    assert result.self_validation_passed is False
    assert len(action_port.received_requests) == 0


async def test_execute_reports_failure_when_the_model_gateway_raises() -> None:
    class RaisingGateway:
        async def generate(self, request: GenerateRequestPayload) -> GenerateReplyPayload:
            raise TimeoutError("no reply within timeout")

    handler = _handler(model_gateway=RaisingGateway())
    task = _task()
    context = _context(task)

    await handler.on_load(_manifest())
    await handler.on_assign(task, context)
    result = await handler.execute()

    assert result.status == "failure"
    assert "no reply within timeout" in result.output["error"]


async def test_execute_reports_failure_when_the_action_does_not_complete() -> None:
    action_port = FakeActionPort(reply=_completed_action_reply(status="failed", error="disk full"))
    handler = _handler(action_port=action_port)
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

    handler = _handler(action_port=RaisingActionPort())
    task = _task()
    context = _context(task)

    await handler.on_load(_manifest())
    await handler.on_assign(task, context)
    result = await handler.execute()

    assert result.status == "failure"
    assert "no reply within timeout" in result.output["error"]


async def test_self_validate_never_requires_peer_review() -> None:
    handler = _handler()
    task = _task()
    context = _context(task)
    await handler.on_load(_manifest())
    await handler.on_assign(task, context)
    result = await handler.execute()

    outcome = await handler.self_validate(result)
    assert outcome.passed is True
    assert outcome.requires_peer_review is False


async def test_on_message_replies_to_health_ping_only() -> None:
    handler = _handler()
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
    handler = _handler()
    await handler.on_load(_manifest())

    task1 = _task()
    await handler.on_assign(task1, _context(task1))
    await handler.execute()

    metrics = handler.metrics_snapshot()
    assert metrics.tasks_completed == 1
    assert metrics.tasks_failed == 0


async def test_on_unload_marks_the_instance_unhealthy() -> None:
    handler = _handler()
    await handler.on_load(_manifest())
    await handler.on_unload()
    health = await handler.health_check()
    assert health.status == "unhealthy"
