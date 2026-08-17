"""`domain.pipeline.execute_action` -- the twelve-stage Action Principle
lifecycle (TDD 3D §6), against fake ports/repository. Covers the three
approved decisions (§5.1/§5.2/§5.3,
`docs/design/phase-3/13-3d-action-engine-research.md`), the ADR-032
identity-confidence gate, the approval loop (Fork E2), and rollback (Fork
3C-3)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from nova_action_engine.domain.models import IdentityConfidencePolicy
from nova_action_engine.domain.pipeline import execute_action
from nova_contracts import ActionExecuteRequestPayload, Capability, RollbackStrategy

from tests.fakes.capability_port import FakeCapabilityPort
from tests.fakes.communication_port import FakeCommunicationPort
from tests.fakes.event_publisher import FakeEventPublisher
from tests.fakes.identity_port import FakeIdentityPort
from tests.fakes.repository import FakeActionRepository


def _request(**overrides: object) -> ActionExecuteRequestPayload:
    defaults: dict[str, object] = {
        "action_id": uuid4(),
        "action_type": "filesystem",
        "priority": "normal",
        "source": "test-suite",
        "requested_by": uuid4(),
        "execution_target": "filesystem",
        "parameters": {"operation": "read", "path": "/tmp/note.txt"},
        "verification_method": "adapter_confirmation",
        "requesting_engine": "test-caller-engine",
        "correlation_id": uuid4(),
    }
    defaults.update(overrides)
    return ActionExecuteRequestPayload(**defaults)  # type: ignore[arg-type]


def _capability(**overrides: object) -> Capability:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "name": "filesystem",
        "description": "Read, write, and list files.",
        "category": "filesystem",
        "version": "1.0.0",
        "required_permissions": ["filesystem:read"],
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "execution_adapter": "filesystem",
        "health_status": "healthy",
        "installed_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Capability(**defaults)  # type: ignore[arg-type]


async def _wait_for_pending_approval(repository: FakeActionRepository, action_id):  # type: ignore[no-untyped-def]
    """Deterministic wait, not a blind `sleep` -- this project's own
    established discipline against sleep-based flakiness (see the
    `fix-ci-communication-websocket-flake` precedent)."""
    for _ in range(200):
        pending = await repository.find_pending_approval(action_id)
        if pending is not None:
            return pending
        await asyncio.sleep(0.01)
    raise AssertionError("pending approval was never inserted")


class _Harness:
    def __init__(self, *, max_confidence: bool = True) -> None:
        self.repository = FakeActionRepository()
        self.capability_port = FakeCapabilityPort()
        self.communication_port = FakeCommunicationPort()
        self.identity_port = FakeIdentityPort()
        self.event_publisher = FakeEventPublisher()
        self.max_confidence = max_confidence

    async def run(
        self, request: ActionExecuteRequestPayload, *, approval_timeout_seconds: float = 5.0
    ):
        if self.max_confidence:
            self.identity_port.confidence_by_user[request.requested_by] = 1.0
        return await execute_action(
            request,
            repository=self.repository,
            capability_port=self.capability_port,
            communication_port=self.communication_port,
            identity_port=self.identity_port,
            event_publisher=self.event_publisher,
            approval_timeout_seconds=approval_timeout_seconds,
        )


async def test_validate_stage_is_structural_only_missing_operation_fails() -> None:
    """Approved decision §5.2: stage 2 checks only `parameters['operation']`
    presence -- never the resolved `Capability.input_schema`, which does
    not exist yet at this point in the pipeline."""
    harness = _Harness()
    result = await harness.run(_request(parameters={"path": "/tmp/note.txt"}))
    assert result.status == "failed"
    assert result.error is not None and "operation" in result.error
    assert harness.capability_port.resolve_calls == []


async def test_adr032_gate_denies_when_confidence_below_threshold() -> None:
    harness = _Harness(max_confidence=False)
    request = _request()
    harness.identity_port.confidence_by_user[request.requested_by] = 0.2
    harness.repository.identity_confidence_policies[request.requested_by] = (
        IdentityConfidencePolicy(
            user_id=request.requested_by, minimum_confidence_by_risk={"negligible": 0.9}
        )
    )
    result = await harness.run(request)
    assert result.status == "denied"
    assert result.error == "identity_confidence_denied"
    assert harness.capability_port.resolve_calls == []


async def test_adr032_gate_fails_closed_on_absent_confidence_signal() -> None:
    """No policy, no confidence signal (`None`, e.g. a timeout) -> treated
    as zero confidence against the maximum-confidence-required default
    (TDD 3D §10) -- never silently bypasses the gate."""
    harness = _Harness(max_confidence=False)
    request = _request()
    result = await harness.run(request)
    assert result.status == "denied"
    assert result.error == "identity_confidence_denied"


async def test_adr032_gate_allows_when_confidence_meets_policy_threshold() -> None:
    harness = _Harness(max_confidence=False)
    request = _request()
    harness.identity_port.confidence_by_user[request.requested_by] = 0.5
    harness.repository.identity_confidence_policies[request.requested_by] = (
        IdentityConfidencePolicy(
            user_id=request.requested_by, minimum_confidence_by_risk={"negligible": 0.4}
        )
    )
    harness.capability_port.capabilities_by_name["filesystem"] = _capability()
    result = await harness.run(request)
    assert result.status == "completed"


async def test_prepare_resources_fails_when_capability_not_found() -> None:
    harness = _Harness()
    request = _request()
    result = await harness.run(request)
    assert result.status == "failed"
    assert result.error is not None and "not found" in result.error
    assert harness.capability_port.resolve_calls == ["filesystem"]


async def test_prepare_resources_fails_when_capability_unhealthy() -> None:
    harness = _Harness()
    harness.capability_port.capabilities_by_name["filesystem"] = _capability(
        health_status="degraded"
    )
    result = await harness.run(_request())
    assert result.status == "failed"
    assert result.error is not None and "degraded" in result.error
    assert harness.capability_port.invoke_calls == []


async def test_execution_target_resolves_by_capability_name() -> None:
    """Approved decision §5.1: `execution_target` is the target
    Capability's stable `name`, resolved via `CapabilityPort.resolve(name=...)`."""
    harness = _Harness()
    capability = _capability(name="git")
    harness.capability_port.capabilities_by_name["git"] = capability
    harness.capability_port.queue_invoke_result(
        capability.id, "read", ("success", {"content": "hi"}, None)
    )
    result = await harness.run(
        _request(execution_target="git", parameters={"operation": "read"})
    )
    assert result.status == "completed"
    assert result.result == {"content": "hi"}
    assert harness.capability_port.resolve_calls == ["git"]


