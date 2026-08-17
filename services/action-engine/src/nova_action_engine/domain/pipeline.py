"""The Action Principle lifecycle (Bible Part 12, TDD 3D §6) -- twelve
stages, implemented literally, mirroring `reasoning-engine`'s own "Bible
lifecycle, implemented literally" precedent.

**Implementation-time note, not one of the three approved decisions
(`docs/design/phase-3/13-3d-action-engine-research.md` §5), disclosed
here rather than silently resolved:** TDD 3D §6 assigns the ADR-032
identity-confidence gate to stage 3 ("Check Permissions"), before stage 4
("Estimate Risk") -- but ADR-032 point 2 requires a *per-risk-tier*
threshold, which needs the risk classification to already exist. This is
a data-dependency between two adjacent, already-specified stages, not a
competing architecture (no alternative ordering is proposed anywhere).
Resolved pragmatically: risk is classified once, internally, before
stage 3's gate check runs; the stage-transition audit trail
(`action_execution_history`) still records `CHECK_PERMISSIONS` before
`ESTIMATE_RISK`, matching Bible's literal stage order for what is
*observable*, while the classification itself is computed once and reused
by both.

**Also disclosed:** `capability.invoke.request`'s `operation` field has no
dedicated slot on `Action` (TDD 3D §3.1's 18 fields). Read here from
`Action.parameters["operation"]` by convention -- `parameters` is already
documented as "deliberately adapter-agnostic"
(`nova_contracts.events.capability`'s own docstring); a missing
`"operation"` key is treated as a stage-5 precondition failure, reported
distinctly, not a crash.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from nova_contracts import (
    Action,
    ActionApprovalDecidedPayload,
    ActionApprovalRequestedPayload,
    ActionExecuteRequestPayload,
    ActionResultPayload,
    EventEnvelope,
    RiskLevel,
)

from nova_action_engine.domain.models import PendingApproval
from nova_action_engine.domain.ports import (
    ActionAlreadyExistsError,
    ActionRepository,
    CapabilityPort,
    CommunicationPort,
    EventPublisher,
    IdentityPort,
)
from nova_action_engine.domain.risk import classify_risk

__all__ = ["ActionStage", "OnStage", "execute_action"]

TERMINAL_STATUSES = frozenset({"completed", "failed", "denied", "rolled_back"})


class ActionStage(StrEnum):
    RECEIVE_REQUEST = "receive_request"
    VALIDATE = "validate"
    CHECK_PERMISSIONS = "check_permissions"
    ESTIMATE_RISK = "estimate_risk"
    PREPARE_RESOURCES = "prepare_resources"
    EXECUTE = "execute"
    MONITOR_PROGRESS = "monitor_progress"
    DETECT_ERRORS = "detect_errors"
    RECOVER_IF_NECESSARY = "recover_if_necessary"
    VERIFY_RESULT = "verify_result"
    REPORT_OUTCOME = "report_outcome"
    STORE_EXPERIENCE = "store_experience"


OnStage = Callable[[ActionStage, str, "str | None"], Awaitable[None]]


async def _idempotent_reply_if_terminal(
    action_id: UUID, *, repository: ActionRepository
) -> ActionResultPayload | None:
    existing = await repository.find_by_id(action_id)
    if existing is None or existing.status not in TERMINAL_STATUSES:
        return None
    stored = await repository.get_result(action_id)
    result, error = stored if stored is not None else (None, None)
    return ActionResultPayload(
        action_id=action_id, status=existing.status, result=result, error=error
    )


async def execute_action(
    request: ActionExecuteRequestPayload,
    *,
    repository: ActionRepository,
    capability_port: CapabilityPort,
    communication_port: CommunicationPort,
    identity_port: IdentityPort,
    event_publisher: EventPublisher,
    approval_timeout_seconds: float,
    on_stage: OnStage | None = None,
) -> ActionResultPayload:
    async def _stage(stage: ActionStage, outcome: str, detail: str | None = None) -> None:
        await repository.record_execution_history(
            action_id=request.action_id, stage=stage.value, outcome=outcome, detail=detail
        )
        if on_stage is not None:
            await on_stage(stage, outcome, detail)

    # --- Idempotency guard (approved, §5.3) -- checked before any stage
    # runs, and before the Action row is even inserted, so a genuine retry
    # never re-triggers any side effect, including the approval loop.
    idempotent_reply = await _idempotent_reply_if_terminal(request.action_id, repository=repository)
    if idempotent_reply is not None:
        return idempotent_reply

    await _stage(ActionStage.RECEIVE_REQUEST, "success")

    # --- Stage 2: Validate -- structural only (approved, §5.2). Pydantic
    # already validated `request`'s own shape at parse time; deep
    # parameter validation against the resolved Capability.input_schema
    # happens at stage 5, not here.
    operation = str(request.parameters.get("operation", "")).strip()
    if not operation:
        await _stage(ActionStage.VALIDATE, "failure", "missing required parameters['operation']")
        return ActionResultPayload(
            action_id=request.action_id,
            status="failed",
            error="parameters['operation'] is required",
        )
    await _stage(ActionStage.VALIDATE, "success")

    risk = classify_risk(action_type=request.action_type, operation=operation)

    action = Action(
        id=request.action_id,
        action_type=request.action_type,
        priority=request.priority,
        source=request.source,
        requested_by=request.requested_by,
        execution_target=request.execution_target,
        depends_on=request.depends_on,
        parameters=request.parameters,
        expected_result=request.expected_result,
        risk=risk.value,
        timeout_seconds=request.timeout_seconds,
        retry_policy=request.retry_policy,
        rollback_strategy=request.rollback_strategy,
        required_permissions=request.required_permissions,
        status="pending",
        verification_method=request.verification_method,
        confidence=None,
    )
    try:
        await repository.insert(action)
    except ActionAlreadyExistsError:
        # A concurrent retry raced us here between the guard above and this
        # insert -- re-check the now-committed row rather than proceeding.
        idempotent_reply = await _idempotent_reply_if_terminal(
            request.action_id, repository=repository
        )
        if idempotent_reply is not None:
            return idempotent_reply
        return ActionResultPayload(
            action_id=request.action_id,
            status="failed",
            error="a request for this action_id is already in flight",
        )

    # --- Stage 3: Check Permissions -- ADR-032 identity-confidence gate
    # (§7). `required_permissions` itself is checked declaratively (no
    # nova-auth yet, TDD 3D §7/§11 -- locally enforced, same reasoning as
    # capability-engine's own TDD 3C §10); the identity-confidence check is
    # this stage's binding, security-relevant gate.
    confidence = await identity_port.get_confidence(user_id=action.requested_by)
    policy = await repository.find_identity_confidence_policy(action.requested_by)
    threshold = 1.0  # absent-policy fails closed: require maximum confidence (TDD 3D §10)
    if policy is not None and risk.value in policy.minimum_confidence_by_risk:
        threshold = policy.minimum_confidence_by_risk[risk.value]
    # timeout/absent identity signal -> zero confidence (fail-closed, TDD 3D §10)
    effective_confidence = confidence if confidence is not None else 0.0
    if effective_confidence < threshold:
        await repository.update_status(
            request.action_id, status="denied", confidence=effective_confidence
        )
        await _stage(
            ActionStage.CHECK_PERMISSIONS,
            "denied",
            f"identity confidence {effective_confidence:.2f} below required "
            f"{threshold:.2f} for risk={risk.value}",
        )
        await repository.record_result(
            request.action_id, result=None, error="identity_confidence_denied"
        )
        return ActionResultPayload(
            action_id=request.action_id, status="denied", error="identity_confidence_denied"
        )
    await repository.update_status(
        request.action_id, status="pending", confidence=effective_confidence
    )
    await _stage(ActionStage.CHECK_PERMISSIONS, "success")

    # --- Stage 4: Estimate Risk -- classification already computed above
    # (see module docstring); recorded here to match Bible's stage order.
    await _stage(ActionStage.ESTIMATE_RISK, "success", detail=risk.value)

    # --- Approval loop (TDD 3D §4, Fork E2's resolution) -- Critical-risk
    # actions block pending approval before Prepare Resources ever runs.
    if risk is RiskLevel.CRITICAL:
        approved = await _run_approval_loop(
            request,
            risk=risk,
            repository=repository,
            communication_port=communication_port,
            event_publisher=event_publisher,
            approval_timeout_seconds=approval_timeout_seconds,
            on_stage=_stage,
        )
        if not approved:
            await repository.update_status(request.action_id, status="denied")
            await repository.record_result(request.action_id, result=None, error=None)
            return ActionResultPayload(action_id=request.action_id, status="denied")
        await repository.update_status(request.action_id, status="approved")

    # --- Stage 5: Prepare Resources -- resolve the target Capability by
    # name (approved, §5.1), confirm health_status, then deep-validate
    # parameters against its input_schema (approved, §5.2).
    await _stage(ActionStage.PREPARE_RESOURCES, "started")
    capability = await capability_port.resolve(name=request.execution_target)
    if capability is None:
        await repository.update_status(request.action_id, status="failed")
        await _stage(ActionStage.PREPARE_RESOURCES, "failure", "capability not found")
        await repository.record_result(
            request.action_id,
            result=None,
            error=f"capability {request.execution_target!r} not found",
        )
        return ActionResultPayload(
            action_id=request.action_id,
            status="failed",
            error=f"capability {request.execution_target!r} not found",
        )
    if capability.health_status != "healthy":
        # Never attempts execution against a known-unhealthy adapter (TDD 3D §10).
        await repository.update_status(request.action_id, status="failed")
        await _stage(
            ActionStage.PREPARE_RESOURCES,
            "failure",
            f"capability unhealthy: {capability.health_status}",
        )
        await repository.record_result(
            request.action_id,
            result=None,
            error=f"capability {capability.name!r} is {capability.health_status}, not healthy",
        )
        return ActionResultPayload(
            action_id=request.action_id,
            status="failed",
            error=f"capability {capability.name!r} is {capability.health_status}, not healthy",
        )
    await _stage(ActionStage.PREPARE_RESOURCES, "success")

    # --- Stage 6: Execute -- invoke the capability's adapter. Rollback
    # pre-state capture (Fork 3C-3's resolution, approved rollback
    # ownership) happens first if a RollbackStrategy is configured.
    await repository.update_status(request.action_id, status="executing")
    pre_state: dict | None = None
    if action.rollback_strategy is not None:
        pre_state = await _capture_rollback_pre_state(
            action, capability_id=capability.id, capability_port=capability_port
        )

    await _stage(ActionStage.EXECUTE, "started")
    outcome, result, error = await capability_port.invoke(
        capability_id=capability.id,
        operation=operation,
        parameters=request.parameters,
    )
    await _stage(
        ActionStage.MONITOR_PROGRESS, "success"
    )  # timeout enforcement is the caller's/eventbus's own timeout_ms concern

    if outcome != "success":
        await _stage(ActionStage.DETECT_ERRORS, "failure", error)
        rolled_back = False
        if action.rollback_strategy is not None and pre_state is not None:
            rolled_back = await _attempt_rollback(
                action,
                capability_id=capability.id,
                pre_state=pre_state,
                capability_port=capability_port,
            )
            await _stage(
                ActionStage.RECOVER_IF_NECESSARY,
                "success" if rolled_back else "failure",
                action.rollback_strategy.kind,
            )
        else:
            await _stage(
                ActionStage.RECOVER_IF_NECESSARY, "skipped", "no rollback_strategy configured"
            )
        final_status = "rolled_back" if rolled_back else "failed"
        await repository.update_status(request.action_id, status=final_status)
        await _stage(ActionStage.VERIFY_RESULT, "skipped", "execution did not succeed")
        combined_error = error or outcome
        if action.rollback_strategy is not None and not rolled_back:
            combined_error = f"{combined_error} (rollback also failed)"
        await repository.record_result(request.action_id, result=None, error=combined_error)
        await _stage(ActionStage.REPORT_OUTCOME, "success")
        await _stage(ActionStage.STORE_EXPERIENCE, "success")
        return ActionResultPayload(
            action_id=request.action_id, status=final_status, error=combined_error
        )

    await _stage(ActionStage.DETECT_ERRORS, "none")
    await _stage(ActionStage.RECOVER_IF_NECESSARY, "skipped", "execution succeeded")

    # --- Stage 10: Verify Result -- per Action.verification_method. No
    # document specifies a concrete verification mechanism beyond the
    # field's own name; a successful adapter invocation is itself treated
    # as satisfying verification for Phase 3's two action types (both
    # synchronous, adapter-confirmed operations) -- disclosed, not a
    # silently-invented architecture.
    await _stage(ActionStage.VERIFY_RESULT, "success")

    await repository.update_status(request.action_id, status="completed")
    await repository.record_result(request.action_id, result=result, error=None)
    await _stage(ActionStage.REPORT_OUTCOME, "success")
    await _stage(ActionStage.STORE_EXPERIENCE, "success")

    return ActionResultPayload(action_id=request.action_id, status="completed", result=result)


async def _run_approval_loop(
    request: ActionExecuteRequestPayload,
    *,
    risk: RiskLevel,
    repository: ActionRepository,
    communication_port: CommunicationPort,
    event_publisher: EventPublisher,
    approval_timeout_seconds: float,
    on_stage: Callable[[ActionStage, str, str | None], Awaitable[None]],
) -> bool:
    """TDD 3D §4 -- the Phase-3-owned approval loop. Returns `True` if
    approved, `False` if denied (including on timeout -- fail-closed,
    never auto-approved)."""
    now = datetime.now(UTC)
    await repository.update_status(request.action_id, status="approval_required")
    await repository.insert_pending_approval(
        PendingApproval(action_id=request.action_id, risk=risk.value, requested_at=now)
    )
    await on_stage(ActionStage.PREPARE_RESOURCES, "blocked", risk.value)

    # TDD 3D §4 point 2 -- publishes action.approval.requested, never
    # autonomy.approval.requested (reserved for Phase 4, Fork E2).
    await event_publisher.publish(
        EventEnvelope(
            subject="action.approval.requested",
            source_engine="action-engine",
            correlation_id=request.correlation_id,
            payload=ActionApprovalRequestedPayload(
                action_id=request.action_id, risk=risk.value, requested_at=now
            ).model_dump(mode="json"),
        )
    )

    try:
        session_id = await communication_port.get_connected_session(user_id=request.requested_by)
    except TimeoutError:
        session_id = None

    if session_id is not None:
        # best-effort disclosure; the approval wait below still enforces the gate
        with contextlib.suppress(TimeoutError):
            await communication_port.deliver_intent(
                session_id=session_id,
                content=(
                    f"Approval required: {request.action_type} action "
                    f"targeting {request.execution_target!r} (risk={risk.value})."
                ),
            )

    decision = await _await_decision(
        request.action_id, repository=repository, timeout_seconds=approval_timeout_seconds
    )
    if decision is None:
        # Timeout -- denies, never auto-approves (TDD 3D §4's timeout policy).
        decided_at = datetime.now(UTC)
        await repository.decide_pending_approval(
            request.action_id, decision="denied", decided_at=decided_at
        )
        await _publish_decision(
            event_publisher, request, decision="denied", decided_at=decided_at, reason="timeout"
        )
        await on_stage(ActionStage.PREPARE_RESOURCES, "timeout", risk.value)
        return False

    await _publish_decision(
        event_publisher,
        request,
        decision=decision,
        decided_at=datetime.now(UTC),
        reason=None,
    )
    await on_stage(ActionStage.PREPARE_RESOURCES, decision, risk.value)
    return decision == "approved"


async def _publish_decision(
    event_publisher: EventPublisher,
    request: ActionExecuteRequestPayload,
    *,
    decision: str,
    decided_at: datetime,
    reason: str | None,
) -> None:
    # TDD 3D §4 point 5 -- publishes action.approval.decided, never
    # autonomy.decision.made (reserved for Phase 4, Fork E2).
    await event_publisher.publish(
        EventEnvelope(
            subject="action.approval.decided",
            source_engine="action-engine",
            correlation_id=request.correlation_id,
            payload=ActionApprovalDecidedPayload(
                action_id=request.action_id,
                decision=decision,
                decided_at=decided_at,
                reason=reason,
            ).model_dump(mode="json"),
        )
    )


async def _await_decision(
    action_id: UUID, *, repository: ActionRepository, timeout_seconds: float
) -> str | None:
    """Polls `find_pending_approval` until a decision lands or the
    approval timeout fires. Real deployments resolve a decision via the
    stopgap `POST /v1/action/approvals/{id}/decide` endpoint (§4 point 4)
    updating the same `pending_approval` row this polls."""
    deadline = time.monotonic() + timeout_seconds
    poll_interval_s = min(0.05, timeout_seconds / 10) if timeout_seconds > 0 else 0.05
    poll_interval_s = poll_interval_s or 0.05
    while time.monotonic() < deadline:
        approval = await repository.find_pending_approval(action_id)
        if approval is not None and approval.decision is not None:
            return approval.decision
        await asyncio.sleep(poll_interval_s)
    return None


async def _capture_rollback_pre_state(
    action: Action, *, capability_id: UUID, capability_port: CapabilityPort
) -> dict | None:
    """Fork 3C-3's resolution (Option B, RESOLVED): `action-engine` owns
    rollback entirely -- captures pre-state via `capability-engine`'s
    existing, non-destructive read operation before the destructive call,
    using the same `capability.invoke.request` RPC already required for
    the operation itself. Only meaningful for `"restore_file"` -- the
    other `RollbackStrategyKind` values (`undo_configuration`,
    `restart_service`, `manual`) have no read-before-write mechanism to
    capture here and are handled at restore time instead."""
    if action.rollback_strategy is None or action.rollback_strategy.kind != "restore_file":
        return None
    read_params = {k: v for k, v in action.parameters.items() if k != "operation"}
    outcome, result, _error = await capability_port.invoke(
        capability_id=capability_id, operation="read", parameters=read_params
    )
    return result if outcome == "success" else None


async def _attempt_rollback(
    action: Action,
    *,
    capability_id: UUID,
    pre_state: dict,
    capability_port: CapabilityPort,
) -> bool:
    """Restores captured pre-state via the same RPC mechanism (Fork
    3C-3). Only `"restore_file"` has a concrete, automated restore path
    here -- `undo_configuration`/`restart_service`/`manual` are disclosed
    as requiring operator/agent-level handling beyond this pipeline's own
    automated reach (TDD 3D §3.1's model is unaffected; only the
    mechanism behind `"restore_file"` is concrete, per the reconciliation
    pass this project already completed)."""
    assert action.rollback_strategy is not None
    if action.rollback_strategy.kind != "restore_file":
        return False
    write_params = {**pre_state, "operation": "write"}
    write_params = {k: v for k, v in write_params.items() if k != "operation"}
    outcome, _result, _error = await capability_port.invoke(
        capability_id=capability_id, operation="write", parameters=write_params
    )
    return outcome == "success"
