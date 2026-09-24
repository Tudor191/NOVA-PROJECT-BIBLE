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

**`execute` became reachable in 4F.5, behind seven independent preconditions.**
*(This paragraph read: "**`execute` is unreachable.** There is no branch in this
module that can produce `DecisionOutcome.EXECUTE`: `permits_execution()` is
unconditionally `False` (`levels.py`), and the one place its value is read
raises if it is ever `True`. TDD §16 control 1 requires that forcing `execute`
at Level 1 fails the suite; `_forbid_execution` is what it fails against.")*

`_dispatch_or_propose` is the only branch that can produce it, and it returns
`None` -- falling through to a suggestion, with **no RPC issued** -- unless
every precondition in TDD 4F.5 §22.4 holds. `_require_execution_path` replaces
`_forbid_execution` as control 3's target: a flag flipped without a wired
execution path still fails the suite.

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

from nova_contracts import ActionExecuteRequestPayload
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
from nova_autonomy_engine.domain.ports import (
    ActionDispatchPort,
    ActionDispatchTimeout,
    ActionDispatchUnavailable,
    ConversationalTrustSource,
)
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

    # --- 4F.5 execution fields (D-4F5-2) ------------------------------------
    #
    # `action.execute` mandates `action_type`, `execution_target` and
    # `verification_method`, and **nothing on this request could supply them**:
    # `category` has ten values against `ActionType`'s two, and the other two
    # have no analogue at all. So they are carried explicitly by whoever
    # actually knows them -- the trigger, which is 4F.6's -- rather than
    # derived.
    #
    # **Optional here, required at the dispatch branch.** A request without
    # them is a perfectly valid Level-0/1 decision; it is only an
    # *auto-executing* decision that cannot proceed without them, and it
    # degrades to a suggestion rather than failing (`_execution_payload`).
    #
    # **No defaults, and no guessing table.** A default would silently supply a
    # security-relevant value nobody chose, which is the failure mode D-4F5-2
    # forbids.
    action_type: str | None = None
    """`ActionType` (`"terminal"` | `"filesystem"`), validated by the contract
    when the payload is built rather than re-declared here."""
    execution_target: str | None = None
    verification_method: str | None = None


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


def _require_execution_path(level: AutonomyLevel, dispatcher: ActionDispatchPort | None) -> None:
    """The single read of `permits_execution`, guarded -- **4F.5 (D-4F5-4).**

    *(This replaced `_forbid_execution`, which raised whenever
    `permits_execution` returned `True` at all. Its message was: "no autonomy
    level may permit unattended execution in this release; level {n} claimed
    it. Enabling Level 2 is milestone 4F (decision D-1) and requires an
    execution path, not a flag." 4F.5 is that milestone, so the guard's meaning
    changes from "no level may execute" to "no level may execute without the
    wired execution path" -- the same protection against the same mistake.)*

    **This is what TDD 4F §16 control 3 fails against.** Flipping
    `permits_execution` to `True` while the dispatch path is absent raises
    here, so a flag-only enablement cannot produce a passing suite. It is
    deliberately *not* the thing that authorizes a dispatch: `decide()` still
    checks every other precondition in TDD 4F.5 §22.4 independently.
    """
    if permits_execution(level) and dispatcher is None:
        raise AssertionError(
            f"autonomy level {int(level)} is execution-eligible but no "
            f"ActionDispatchPort is wired. Level 2 requires an execution path, "
            f"not a flag (TDD 4F §16 control 3, TDD 4F.5 D-4F5-4)."
        )


def _execution_payload(
    request: DecisionRequest, *, subject_id: UUID
) -> ActionExecuteRequestPayload | None:
    """Build `action.execute`'s payload, or `None` if the request cannot
    supply it -- **4F.5 (D-4F5-2).**

    **`None` is a refusal to guess, not an error.** The three execution fields
    have no derivation available: `PermissionCategory` has ten values against
    `ActionType`'s two, and `execution_target`/`verification_method` have no
    analogue on a `DecisionRequest` at all. A missing field therefore degrades
    the decision to a suggestion rather than being filled in -- defaulting a
    security-relevant value nobody chose is exactly what D-4F5-2 forbids.

    `action_id` is `subject_id`, the id the decision log already minted, so the
    log row and the dispatched action share one identifier and
    `action-engine`'s caller-supplied-id idempotency guard keys on something
    this engine can point at.
    """
    if (
        request.action_type is None
        or request.execution_target is None
        or request.verification_method is None
    ):
        return None
    return ActionExecuteRequestPayload(
        action_id=subject_id,
        action_type=request.action_type,
        priority="normal",
        source="autonomy-engine",
        requested_by=request.user_id,
        execution_target=request.execution_target,
        parameters={},
        verification_method=request.verification_method,
        requesting_engine="autonomy-engine",
        correlation_id=subject_id,
    )


def _trust_denies(trust: TrustScore) -> bool:
    """Has a Trust implementation **affirmatively refused** this decision?

    **The CF-10 seam, and it is deliberately empty** -- TDD 4F.5 §22.7.

    Trust has three conceptual states. **PASS** is not reachable in 4F.5: no
    threshold exists and this slice creates none. **DENY** is blocking, and no
    `TrustInputStatus` expresses it -- `AVAILABLE`, `NO_DATA` and `UNAVAILABLE`
    are all *observations*, not refusals -- so this returns `False` today.
    **`UNAVAILABLE`** is CF-10's current state: **non-blocking here, and never
    a PASS.**

    Three things this function is careful *not* to be:

    * **not a `trust_passed` boolean.** It asks whether trust refused, so a
      `False` never means "trust approved" -- it means "nothing refused". A
      dispatch is attributable to §22.4's other preconditions, never to trust;
    * **not a threshold check.** `satisfies_threshold` is not called, here or
      anywhere on this path; were it called, `None` would correctly be `False`;
    * **not a coercion.** `TrustScore.score` stays `None`; nothing here reads
      it, defaults it, or turns it into a number.

    **CF-10's implementation owns the real semantics** -- the threshold, the
    states and the policy -- and will fill this seam without touching
    `action-engine`'s stage 3, which remains an independent fail-closed gate on
    every action regardless of what this returns.
    """
    return False


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
    """**Defaults to `True`, and 4F.5 did not change that.**

    At Levels 0-1 approval is always required, so the safe value is the default
    and a policy or grant can only confirm it. 4D recorded it for the log *"so
    that when 4F enables Level 2 the signal is already being carried rather
    than needing to be retrofitted"* -- which is exactly how 4F.5 uses it.

    **Only an affirmative, in-bounds `AUTO_EXECUTE` lowers it** (D-4F5-1).
    Absence of any policy leaves it `True`, so an empty policy set still means
    approval, never execution -- the fail-closed property is structural rather
    than a consequence of writing policies correctly. And `False` here is still
    not permission to dispatch: it is one of the seven preconditions in TDD
    4F.5 §22.4."""
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

    # 4F.5: the *only* place `requires_approval` can fall below its `True`
    # default, and it takes an affirmative in-bounds `AUTO_EXECUTE` to do it.
    # `policy_result.auto_execute` is already narrowed by `evaluate_policies`
    # to "matched, nothing denied, no REQUIRE_APPROVAL, at or below low", so an
    # empty or non-matching policy set leaves this `True` and the Level-2 path
    # closed. Reaching here at all means both denying gates passed.
    return GateReport(
        denied=False,
        requires_approval=not policy_result.auto_execute,
        policy_checks=policy_result.checks,
    )


async def _dispatch_or_propose(
    request: DecisionRequest,
    *,
    level: AutonomyLevel,
    subject_id: UUID,
    checks: list[PolicyCheck],
    trust: TrustScore,
    confidence: float,
    dispatcher: ActionDispatchPort | None,
    moment: datetime,
) -> DecisionResult | None:
    """Dispatch `action.execute`, or return `None` to fall through to a
    suggestion -- **TDD 4F.5 §22.4's precondition set.**

    Reached only when policy lowered `requires_approval`, which is precondition
    2 and is already behind preconditions 3 and 7 (`evaluate_gates` returns
    `denied` for a policy or permission refusal, and `decide` returns before
    this on `denied`). The remaining four are checked here, **each
    independently load-bearing** -- X-15 asserts that by removing them one at a
    time.

    **`None` means "nothing was executed".** Every refusal below returns before
    `dispatcher.dispatch`, so a decision that falls through has provably
    dispatched nothing.

    **`ActionDispatchUnavailable` propagates** rather than being turned into
    `None` here, so `decide()` can say *why* the decision did not execute. It
    is the one case where `dispatcher.dispatch` was called and still nothing
    ran: the broker had no subscriber and answered immediately. *(This
    paragraph read "**`None` means "no RPC was issued"**" until the 2026-09-21
    ratified fix pass, which found that a zero-subscriber dispatch is attempted
    but delivered to nobody; preserved per protocol §0.3.4.)*
    """
    # Precondition 1 -- level. `permits_execution` is *eligibility*: a Level-0
    # or Level-1 run with an AUTO_EXECUTE policy reaches here and is refused,
    # which is the whole point of the flag not being permission.
    if not permits_execution(level):
        return None

    # Precondition 6 -- the execution path is wired. Unreachable at Level 2
    # because `_require_execution_path` already raised, but load-bearing for a
    # lower level and cheap to keep honest.
    if dispatcher is None:
        return None

    # Precondition 4 -- no Trust DENY. `UNAVAILABLE` is not a denial and not a
    # pass (§22.7); nothing here reads `trust.score`, defaults it, or compares
    # it to a threshold.
    if _trust_denies(trust):
        return None

    # Precondition 5 -- the execution fields. Missing any one yields a
    # suggestion rather than a guessed action.
    payload = _execution_payload(request, subject_id=subject_id)
    if payload is None:
        return None

    # Every precondition holds. Exactly one request, and no retry on any
    # outcome -- `action-engine` may have executed an action it replied to
    # late, so re-sending could double-execute it.
    try:
        result = await dispatcher.dispatch(payload, correlation_id=subject_id)
    except ActionDispatchTimeout as exc:
        entry = DecisionLogEntry(
            subject_id=subject_id,
            autonomy_level=level,
            risk=request.risk,
            confidence=confidence,
            policy_checks=checks,
            outcome=DecisionOutcome.TIMEOUT,
            reason=str(exc),
            created_at=moment,
        )
        return DecisionResult(
            outcome=DecisionOutcome.TIMEOUT,
            reason=str(exc),
            policy_checks=checks,
            trust=trust,
            log_entry=entry,
        )

    reason = (
        f"auto-executed at autonomy level {int(level)} by policy; "
        f"action-engine reported {result.status}"
    )
    entry = DecisionLogEntry(
        subject_id=subject_id,
        autonomy_level=level,
        risk=request.risk,
        confidence=confidence,
        policy_checks=checks,
        outcome=DecisionOutcome.EXECUTE,
        reason=reason,
        created_at=moment,
    )
    return DecisionResult(
        outcome=DecisionOutcome.EXECUTE,
        reason=reason,
        policy_checks=checks,
        trust=trust,
        log_entry=entry,
    )


async def decide(
    request: DecisionRequest,
    *,
    level: AutonomyLevel,
    policies: Sequence[Policy],
    grants: Sequence[PermissionGrant],
    trust_source: ConversationalTrustSource,
    dispatcher: ActionDispatchPort | None = None,
    now: datetime | None = None,
    subject_id: UUID | None = None,
) -> DecisionResult:
    """Produce one decision.

    `trust_source` is awaited only if both denying gates pass, which is what
    makes §4.2's ordering observable: a spy source that records whether it was
    read proves a policy deny never reached it.

    **4F.5:** this may now dispatch `action.execute` -- but only through
    `_dispatch_or_propose`, and only when every precondition in TDD 4F.5 §22.4
    holds. `dispatcher` defaults to `None`, so a caller that does not supply
    one gets 4D's behaviour exactly: proposals and denials, never execution.
    *(The docstring read "**Never executes anything**, at any level." until
    4F.5 enabled Level 2.)*

    **4F.6 (A-4F6-3, Layer 1):** `subject_id` lets the orchestration boundary
    supply the decision's identity -- `decision_orchestration` derives it from
    the trigger envelope's `event_id`, so a redelivered envelope yields the same
    `subject_id`, the same `action_id` and `action-engine`'s existing replay.
    It is a **keyword on this function, never a field on `DecisionRequest`**:
    nothing a producer sends can reach it. Omitted, a fresh `uuid4()` is minted
    exactly as before, so every existing caller is unchanged.
    """
    _require_execution_path(level, dispatcher)
    moment = now or datetime.now(UTC)
    # Minted before the gates run so a `deny` and a `propose` log the same
    # `subject_id` shape. Doc 07's column is `action_id UUID NOT NULL`, so a
    # denied decision still needs an id -- minting one here makes a denial a
    # first-class, queryable log row rather than a row with a synthetic
    # sentinel. 4F.6: a caller-derived id is used instead when one is given.
    subject_id = subject_id if subject_id is not None else uuid4()

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

    # --- THE SINGLE DISPATCH POINT (TDD 4F §6.6, TDD 4F.5 §22.4) -----------
    #
    # Everything above this line is identical between a Level-1 and a Level-2
    # run: same request shape, same gate order, same trust read, same log
    # construction. That is what makes AC-8's "no code path differs" literally
    # true rather than rhetorically true, and what X-8 asserts with a spy.
    unavailable: str | None = None
    if not gates.requires_approval:
        try:
            dispatched = await _dispatch_or_propose(
                request,
                level=level,
                subject_id=subject_id,
                checks=checks,
                trust=trust,
                confidence=confidence,
                dispatcher=dispatcher,
                moment=moment,
            )
        except ActionDispatchUnavailable as exc:
            # §22.4 precondition 6 proving false at runtime: the path looked
            # wired, and the broker had nobody on the other end. §22.4's own
            # consequence applies unchanged -- no execution, the decision stays
            # non-executing, fail-safe preserved -- so this joins the ordinary
            # proposal path below rather than inventing an outcome. The reason
            # is kept specific so the log row does not read like an ordinary
            # approval requirement. **Not a TIMEOUT:** nothing received it.
            unavailable = str(exc)
        else:
            if dispatched is not None:
                return dispatched
            # Fell through: a precondition other than policy failed, so this is
            # a suggestion. No RPC was issued.

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
        reason=(
            f"proposed for explicit user approval; nothing is executed "
            f"({unavailable})"
            if unavailable is not None
            else "proposed for explicit user approval; nothing is executed"
        ),
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