async def test_successful_execution_reaches_completed_and_records_result() -> None:
    harness = _Harness()
    capability = _capability()
    harness.capability_port.capabilities_by_name["filesystem"] = capability
    harness.capability_port.queue_invoke_result(
        capability.id, "read", ("success", {"content": "hello"}, None)
    )
    request = _request()
    result = await harness.run(request)
    assert result.status == "completed"
    assert result.result == {"content": "hello"}
    assert harness.repository.results[request.action_id] == ({"content": "hello"}, None)


async def test_execution_failure_without_rollback_strategy_reaches_failed() -> None:
    harness = _Harness()
    capability = _capability()
    harness.capability_port.capabilities_by_name["filesystem"] = capability
    harness.capability_port.queue_invoke_result(
        capability.id, "read", ("failure", None, "adapter error")
    )
    result = await harness.run(_request())
    assert result.status == "failed"
    assert result.error == "adapter error"


async def test_execution_failure_with_rollback_strategy_attempts_restore_and_rolls_back() -> None:
    """Fork 3C-3 (resolved, Option B): `action-engine` owns rollback --
    a read-before-write pattern against `CapabilityPort.invoke()`. Only
    `restore_file` has a concrete, automated mechanism: pre-state is
    captured via a "read" before the destructive "write" runs; if that
    "write" fails, the captured pre-state is restored via a second "write"
    call. `capability_id`/`operation` are identical for both the action's
    own execute-stage "write" and the restore "write" -- the fake port
    queues per-call results in order to distinguish them."""
    harness = _Harness()
    capability = _capability()
    harness.capability_port.capabilities_by_name["filesystem"] = capability
    harness.capability_port.queue_invoke_result(
        capability.id, "read", ("success", {"content": "pre-state"}, None)
    )
    harness.capability_port.queue_invoke_result(
        capability.id, "write", ("failure", None, "disk full")
    )
    harness.capability_port.queue_invoke_result(capability.id, "write", ("success", {}, None))
    request = _request(
        parameters={"operation": "write", "path": "/tmp/note.txt", "content": "new"},
        rollback_strategy=RollbackStrategy(kind="restore_file"),
    )
    result = await harness.run(request)

    assert result.status == "rolled_back"
    assert result.error is not None and "disk full" in result.error
    operations = [c["operation"] for c in harness.capability_port.invoke_calls]
    assert operations == ["read", "write", "write"]


