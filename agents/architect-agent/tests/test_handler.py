"""Unit tests for architect-agent's `Handler` (doc 12 §4's `AgentHandler`
Protocol). No fake Port is needed -- unlike every other Agent Package's own
`execute()`, this Handler's real Phase 3 work (`on_message`'s
`PEER_REVIEW_REQUEST` branch) operates only on the `AgentMessage.payload`
already delivered to it, calling neither `ModelGatewayPort` nor
`ActionPort`. Mirrors `agents/qa-agent/tests/test_handler.py`'s own
structure otherwise.
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from nova_agent_sdk import AgentContext, AgentManifest
from nova_contracts import (
    AgentMessage,
    AgentMessageType,
    AgentResult,
    PermissionSet,
    TaskNodeSnapshot,
    WorldModelSnapshot,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from handler import Handler  # noqa: E402


def _manifest() -> AgentManifest:
    return AgentManifest.model_validate(
        {
            "id": "architect-agent",
            "version": "0.1.0",
            "category": "architect",
            "display_name": "Architect Agent",
            "required_capabilities": [],
            "required_permissions": [],
            "supported_execution_backends": ["inprocess"],
            "resource_profile": {"cpu": "standard", "memory": "standard", "gpu": "none"},
            "health_check": {"interval_seconds": 30},
            "compatibility": {"min_kernel_version": "0.1.0"},
        }
    )


def _task() -> TaskNodeSnapshot:
    return TaskNodeSnapshot(
        id=uuid4(),
        objective="Review the rate-limiting middleware change",
        depends_on=[],
        assigned_agent_category="architect",
        effort_hours=0.25,
        confidence=0.9,
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


def _primary_result(**overrides: object) -> AgentResult:
    defaults: dict[str, object] = {
        "agent_instance_id": uuid4(),
        "task_node_id": uuid4(),
        "status": "success",
        "output": {"change": {"content": "written"}},
        "confidence": 1.0,
        "self_validation_passed": True,
        "correlation_id": uuid4(),
    }
    defaults.update(overrides)
    return AgentResult(**defaults)


def _peer_review_request(primary_result: AgentResult, *, to_instance_id: UUID) -> AgentMessage:
    return AgentMessage(
        message_type=AgentMessageType.PEER_REVIEW_REQUEST,
        from_instance_id=primary_result.agent_instance_id,
        to_instance_id=to_instance_id,
        payload=primary_result.model_dump(mode="json"),
        correlation_id=primary_result.correlation_id,
    )


async def test_on_load_and_health_check_report_healthy() -> None:
    handler = Handler(agent_instance_id=uuid4())
    health_before = await handler.health_check()
    assert health_before.status == "unhealthy"

    await handler.on_load(_manifest())
    health_after = await handler.health_check()
    assert health_after.status == "healthy"


async def test_execute_without_on_assign_raises() -> None:
    handler = Handler(agent_instance_id=uuid4())
    await handler.on_load(_manifest())
    with pytest.raises(RuntimeError, match="on_assign"):
        await handler.execute()


async def test_execute_returns_a_disclosed_stub_result() -> None:
    instance_id = uuid4()
    handler = Handler(agent_instance_id=instance_id)
    task = _task()
    context = _context(task)

    await handler.on_load(_manifest())
    await handler.on_assign(task, context)
    result = await handler.execute()

    assert result.agent_instance_id == instance_id
    assert result.task_node_id == task.id
    assert result.status == "success"
    assert "peer review" in result.output["note"]
    assert result.correlation_id == context.correlation_id


async def test_self_validate_never_requires_peer_review() -> None:
    handler = Handler(agent_instance_id=uuid4())
    task = _task()
    context = _context(task)
    await handler.on_load(_manifest())
    await handler.on_assign(task, context)
    result = await handler.execute()

    outcome = await handler.self_validate(result)
    assert outcome.passed is True
    assert outcome.requires_peer_review is False


async def test_on_message_replies_to_health_ping() -> None:
    handler = Handler(agent_instance_id=uuid4())
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


async def test_on_message_ignores_unrelated_message_types() -> None:
    handler = Handler(agent_instance_id=uuid4())
    await handler.on_load(_manifest())

    delegation = AgentMessage(
        message_type=AgentMessageType.DELEGATION,
        from_instance_id=uuid4(),
        to_instance_id=uuid4(),
        payload={},
        correlation_id=uuid4(),
    )
    assert await handler.on_message(delegation) is None


async def test_peer_review_request_approves_a_self_consistent_successful_result() -> None:
    reviewer_instance_id = uuid4()
    handler = Handler(agent_instance_id=reviewer_instance_id)
    await handler.on_load(_manifest())

    primary = _primary_result(status="success", self_validation_passed=True)
    request = _peer_review_request(primary, to_instance_id=reviewer_instance_id)

    reply = await handler.on_message(request)

    assert reply is not None
    assert reply.message_type is AgentMessageType.PEER_REVIEW_RESULT
    assert reply.from_instance_id == reviewer_instance_id
    assert reply.to_instance_id == primary.agent_instance_id
    assert reply.correlation_id == request.correlation_id

    verdict = AgentResult.model_validate(reply.payload)
    assert verdict.status == "success"
    assert verdict.self_validation_passed is True
    assert verdict.task_node_id == primary.task_node_id
    assert verdict.output["verdict"] == "success"
    assert verdict.output["reviewed_agent_instance_id"] == str(primary.agent_instance_id)


async def test_peer_review_request_rejects_a_failed_primary_result() -> None:
    reviewer_instance_id = uuid4()
    handler = Handler(agent_instance_id=reviewer_instance_id)
    await handler.on_load(_manifest())

    primary = _primary_result(status="failure", self_validation_passed=False)
    request = _peer_review_request(primary, to_instance_id=reviewer_instance_id)

    reply = await handler.on_message(request)

    assert reply is not None
    verdict = AgentResult.model_validate(reply.payload)
    assert verdict.status == "needs_revision"
    assert verdict.self_validation_passed is False


async def test_peer_review_request_rejects_an_inconsistent_self_report() -> None:
    """`status="success"` but `self_validation_passed=False` is internally
    inconsistent -- the scripted review rejects it, never blindly trusting
    `status` alone."""
    reviewer_instance_id = uuid4()
    handler = Handler(agent_instance_id=reviewer_instance_id)
    await handler.on_load(_manifest())

    primary = _primary_result(status="success", self_validation_passed=False)
    request = _peer_review_request(primary, to_instance_id=reviewer_instance_id)

    reply = await handler.on_message(request)

    assert reply is not None
    verdict = AgentResult.model_validate(reply.payload)
    assert verdict.status == "needs_revision"


async def test_metrics_snapshot_tracks_completed_reviews() -> None:
    reviewer_instance_id = uuid4()
    handler = Handler(agent_instance_id=reviewer_instance_id)
    await handler.on_load(_manifest())

    primary = _primary_result()
    request = _peer_review_request(primary, to_instance_id=reviewer_instance_id)
    await handler.on_message(request)

    metrics = handler.metrics_snapshot()
    assert metrics.tasks_completed == 1
    assert metrics.tasks_failed == 0


async def test_on_unload_marks_the_instance_unhealthy() -> None:
    handler = Handler(agent_instance_id=uuid4())
    await handler.on_load(_manifest())
    await handler.on_unload()
    health = await handler.health_check()
    assert health.status == "unhealthy"
