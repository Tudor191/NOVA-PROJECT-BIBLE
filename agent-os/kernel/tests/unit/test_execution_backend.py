"""`InprocessExecutionBackend` against the **real** `agents/research-agent`
package on disk -- the same dynamic-import mechanism (`domain/
execution_backend.py::_load_handler_class`) Registry's own install pipeline
uses, exercised here at dispatch time instead of install time. A fake
`ModelGatewayPort` stands in for the real `ai_model.generate.request` RPC.

`spawn_and_review()`'s own tests (bottom of this file) reuse
`agents/research-agent`'s real, already-on-disk Handler as a **transport-only
stand-in reviewer** -- `architect-agent` does not exist yet (disclosed,
`agents/coding-agent/README.md`'s own gap note), and research-agent's own
`on_message()` already has a proven, tested `PEER_REVIEW_REQUEST -> None`
branch (`agents/research-agent/tests/test_handler.py`) precisely because it
has no reviewer-side logic of its own. That is exactly the right fixture for
proving `spawn_and_review()`'s own mechanics (dynamic import, `on_load` ->
`on_message` -> `on_unload`, reply pass-through) independently of any real
review verdict, which no Phase 3 package can yet provide.

`test_spawn_drives_the_real_qa_agent_handler_...` below proves the same
dynamic-import/constructor mechanism a third time, against
`agents/qa-agent`'s real on-disk Handler and a `FakeActionPort` (qa-agent's
own `execute()` uses `action_port`, not `model_gateway` -- mirrors
`agents/coding-agent/tests/test_handler.py`'s own `FakeActionPort`
precedent, here driven through the real `InprocessExecutionBackend` rather
than the Handler in isolation).
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from nova_agent_os_kernel.domain.execution_backend import InprocessExecutionBackend
from nova_agent_sdk import AgentContext
from nova_contracts import (
    ActionExecuteRequestPayload,
    ActionResultPayload,
    AgentMessage,
    AgentMessageType,
    AgentPackageSnapshot,
    GenerateReplyPayload,
    GenerateRequestPayload,
    PermissionSet,
    TaskNodeSnapshot,
    WorldModelSnapshot,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]


class FakeModelGatewayPort:
    def __init__(self, *, reply: GenerateReplyPayload) -> None:
        self._reply = reply

    async def generate(self, request: GenerateRequestPayload) -> GenerateReplyPayload:
        return self._reply


class FakeActionPort:
    def __init__(self, *, reply: ActionResultPayload) -> None:
        self._reply = reply

    async def execute(self, request: ActionExecuteRequestPayload) -> ActionResultPayload:
        return self._reply


def _package() -> AgentPackageSnapshot:
    return AgentPackageSnapshot(
        id=uuid4(),
        category="research",
        version="0.1.0",
        manifest_json={
            "id": "research-agent",
            "version": "0.1.0",
            "category": "research",
            "display_name": "Research Agent",
            "supported_execution_backends": ["inprocess"],
            "resource_profile": {"cpu": "standard", "memory": "standard", "gpu": "none"},
            "health_check": {"interval_seconds": 30},
            "compatibility": {"min_kernel_version": "0.1.0"},
        },
        health_status="healthy",
    )


def _context() -> AgentContext:
    task = TaskNodeSnapshot(
        id=uuid4(),
        objective="Research rate limiting approaches",
        depends_on=[],
        assigned_agent_category="research",
        effort_hours=1.0,
        confidence=0.7,
        risk="low",
        status="ready",
    )
    return AgentContext(
        task=task,
        world_model_slice=WorldModelSnapshot(user_id=uuid4(), degraded=True),
        relevant_memory=[],
        relevant_knowledge=[],
        granted_permissions=PermissionSet(granted=[]),
        granted_capabilities=[],
        correlation_id=uuid4(),
    )


def _qa_package() -> AgentPackageSnapshot:
    return AgentPackageSnapshot(
        id=uuid4(),
        category="qa",
        version="0.1.0",
        manifest_json={
            "id": "qa-agent",
            "version": "0.1.0",
            "category": "qa",
            "display_name": "QA Agent",
            "required_capabilities": ["terminal"],
            "required_permissions": ["terminal:execute"],
            "supported_execution_backends": ["inprocess"],
            "resource_profile": {"cpu": "standard", "memory": "standard", "gpu": "none"},
            "health_check": {"interval_seconds": 30},
            "compatibility": {"min_kernel_version": "0.1.0"},
        },
        health_status="healthy",
    )


def _qa_context() -> AgentContext:
    task = TaskNodeSnapshot(
        id=uuid4(),
        objective="Run the test suite",
        depends_on=[],
        assigned_agent_category="qa",
        effort_hours=0.5,
        confidence=0.9,
        risk="low",
        status="ready",
    )
    return AgentContext(
        task=task,
        world_model_slice=WorldModelSnapshot(user_id=uuid4(), degraded=True),
        relevant_memory=[],
        relevant_knowledge=[],
        granted_permissions=PermissionSet(granted=[]),
        granted_capabilities=[],
        correlation_id=uuid4(),
    )


async def test_spawn_drives_the_real_qa_agent_handler_to_a_successful_result() -> None:
    action_port = FakeActionPort(
        reply=ActionResultPayload(
            action_id=uuid4(),
            status="completed",
            result={"exit_code": 0, "stdout": "3 passed", "stderr": ""},
            error=None,
        )
    )
    backend = InprocessExecutionBackend(
        agents_root=_REPO_ROOT / "agents",
        model_gateway=FakeModelGatewayPort(
            reply=GenerateReplyPayload(
                text="",
                input_tokens=0,
                output_tokens=0,
                finish_reason="stop",
                structural_confidence=0.0,
                model_id=uuid4(),
                provider="fake",
            )
        ),
        action_port=action_port,
    )
    context = _qa_context()

    handle = await backend.spawn(_qa_package(), context)

    assert handle.error is None
    assert handle.result is not None
    assert handle.result.status == "success"
    assert handle.result.output["exit_code"] == 0
    assert handle.result.task_node_id == context.task.id
    assert handle.result.agent_instance_id == handle.instance_id
    assert handle.validation is not None
    assert handle.validation.passed is True
    assert handle.validation.requires_peer_review is False


async def test_spawn_drives_the_real_research_agent_handler_to_a_successful_result() -> None:
    gateway = FakeModelGatewayPort(
        reply=GenerateReplyPayload(
            text="Token-bucket rate limiting is standard.",
            input_tokens=10,
            output_tokens=10,
            finish_reason="stop",
            structural_confidence=0.9,
            model_id=uuid4(),
            provider="fake",
        )
    )
    backend = InprocessExecutionBackend(agents_root=_REPO_ROOT / "agents", model_gateway=gateway)
    context = _context()

    handle = await backend.spawn(_package(), context)

    assert handle.error is None
    assert handle.result is not None
    assert handle.result.status == "success"
    assert handle.result.task_node_id == context.task.id
    assert handle.result.agent_instance_id == handle.instance_id
    assert handle.validation is not None
    assert handle.validation.passed is True


async def test_spawn_reports_an_error_handle_for_an_unknown_agent_id() -> None:
    gateway = FakeModelGatewayPort(
        reply=GenerateReplyPayload(
            text="",
            input_tokens=0,
            output_tokens=0,
            finish_reason="stop",
            structural_confidence=0.0,
            model_id=uuid4(),
            provider="fake",
        )
    )
    backend = InprocessExecutionBackend(agents_root=_REPO_ROOT / "agents", model_gateway=gateway)
    package = _package()
    package = package.model_copy(
        update={"manifest_json": {**package.manifest_json, "id": "does-not-exist-agent"}}
    )

    handle = await backend.spawn(package, _context())

    assert handle.error is not None
    assert handle.result is None


async def test_spawn_and_review_delivers_health_ping_to_the_real_research_agent_handler() -> None:
    gateway = FakeModelGatewayPort(
        reply=GenerateReplyPayload(
            text="",
            input_tokens=0,
            output_tokens=0,
            finish_reason="stop",
            structural_confidence=0.0,
            model_id=uuid4(),
            provider="fake",
        )
    )
    backend = InprocessExecutionBackend(agents_root=_REPO_ROOT / "agents", model_gateway=gateway)
    reviewer_instance_id = uuid4()
    message = AgentMessage(
        message_type=AgentMessageType.HEALTH_PING,
        from_instance_id=uuid4(),
        to_instance_id=reviewer_instance_id,
        payload={},
        correlation_id=uuid4(),
    )

    reply = await backend.spawn_and_review(_package(), message)

    assert reply is not None
    assert reply.message_type is AgentMessageType.HEALTH_PING
    assert reply.correlation_id == message.correlation_id


async def test_spawn_and_review_returns_none_for_a_reviewer_with_no_peer_review_logic() -> None:
    """`agents/research-agent` has no reviewer-side role in Phase 3 (its own
    `on_message()` returns `None` for `PEER_REVIEW_REQUEST`, proven by
    `agents/research-agent/tests/test_handler.py`) -- proves
    `spawn_and_review()` faithfully passes that `None` straight through
    rather than fabricating a verdict."""
    gateway = FakeModelGatewayPort(
        reply=GenerateReplyPayload(
            text="",
            input_tokens=0,
            output_tokens=0,
            finish_reason="stop",
            structural_confidence=0.0,
            model_id=uuid4(),
            provider="fake",
        )
    )
    backend = InprocessExecutionBackend(agents_root=_REPO_ROOT / "agents", model_gateway=gateway)
    message = AgentMessage(
        message_type=AgentMessageType.PEER_REVIEW_REQUEST,
        from_instance_id=uuid4(),
        to_instance_id=uuid4(),
        payload={"status": "success"},
        correlation_id=uuid4(),
    )

    reply = await backend.spawn_and_review(_package(), message)

    assert reply is None


async def test_spawn_and_review_returns_none_for_an_unknown_agent_id() -> None:
    gateway = FakeModelGatewayPort(
        reply=GenerateReplyPayload(
            text="",
            input_tokens=0,
            output_tokens=0,
            finish_reason="stop",
            structural_confidence=0.0,
            model_id=uuid4(),
            provider="fake",
        )
    )
    backend = InprocessExecutionBackend(agents_root=_REPO_ROOT / "agents", model_gateway=gateway)
    package = _package()
    package = package.model_copy(
        update={"manifest_json": {**package.manifest_json, "id": "does-not-exist-agent"}}
    )
    message = AgentMessage(
        message_type=AgentMessageType.PEER_REVIEW_REQUEST,
        from_instance_id=uuid4(),
        to_instance_id=uuid4(),
        payload={},
        correlation_id=uuid4(),
    )

    reply = await backend.spawn_and_review(package, message)

    assert reply is None
