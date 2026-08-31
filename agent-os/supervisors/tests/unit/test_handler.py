"""`domain/handler.py` -- `EngineeringSupervisorHandler`'s
`AgentHandler` conformance (doc 12 §9) and its one genuinely exercised
message type, `HEALTH_PING`."""

from __future__ import annotations

from uuid import uuid4

from nova_agent_os_supervisors.domain.handler import EngineeringSupervisorHandler
from nova_agent_sdk import AgentHandler, AgentManifest
from nova_contracts import AgentMessage, AgentMessageType


def _manifest() -> AgentManifest:
    return AgentManifest.model_validate(
        {
            "id": "engineering-supervisor",
            "version": "0.1.0",
            "category": "supervisor",
            "display_name": "Engineering Supervisor",
            "supported_execution_backends": ["inprocess"],
            "resource_profile": {"cpu": "standard", "memory": "standard", "gpu": "none"},
            "health_check": {"interval_seconds": 30},
            "compatibility": {"min_kernel_version": "0.1.0"},
        }
    )


async def test_satisfies_the_agent_handler_protocol() -> None:
    assert isinstance(EngineeringSupervisorHandler(), AgentHandler)


async def test_health_check_reports_unhealthy_before_load_and_healthy_after() -> None:
    handler = EngineeringSupervisorHandler()

    before = await handler.health_check()
    assert before.status == "unhealthy"

    await handler.on_load(_manifest())
    after = await handler.health_check()
    assert after.status == "healthy"

    await handler.on_unload()
    unloaded = await handler.health_check()
    assert unloaded.status == "unhealthy"


async def test_on_message_replies_to_health_ping() -> None:
    handler = EngineeringSupervisorHandler()
    await handler.on_load(_manifest())
    supervisor_instance_id = uuid4()
    sender_id = uuid4()
    ping = AgentMessage(
        message_type=AgentMessageType.HEALTH_PING,
        from_instance_id=sender_id,
        to_instance_id=supervisor_instance_id,
        payload={},
        correlation_id=uuid4(),
    )

    reply = await handler.on_message(ping)

    assert reply is not None
    assert reply.message_type is AgentMessageType.HEALTH_PING
    assert reply.from_instance_id == supervisor_instance_id
    assert reply.to_instance_id == sender_id
    assert reply.payload["status"] == "healthy"


async def test_on_message_ignores_every_other_message_type() -> None:
    handler = EngineeringSupervisorHandler()
    await handler.on_load(_manifest())
    message = AgentMessage(
        message_type=AgentMessageType.DELEGATION,
        from_instance_id=uuid4(),
        to_instance_id=uuid4(),
        payload={},
        correlation_id=uuid4(),
    )

    reply = await handler.on_message(message)

    assert reply is None


def test_metrics_snapshot_starts_at_zero() -> None:
    handler = EngineeringSupervisorHandler()

    metrics = handler.metrics_snapshot()

    assert metrics.tasks_completed == 0
    assert metrics.tasks_failed == 0
