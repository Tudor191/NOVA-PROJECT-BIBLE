"""Round-trip serialization for `Action`/`RetryPolicy`/`RollbackStrategy`
and the 4 new `action.execute`/`action.result`/`action.approval.*`
payloads, plus subject registration (`nova_contracts.registry`) and the
Fork E2 namespace boundary -- mirrors every other engine's own
`tests/contract/` convention."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from nova_contracts import (
    Action,
    ActionApprovalDecidedPayload,
    ActionApprovalRequestedPayload,
    ActionExecuteRequestPayload,
    ActionResultPayload,
    RetryPolicy,
    RollbackStrategy,
)
from nova_contracts.registry import known_subjects, payload_model_for


def _action(**overrides: object) -> Action:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "action_type": "filesystem",
        "priority": "normal",
        "source": "test-suite",
        "requested_by": uuid4(),
        "execution_target": "filesystem",
        "risk": "negligible",
        "timeout_seconds": 30,
        "retry_policy": RetryPolicy(),
        "status": "pending",
        "verification_method": "adapter_confirmation",
    }
    defaults.update(overrides)
    return Action(**defaults)  # type: ignore[arg-type]


def test_action_round_trips_through_json() -> None:
    action = _action()
    restored = Action.model_validate_json(action.model_dump_json())
    assert restored == action


def test_action_with_rollback_strategy_round_trips() -> None:
    strategy = RollbackStrategy(kind="restore_file", detail="pre-write snapshot")
    action = _action(rollback_strategy=strategy)
    restored = Action.model_validate_json(action.model_dump_json())
    assert restored == action
    assert restored.rollback_strategy is not None
    assert restored.rollback_strategy.kind == "restore_file"


def test_retry_policy_defaults() -> None:
    policy = RetryPolicy()
    assert policy.max_retries == 0
    assert policy.backoff_seconds == 1.0


def test_execute_request_round_trips() -> None:
    request = ActionExecuteRequestPayload(
        action_id=uuid4(),
        action_type="terminal",
        priority="high",
        source="test-suite",
        requested_by=uuid4(),
        execution_target="terminal",
        parameters={"operation": "execute", "command": "ls"},
        verification_method="adapter_confirmation",
        requesting_engine="test-caller-engine",
        correlation_id=uuid4(),
    )
    restored = ActionExecuteRequestPayload.model_validate_json(request.model_dump_json())
    assert restored == request
    assert restored.schema_version == 1


def test_execute_request_omits_server_computed_fields() -> None:
    """`risk`/`status`/`confidence` are deliberately absent from the
    request payload -- server-computed by the Action Principle lifecycle's
    own stages, never caller-supplied."""
    fields = ActionExecuteRequestPayload.model_fields
    assert "risk" not in fields
    assert "status" not in fields
    assert "confidence" not in fields


def test_result_payload_round_trips_for_every_status() -> None:
    for status in (
        "pending",
        "approval_required",
        "approved",
        "denied",
        "executing",
        "completed",
        "failed",
        "rolled_back",
    ):
        payload = ActionResultPayload(action_id=uuid4(), status=status)  # type: ignore[arg-type]
        assert ActionResultPayload.model_validate_json(payload.model_dump_json()) == payload


def test_approval_requested_and_decided_round_trip() -> None:
    requested = ActionApprovalRequestedPayload(
        action_id=uuid4(), risk="critical", requested_at=datetime.now(UTC)
    )
    assert (
        ActionApprovalRequestedPayload.model_validate_json(requested.model_dump_json())
        == requested
    )

    decided = ActionApprovalDecidedPayload(
        action_id=uuid4(), decision="approved", decided_at=datetime.now(UTC)
    )
    assert ActionApprovalDecidedPayload.model_validate_json(decided.model_dump_json()) == decided

    timed_out = ActionApprovalDecidedPayload(
        action_id=uuid4(), decision="denied", decided_at=datetime.now(UTC), reason="timeout"
    )
    assert timed_out.reason == "timeout"


def test_every_action_subject_is_registered() -> None:
    subjects = known_subjects()
    assert "action.execute" in subjects
    assert "action.result" in subjects
    assert "action.approval.requested" in subjects
    assert "action.approval.decided" in subjects

    assert payload_model_for("action.execute") is ActionExecuteRequestPayload
    assert payload_model_for("action.result") is ActionResultPayload
    assert payload_model_for("action.approval.requested") is ActionApprovalRequestedPayload
    assert payload_model_for("action.approval.decided") is ActionApprovalDecidedPayload


def test_fork_e2_namespace_boundary_never_uses_autonomy_prefix() -> None:
    """Fork E2's resolution: this is a new, Phase-3-owned `action.approval.*`
    namespace -- never `autonomy.approval.*`/`autonomy.decision.made`,
    reserved for `autonomy-engine` to claim in Phase 4."""
    subjects = known_subjects()
    assert "autonomy.approval.requested" not in subjects
    assert "autonomy.decision.made" not in subjects


def test_every_new_payload_carries_a_schema_version() -> None:
    assert (
        ActionExecuteRequestPayload(
            action_id=uuid4(),
            action_type="filesystem",
            priority="normal",
            source="x",
            requested_by=uuid4(),
            execution_target="filesystem",
            verification_method="adapter_confirmation",
            requesting_engine="x",
            correlation_id=uuid4(),
        ).schema_version
        == 1
    )
    assert ActionResultPayload(action_id=uuid4(), status="completed").schema_version == 1
    assert (
        ActionApprovalRequestedPayload(
            action_id=uuid4(), risk="critical", requested_at=datetime.now(UTC)
        ).schema_version
        == 1
    )
    assert (
        ActionApprovalDecidedPayload(
            action_id=uuid4(), decision="denied", decided_at=datetime.now(UTC)
        ).schema_version
        == 1
    )
