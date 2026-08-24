"""`InprocessExecutionBackend` against the **real** `agents/research-agent`
package on disk -- the same dynamic-import mechanism (`domain/
execution_backend.py::_load_handler_class`) Registry's own install pipeline
uses, exercised here at dispatch time instead of install time. A fake
`ModelGatewayPort` stands in for the real `ai_model.generate.request` RPC.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from nova_agent_os_kernel.domain.execution_backend import InprocessExecutionBackend
from nova_agent_sdk import AgentContext
from nova_contracts import (
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
