"""The decision pipeline -- TDD 4D §4.2, §4.3; Bible Part 14 "THE AUTONOMY
PRINCIPLE" and "DECISION ENGINE".

Part 14 lists eleven steps. 4D implements the **gating subset** Levels 0-1 can
honour, and TDD §4.2 names the rest as deferred. The steps this module runs, in
the order §4.2 makes **binding**:

    Check Policies (5) -> Check Permissions (6) -> Trust -> Decide (8)

**Why the order is binding, and how it is enforced.** §4.2: *"A policy denial
must be reachable without consulting trust, and a permission denial without
consulting identity confidence -- so that a deny is attributable to exactly
one gate."* `decide()` therefore takes the trust input as a **port it awaits**,
not a value it is handed: a policy or permission denial returns before that
await, so a spy source proves the ordering rather than the test asserting it
from a reason string. Identity confidence is not consulted at any point in 4D
(CF-9, §11), so the second half of that clause holds trivially and
`confidence` on the log is this engine's own trust score.

**Why the level is applied at Decide and not first.** §4.3's table makes
`deny` reachable at **every** level, Level 0 included. Gating on the level
first would make a policy deny at Level 0 report as `observe_only`, hiding the
policy. So the gates run regardless of level, and the level chooses between
`observe_only` and `propose` only once nothing has denied -- which is exactly
where Part 14 puts step 8.

**`execute` is unreachable.** There is no branch in this module that can
produce `DecisionOutcome.EXECUTE`: `permits_execution()` is unconditionally
`False` (`levels.py`), and the one place its value is read raises if it is ever
`True`. TDD §16 control 1 requires that forcing `execute` at Level 1 fails the
suite; `_forbid_execution` is what it fails against.

**Deterministic and fail-closed.** The only non-pure inputs are `now` (passed
in, defaulted once) and the trust read (whose every failure mode is a `None`
score, never an exception -- `ConversationalTrustSource` forbids raising).
A policy evaluation that raises becomes a **deny**, per TDD §13: *"A policy
engine that fails open is not a policy engine."*
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from nova_contracts.events.planning import RiskLevel
from pydantic import BaseModel, Field

from nova_autonomy_engine.domain.levels import permits_execution, permits_proposal
from nova_autonomy_engine.domain.models import (
    AutonomyLevel,
    DecisionLogEntry,
    DecisionOutcome,
    PermissionCategory,
    PermissionGrant,
    Policy,
    PolicyCheck,
    Suggestion,
    TrustScore,
)
from nova_autonomy_engine.domain.permissions import evaluate_permission, find_grant
from nova_autonomy_engine.domain.policy import evaluate_policies
from nova_autonomy_engine.domain.ports import ConversationalTrustSource
from nova_autonomy_engine.domain.trust import compute_trust_score

__all__ = ["DecisionRequest", "DecisionResult", "GateReport", "decide", "evaluate_gates"]

_DENIED_CONFIDENCE = 0.0
"""Doc 07's `decision_log.confidence` is `REAL NOT NULL`, so a decision made
without a trust score records the fail-closed `0.0` **in the log only** --
`TrustScore.score` itself stays `None`. The log records what the gate acted on;
the score records what was known. Coercing the score itself would be TDD §16
control 3."""


class DecisionRequest(BaseModel):
    """What is being proposed. **`risk` arrives on the request and is not
    re-derived** (TDD §4.2 step 4): risk classification belongs to the engine
    that owns the action, and 4D consumes `action-engine`'s vocabulary rather
    than inventing a second classifier."""

    user_id: UUID
    category: PermissionCategory
    risk: RiskLevel
    title: str
    detail: str = ""
    capability_class: str | None = None
    priority: int = 0
    """Part 14 step 3 "Evaluate Importance", **carried not scored** (TDD §4.2):
    the field exists so a caller's own priority survives into the suggestion,
    and 4D does not compute one."""


class DecisionResult(BaseModel):
    """A decision and everything needed to explain it -- Part 14's Explanation
    Engine reduced to what 4D can honestly provide: *what policies were
    applied, what risks were considered* (TDD §14).

    `suggestion` is populated **only** for `PROPOSE`. It is constructed, not
    persisted: persisting it is `AutonomyRepository.insert_suggestion`'s job, in
    one transaction with `log_entry`.
    """

    outcome: DecisionOutcome
    reason: str
    gate: str | None = None
    """Which gate produced a `deny`, so a denial is attributable to exactly one
    -- §4.2's stated purpose for fixing the order. `None` when nothing
    denied."""
    policy_checks: list[PolicyCheck] = Field(default_factory=list)
    trust: TrustScore | None = None
    """`None` when a gate denied before the trust stage was reached. That
    `None` is itself the evidence for §4.2's ordering requirement, and
    `tests/unit/test_decision_pipeline.py` asserts it."""
    suggestion: Suggestion | None = None
    log_entry: DecisionLogEntry


def _forbid_execution(level: AutonomyLevel) -> None:
    """The single read of `permits_execution`, guarded.

    If some future edit makes `permits_execution` return `True` without also
    building a real execution path, every decision raises instead of silently
    acquiring one. This is the assertion TDD §16 control 1 fails against:
    forcing `execute` at Level 1 cannot produce a passing suite.
    """
    if permits_execution(level):
        raise AssertionError(
            f"no autonomy level may permit unattended execution in this release; "
            f"level {int(level)} claimed it. Enabling Level 2 is milestone 4F "
            f"(decision D-1) and requires an execution path, not a flag."
        )


class GateReport(BaseModel):
    """Which of the two denying gates a request passes, and why not.

    This is also what TDD §12's suggestion inbox renders -- *"each suggestion
    shows what is proposed, its risk, **which gates passed**"* -- so it is a
    named type rather than a tuple: the panel, the decision log and the
    approval path all read the same fields.

    Note there is no `allowed` field. `denied is False` means only that no gate
    refused; it never means anything may execute.
    """

    denied: bool = False
    gate: str | None = None
    """`"policy"` or `"permission"`, so a denial is attributable to exactly one
    gate -- §4.2's stated purpose for fixing the order. `None` when nothing
    denied."""
    reason: str | None = None
    requires_approval: bool = True
    """**Defaults to `True`.** At Levels 0-1 approval is always required, so
    the safe value is the default and a policy or grant can only confirm it.
    It is recorded for the log now so that when 4F enables Level 2 the signal
    is already being carried rather than needing to be retrofitted."""
    policy_checks: list[PolicyCheck] = Field(default_factory=list)


def evaluate_gates(
    request: DecisionRequest,
    *,
    policies: Sequence[Policy],
    grants: Sequence[PermissionGrant],
) -> GateReport:
    """Run the two denying gates in §4.2's order.

    Split out from `decide()` so the ordering is testable synchronously, and so
    the API's suggestion listing can report which gates a stored suggestion
    passes (TDD §12) without re-entering the async trust read for every row.

    A policy evaluation that raises is converted to a **deny** here, not
    propagated: TDD §13 requires a failing policy engine to fail closed.
    """
    try:
        policy_result = evaluate_policies(
            policies,
            category=request.category,
            risk=request.risk,
            capability_class=request.capability_class,
        )
    except Exception as exc:  # noqa: BLE001 - fail closed, deliberately broad
        return GateReport(
            denied=True,
            gate="policy",
            reason=f"policy evaluation failed and therefore denies: {exc!r}",
        )

    if policy_result.denied:
        # Deny wins: return before the permission gate is consulted, and long
        # before the trust read. No later gate can overturn this (§6 item 2).
        return GateReport(
            denied=True,
            gate="policy",
            reason=policy_result.reason,
            policy_checks=policy_result.checks,
        )

    permission_result = evaluate_permission(
        find_grant(grants, request.category), category=request.category, risk=request.risk
    )
    if permission_result.denied:
        return GateReport(
            denied=True,
            gate="permission",
            reason=permission_result.reason,
            policy_checks=policy_result.checks,
        )

    return GateReport(
        denied=False,
        requires_approval=True,
        policy_checks=policy_result.checks,
    )


async def decide(
    request: DecisionRequest,
    *,
    level: AutonomyLevel,
    policies: Sequence[Policy],
    grants: Sequence[PermissionGrant],
    trust_source: ConversationalTrustSource,
    now: datetime | None = None,
) -> DecisionResult:
    """Produce one decision. **Never executes anything**, at any level.

    `trust_source` is awaited only if both denying gates pass, which is what
    makes §4.2's ordering observable: a spy source that records whether it was
    read proves a policy deny never reached it.
    """
    _forbid_execution(level)
    moment = now or datetime.now(UTC)
    # Minted before the gates run so a `deny` and a `propose` log the same
    # `subject_id` shape. Doc 07's column is `action_id UUID NOT NULL`, so a
    # denied decision still needs an id -- minting one here makes a denial a
    # first-class, queryable log row rather than a row with a synthetic
    # sentinel.
    subject_id = uuid4()

    gates = evaluate_gates(request, policies=policies, grants=grants)
    checks = gates.policy_checks

    if gates.denied:
        entry = DecisionLogEntry(
            subject_id=subject_id,
            autonomy_level=level,
            risk=request.risk,
            confidence=_DENIED_CONFIDENCE,
            policy_checks=checks,
            outcome=DecisionOutcome.DENY,
            reason=gates.reason,
            created_at=moment,
        )
        return DecisionResult(
            outcome=DecisionOutcome.DENY,
            reason=gates.reason or "denied",
            gate=gates.gate,
            policy_checks=checks,
            trust=None,
            log_entry=entry,
        )

    # --- Trust stage. Recorded, never a denial in 4D: nothing executes at
    # Levels 0-1, so there is no threshold for trust to gate (trust.py).
    read = await trust_source.read(request.user_id)
    trust = compute_trust_score(
        user_id=request.user_id,
        category=request.category,
        conversational=read.snapshot,
        status=read.status,
        detail=read.detail,
        now=moment,
    )
    confidence = trust.score if trust.score is not None else _DENIED_CONFIDENCE

    # --- Decide (Part 14 step 8). The level chooses here, and only here.
    if not permits_proposal(level):
        entry = DecisionLogEntry(
            subject_id=subject_id,
            autonomy_level=level,
            risk=request.risk,
            confidence=confidence,
            policy_checks=checks,
            outcome=DecisionOutcome.OBSERVE_ONLY,
            reason=(
                f"autonomy level {int(level)} observes and reports only; no proposal "
                f"was recorded"
            ),
            created_at=moment,
        )
        return DecisionResult(
            outcome=DecisionOutcome.OBSERVE_ONLY,
            reason=entry.reason or "",
            policy_checks=checks,
            trust=trust,
            log_entry=entry,
        )

    suggestion = Suggestion(
        id=subject_id,
        user_id=request.user_id,
        category=request.category,
        risk=request.risk,
        title=request.title,
        detail=request.detail,
        created_at=moment,
    )
    entry = DecisionLogEntry(
        subject_id=subject_id,
        autonomy_level=level,
        risk=request.risk,
        confidence=confidence,
        policy_checks=checks,
        outcome=DecisionOutcome.PROPOSE,
        reason="proposed for explicit user approval; nothing is executed",
        created_at=moment,
    )
    return DecisionResult(
        outcome=DecisionOutcome.PROPOSE,
        reason=entry.reason or "",
        policy_checks=checks,
        trust=trust,
        suggestion=suggestion,
        log_entry=entry,
    )