async def test_idempotent_replay_of_a_terminal_action_returns_stored_result() -> None:
    """Approved decision §5.3: natural-key idempotency on `Action.id` --
    a repeat request for an already-terminal `action_id` returns the
    stored result unmodified, never re-executes."""
    harness = _Harness()
    capability = _capability()
    harness.capability_port.capabilities_by_name["filesystem"] = capability
    harness.capability_port.queue_invoke_result(
        capability.id, "read", ("success", {"content": "hello"}, None)
    )
    request = _request()
    first = await harness.run(request)
    assert first.status == "completed"
    assert len(harness.capability_port.invoke_calls) == 1

    second = await harness.run(request)
    assert second == first
    # No second invocation -- the idempotency guard short-circuited before
    # stage 5 ("Prepare Resources") ever ran again.
    assert len(harness.capability_port.invoke_calls) == 1


async def test_a_concurrent_retry_racing_the_insert_is_reported_as_already_in_flight() -> None:
    """A genuine race: another in-flight call already inserted the row
    (still non-terminal) between this call's idempotency check and its own
    `insert()` -- `PostgresActionRepository`/`FakeActionRepository` both
    raise `ActionAlreadyExistsError` on the primary-key collision."""
    harness = _Harness()
    request = _request()
    # Simulate the race directly: pre-insert a non-terminal row for the
    # same action_id, as a concurrent in-flight call would have.
    from nova_contracts import Action, RetryPolicy

    await harness.repository.insert(
        Action(
            id=request.action_id,
            action_type=request.action_type,
            priority=request.priority,
            source=request.source,
            requested_by=request.requested_by,
            execution_target=request.execution_target,
            parameters=request.parameters,
            risk="negligible",
            timeout_seconds=request.timeout_seconds,
            retry_policy=RetryPolicy(),
            status="executing",
            verification_method=request.verification_method,
        )
    )
    result = await harness.run(request)
    assert result.status == "failed"
    assert result.error == "a request for this action_id is already in flight"


async def test_critical_risk_action_blocks_in_approval_loop_and_publishes_requested_event() -> None:
    harness = _Harness()
    capability = _capability()
    harness.capability_port.capabilities_by_name["filesystem"] = capability
    request = _request(parameters={"operation": "delete", "path": "/tmp/note.txt"})

    async def _decide_shortly() -> None:
        pending = await _wait_for_pending_approval(harness.repository, request.action_id)
        assert pending.risk == "critical"
        await harness.repository.decide_pending_approval(
            request.action_id, decision="approved", decided_at=datetime.now(UTC)
        )

    decider = asyncio.create_task(_decide_shortly())
    harness.capability_port.queue_invoke_result(capability.id, "delete", ("success", {}, None))
    result = await harness.run(request, approval_timeout_seconds=2.0)
    await decider

    assert result.status == "completed"
    subjects = [e.subject for e in harness.event_publisher.published]
    assert "action.approval.requested" in subjects
    assert "action.approval.decided" in subjects


async def test_critical_risk_action_denied_by_explicit_decision_never_executes() -> None:
    harness = _Harness()
    capability = _capability()
    harness.capability_port.capabilities_by_name["filesystem"] = capability
    request = _request(parameters={"operation": "delete", "path": "/tmp/note.txt"})

    async def _deny_shortly() -> None:
        await _wait_for_pending_approval(harness.repository, request.action_id)
        await harness.repository.decide_pending_approval(
            request.action_id, decision="denied", decided_at=datetime.now(UTC)
        )

    decider = asyncio.create_task(_deny_shortly())
    result = await harness.run(request, approval_timeout_seconds=2.0)
    await decider

    assert result.status == "denied"
    assert harness.capability_port.invoke_calls == []


async def test_critical_risk_action_timeout_denies_never_auto_approves() -> None:
    """TDD 3D §4's timeout policy: an approval timeout **denies**, never
    auto-approves -- this project's standing fail-closed discipline."""
    harness = _Harness()
    capability = _capability()
    harness.capability_port.capabilities_by_name["filesystem"] = capability
    request = _request(parameters={"operation": "delete", "path": "/tmp/note.txt"})

    result = await harness.run(request, approval_timeout_seconds=0.05)

    assert result.status == "denied"
    assert harness.capability_port.invoke_calls == []
    reasons = [
        e.payload.get("reason")
        for e in harness.event_publisher.published
        if e.subject == "action.approval.decided"
    ]
    assert "timeout" in reasons
