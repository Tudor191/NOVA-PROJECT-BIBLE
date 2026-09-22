"""Autonomy Level 2 — the dispatch decision, and the seven preconditions that
gate it. **Phase 4F.5**, TDD 4F.5 §11 and §22.

**The negative tests are the point.** A Level-2 implementation that dispatched
slightly too eagerly would satisfy every happy-path assertion here and still be
a serious security defect, so every refusal has its own test and each
precondition is removed one at a time (X-15).

**Nothing here mocks the thing under test.** The policy engine, the permission
matrix, the gate order and `decide()` are all real; only the two ports are
substituted — `ConversationalTrustSource`, which is an Event-Bus read this
slice does not own, and `ActionDispatchPort`, whose *real* behaviour is proven
against real NATS in `tests/integration/test_level_two_real_postgres.py`. The
recording dispatcher here exists to count calls, which is a fact about
`decide()` rather than about the transport.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from nova_autonomy_engine.domain.decision import DecisionRequest, decide
from nova_autonomy_engine.domain.models import (
    AutonomyLevel,
    DecisionOutcome,
    PermissionCategory,
    PermissionGrant,
    Policy,
    PolicyEffect,
    PolicyMatch,
    TrustInputStatus,
)
from nova_autonomy_engine.domain.ports import (
    ActionDispatchResult,
    ActionDispatchTimeout,
    ActionDispatchUnavailable,
)
from nova_contracts import ActionExecuteRequestPayload
from nova_contracts.events.planning import RiskLevel

from tests.fakes.trust_source import StubTrustSource

USER = uuid4()

EXECUTION_FIELDS = {
    "action_type": "filesystem",
    "execution_target": "filesystem",
    "verification_method": "none",
}
"""The three fields D-4F5-2 requires at the dispatch branch. Named once so a
test that omits one omits it visibly."""


class RecordingDispatcher:
    """Counts dispatches and remembers payloads. **Counting is the assertion**:
    "exactly one" and "zero" are the two facts nearly every test here needs."""

    def __init__(self, *, raises: Exception | None = None) -> None:
        self.payloads: list[ActionExecuteRequestPayload] = []
        self.correlation_ids: list[UUID | None] = []
        self._raises = raises

    async def dispatch(
        self,
        payload: ActionExecuteRequestPayload,
        *,
        correlation_id: UUID | None = None,
    ) -> ActionDispatchResult:
        self.payloads.append(payload)
        self.correlation_ids.append(correlation_id)
        if self._raises is not None:
            raise self._raises
        return ActionDispatchResult(action_id=payload.action_id, status="completed")


def _request(
    *,
    risk: RiskLevel = RiskLevel.LOW,
    category: PermissionCategory = PermissionCategory.CREATE,
    **overrides: object,
) -> DecisionRequest:
    fields = {**EXECUTION_FIELDS, **overrides}
    return DecisionRequest(
        user_id=USER,
        category=category,
        risk=risk,
        title="rotate the scratch directory",
        **fields,  # type: ignore[arg-type]
    )


def _open_grant(category: PermissionCategory = PermissionCategory.CREATE) -> PermissionGrant:
    return PermissionGrant(user_id=USER, category=category, max_risk=RiskLevel.CRITICAL)


def _auto_execute(min_risk: RiskLevel | None = None) -> Policy:
    return Policy(
        user_id=USER,
        name="auto-execute low-risk creates",
        effect=PolicyEffect.AUTO_EXECUTE,
        match=PolicyMatch(category=PermissionCategory.CREATE, min_risk=min_risk),
    )


async def _decide(
    request: DecisionRequest,
    *,
    level: AutonomyLevel = AutonomyLevel.ASSISTED,
    policies: list[Policy] | None = None,
    grants: list[PermissionGrant] | None = None,
    dispatcher: RecordingDispatcher | None = None,
    trust_source: StubTrustSource | None = None,
):  # type: ignore[no-untyped-def]
    return await decide(
        request,
        level=level,
        policies=policies if policies is not None else [_auto_execute()],
        grants=grants if grants is not None else [_open_grant()],
        trust_source=trust_source if trust_source is not None else StubTrustSource(),
        dispatcher=dispatcher if dispatcher is not None else RecordingDispatcher(),
    )


def _cf10_trust() -> StubTrustSource:
    """CF-10's actual production state: the source could not be consulted, so
    `score` is `None` and the status is `UNAVAILABLE`. This is what
    `UnavailableConversationalTrustSource` — the only shipped adapter — returns
    on every read."""
    return StubTrustSource(status=TrustInputStatus.UNAVAILABLE)


# --- X-3 / invariant 3: the one case that dispatches -------------------------


async def test_auto_execute_at_low_with_every_gate_satisfied_dispatches_exactly_once() -> None:
    """**X-3, and invariant 3.** The slice's exit criterion: *"Stage 3 can pass
    for LOW risk"*, reached only with every applicable gate satisfied.

    *Exactly* one — a second dispatch would be a retry, which D-4F5-3 forbids.
    """
    dispatcher = RecordingDispatcher()
    result = await _decide(_request(), dispatcher=dispatcher)

    assert result.outcome is DecisionOutcome.EXECUTE
    assert len(dispatcher.payloads) == 1
    assert result.suggestion is None
    assert result.log_entry.outcome is DecisionOutcome.EXECUTE


async def test_negligible_risk_also_auto_executes() -> None:
    """The ceiling is `low` **inclusive of `negligible`**. Reading "low risk"
    as an equality test would leave `negligible` stricter than `low`, which is
    incoherent rather than merely conservative."""
    dispatcher = RecordingDispatcher()
    result = await _decide(_request(risk=RiskLevel.NEGLIGIBLE), dispatcher=dispatcher)

    assert result.outcome is DecisionOutcome.EXECUTE
    assert len(dispatcher.payloads) == 1


async def test_the_dispatched_payload_carries_the_decisions_own_identifiers() -> None:
    """`action_id` is the decision log's `subject_id`, so the log row and the
    dispatched action share one identifier."""
    dispatcher = RecordingDispatcher()
    result = await _decide(_request(), dispatcher=dispatcher)

    payload = dispatcher.payloads[0]
    assert payload.action_id == result.log_entry.subject_id
    assert payload.requested_by == USER
    assert payload.requesting_engine == "autonomy-engine"
    assert dispatcher.correlation_ids == [result.log_entry.subject_id]


# --- invariants 1, 2, 4, 5: policy refusals ----------------------------------


async def test_invariant_1_absent_policy_does_not_dispatch() -> None:
    """**The fail-closed control.** An empty policy set leaves
    `requires_approval` at its `True` default, so "no policy" means approval,
    never execution. Asserted before any admission test in file order."""
    dispatcher = RecordingDispatcher()
    result = await _decide(_request(), policies=[], dispatcher=dispatcher)

    assert result.outcome is DecisionOutcome.PROPOSE
    assert dispatcher.payloads == []


async def test_a_non_matching_auto_execute_policy_does_not_dispatch() -> None:
    """Absence of a *match* is as fail-closed as absence of a policy."""
    dispatcher = RecordingDispatcher()
    result = await _decide(
        _request(category=PermissionCategory.MODIFY),
        grants=[_open_grant(PermissionCategory.MODIFY)],
        dispatcher=dispatcher,
    )

    assert result.outcome is DecisionOutcome.PROPOSE
    assert dispatcher.payloads == []


async def test_invariant_2_a_deny_policy_does_not_dispatch() -> None:
    dispatcher = RecordingDispatcher()
    result = await _decide(
        _request(),
        policies=[Policy(user_id=USER, name="deny all", effect=PolicyEffect.DENY)],
        dispatcher=dispatcher,
    )

    assert result.outcome is DecisionOutcome.DENY
    assert dispatcher.payloads == []


@pytest.mark.parametrize("order", ["deny-first", "auto-first"])
async def test_invariant_5_deny_beats_auto_execute_at_any_ordering(order: str) -> None:
    """**Deny wins unconditionally.** Policy order must not decide a security
    question, so both orderings are swept."""
    deny = Policy(user_id=USER, name="deny all", effect=PolicyEffect.DENY)
    policies = [deny, _auto_execute()] if order == "deny-first" else [_auto_execute(), deny]

    dispatcher = RecordingDispatcher()
    result = await _decide(_request(), policies=policies, dispatcher=dispatcher)

    assert result.outcome is DecisionOutcome.DENY
    assert dispatcher.payloads == []


async def test_require_approval_beats_auto_execute() -> None:
    """A tier the operator marked for approval is not auto-executed because a
    second policy also matched. The stricter effect wins."""
    require = Policy(
        user_id=USER, name="approve creates", effect=PolicyEffect.REQUIRE_APPROVAL
    )
    dispatcher = RecordingDispatcher()
    result = await _decide(
        _request(), policies=[_auto_execute(), require], dispatcher=dispatcher
    )

    assert result.outcome is DecisionOutcome.PROPOSE
    assert dispatcher.payloads == []


@pytest.mark.parametrize(
    "risk", [RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.CRITICAL]
)
async def test_invariant_4_auto_execute_is_inert_above_low(risk: RiskLevel) -> None:
    """**`AUTO_EXECUTE` is inert above `low`**, so Bible Part 14's *"low risk
    actions execute automatically"* cannot be widened by policy. Swept over
    every tier above the ceiling, with a permitting policy present."""
    dispatcher = RecordingDispatcher()
    result = await _decide(
        _request(risk=risk), policies=[_auto_execute()], dispatcher=dispatcher
    )

    assert result.outcome is DecisionOutcome.PROPOSE
    assert dispatcher.payloads == []


# --- invariant 8: the Permission Matrix stays independently blocking ---------


async def test_invariant_8_a_permission_denial_does_not_dispatch() -> None:
    """The Permission Matrix is **independently** load-bearing: an
    `AUTO_EXECUTE` policy does not bypass it."""
    dispatcher = RecordingDispatcher()
    result = await _decide(_request(), grants=[], dispatcher=dispatcher)

    assert result.outcome is DecisionOutcome.DENY
    assert result.gate == "permission"
    assert dispatcher.payloads == []


async def test_a_grant_whose_ceiling_excludes_the_risk_does_not_dispatch() -> None:
    narrow = PermissionGrant(
        user_id=USER, category=PermissionCategory.CREATE, max_risk=RiskLevel.NEGLIGIBLE
    )
    dispatcher = RecordingDispatcher()
    result = await _decide(_request(risk=RiskLevel.LOW), grants=[narrow], dispatcher=dispatcher)

    assert result.outcome is DecisionOutcome.DENY
    assert dispatcher.payloads == []


# --- invariant 6 / X-14: the execution fields -------------------------------


@pytest.mark.parametrize(
    "missing", ["action_type", "execution_target", "verification_method"]
)
async def test_invariant_6_a_missing_execution_field_yields_a_suggestion(
    missing: str,
) -> None:
    """**X-14.** Each field removed in turn, with a matching `AUTO_EXECUTE`
    policy and every gate passing. The decision degrades to a suggestion and
    **nothing is guessed, defaulted or synthesized**."""
    dispatcher = RecordingDispatcher()
    result = await _decide(_request(**{missing: None}), dispatcher=dispatcher)

    assert result.outcome is DecisionOutcome.PROPOSE
    assert dispatcher.payloads == []
    assert result.suggestion is not None


async def test_a_request_with_no_execution_fields_at_all_yields_a_suggestion() -> None:
    """The default `DecisionRequest` — which is every 4D caller — is unchanged
    by 4F.5 and can never auto-execute."""
    dispatcher = RecordingDispatcher()
    bare = DecisionRequest(
        user_id=USER, category=PermissionCategory.CREATE, risk=RiskLevel.LOW, title="bare"
    )
    result = await _decide(bare, dispatcher=dispatcher)

    assert result.outcome is DecisionOutcome.PROPOSE
    assert dispatcher.payloads == []


# --- invariant 9 / X-15: eligibility is not permission ----------------------


@pytest.mark.parametrize(
    "level", [AutonomyLevel.OBSERVATION_ONLY, AutonomyLevel.SUGGESTIVE]
)
async def test_invariant_9_levels_below_two_never_dispatch(level: AutonomyLevel) -> None:
    """**Level is precondition 1, and it is load-bearing.** Even with a
    matching `AUTO_EXECUTE` policy, every gate passing and all execution fields
    present, Levels 0 and 1 dispatch nothing."""
    dispatcher = RecordingDispatcher()
    result = await _decide(_request(), level=level, dispatcher=dispatcher)

    assert result.outcome is not DecisionOutcome.EXECUTE
    assert dispatcher.payloads == []


async def test_x15_each_precondition_is_independently_load_bearing() -> None:
    """**X-15.** Start from the one configuration that dispatches, remove one
    precondition at a time, and assert **each removal alone** stops it.

    This is the test that makes "eligibility is not permission" concrete: the
    level stays `ASSISTED` and `permits_execution` stays `True` throughout."""
    baseline = RecordingDispatcher()
    assert (await _decide(_request(), dispatcher=baseline)).outcome is DecisionOutcome.EXECUTE
    assert len(baseline.payloads) == 1

    removals = {
        "policy": {"policies": []},
        "permission": {"grants": []},
        "execution fields": {"request": _request(action_type=None)},
        "level": {"level": AutonomyLevel.SUGGESTIVE},
    }
    for name, override in removals.items():
        dispatcher = RecordingDispatcher()
        request = override.pop("request", _request())  # type: ignore[arg-type]
        result = await _decide(request, dispatcher=dispatcher, **override)  # type: ignore[arg-type]
        assert result.outcome is not DecisionOutcome.EXECUTE, f"{name} was not load-bearing"
        assert dispatcher.payloads == [], f"{name} removed but a dispatch still happened"


# --- invariant 7 / X-16: the Trust contract ---------------------------------


async def test_invariant_7b_trust_unavailable_is_never_coerced_to_a_number() -> None:
    """**X-16, and the core of §22.7.** `TrustScore.score` stays `None` — never
    `0.0` (which would read as *perfect* trust after the score→corrections
    inversion), never `1.0`, never a default."""
    result = await _decide(_request(), trust_source=_cf10_trust())

    assert result.trust is not None
    assert result.trust.score is None
    assert result.trust.input_status is TrustInputStatus.UNAVAILABLE


async def test_invariant_7c_trust_unavailable_does_not_block_the_level_two_path() -> None:
    """**CF-10 is OPEN**, so trust is unavailable on every decision — and the
    dispatch above still happened. A gate held closed for a reason unrelated to
    the decision would be a dead path, not a safety property (§22.7)."""
    dispatcher = RecordingDispatcher()
    result = await _decide(_request(), dispatcher=dispatcher, trust_source=_cf10_trust())

    assert result.trust is not None
    assert result.trust.score is None
    assert result.trust.input_status is TrustInputStatus.UNAVAILABLE
    assert result.outcome is DecisionOutcome.EXECUTE
    assert len(dispatcher.payloads) == 1


async def test_invariant_7a_nothing_records_trust_as_having_passed() -> None:
    """**`UNAVAILABLE` is not a PASS.** The dispatch is attributable to the
    other preconditions; no field, reason or log entry claims trust approved.
    """
    result = await _decide(_request(), trust_source=_cf10_trust())

    assert "trust" not in result.reason.lower()
    assert "trust" not in (result.log_entry.reason or "").lower()
    assert not hasattr(result, "trust_passed")
    assert not hasattr(result.log_entry, "trust_passed")


async def test_invariant_7d_an_explicit_trust_denial_blocks_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**A future explicit Trust DENY remains blocking**, asserted against a
    constructed denial **without 4F.5 building the Trust implementation that
    would produce one** (§22.7).

    No `TrustInputStatus` expresses refusal today, so the seam is driven
    directly. This proves precondition 4 is wired and load-bearing, which is
    what lets CF-10's implementation fill it without re-plumbing `decide()`."""
    from nova_autonomy_engine.domain import decision as decision_module

    monkeypatch.setattr(decision_module, "_trust_denies", lambda _trust: True)

    dispatcher = RecordingDispatcher()
    result = await _decide(_request(), dispatcher=dispatcher, trust_source=_cf10_trust())

    assert result.outcome is DecisionOutcome.PROPOSE
    assert dispatcher.payloads == []


async def test_no_threshold_is_consulted_on_the_dispatch_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**4F.5 introduces no Trust threshold**, so `satisfies_threshold` is not
    called. Were it called with `None` it would correctly return `False` — and
    that would make Level 2 permanently undispatchable under an open CF-10,
    which is the contradiction §22.7 resolved."""
    from nova_autonomy_engine.domain import trust as trust_module

    def _explode(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError("satisfies_threshold must not be called on the dispatch path")

    monkeypatch.setattr(trust_module, "satisfies_threshold", _explode)

    result = await _decide(_request(), trust_source=_cf10_trust())
    assert result.outcome is DecisionOutcome.EXECUTE


# --- invariant 10 / X-13: the timeout ---------------------------------------


async def test_invariant_10_a_timeout_produces_the_timeout_outcome() -> None:
    """**X-13.** No reply within the bounded wait becomes
    `DecisionOutcome.TIMEOUT` — distinguishable from a policy denial *and* from
    an ordinary execution failure."""
    dispatcher = RecordingDispatcher(raises=ActionDispatchTimeout("no reply in 15.0s"))
    result = await _decide(_request(), dispatcher=dispatcher)

    assert result.outcome is DecisionOutcome.TIMEOUT
    assert result.outcome is not DecisionOutcome.DENY
    assert result.log_entry.outcome is DecisionOutcome.TIMEOUT


async def test_invariant_10_a_timeout_is_not_retried_and_dispatches_once() -> None:
    """**No retry, no second dispatch.** `action-engine` may have executed the
    action and replied late, so re-sending could double-execute it."""
    dispatcher = RecordingDispatcher(raises=ActionDispatchTimeout("no reply in 15.0s"))
    result = await _decide(_request(), dispatcher=dispatcher)

    assert result.outcome is DecisionOutcome.TIMEOUT
    assert len(dispatcher.payloads) == 1


async def test_a_timeout_does_not_claim_the_action_did_not_run() -> None:
    """The decision log records what this engine observed, not a conclusion it
    cannot support."""
    dispatcher = RecordingDispatcher(
        raises=ActionDispatchTimeout("no reply to action.execute within 15.0s")
    )
    result = await _decide(_request(), dispatcher=dispatcher)

    reason = (result.log_entry.reason or "").lower()
    assert "no reply" in reason
    assert "did not execute" not in reason
    assert "failed" not in reason


async def test_a_timeout_produces_no_suggestion() -> None:
    """A dispatched action is not also a proposal — the two outcomes are
    mutually exclusive."""
    dispatcher = RecordingDispatcher(raises=ActionDispatchTimeout("no reply"))
    result = await _decide(_request(), dispatcher=dispatcher)

    assert result.suggestion is None


# --- no responder: §22.4 precondition 6 failing at runtime -------------------
#
# **Ratified 2026-09-21 (D-1).** A broker with no `action.execute` subscriber
# is a *different fact* from a bounded wait elapsing, and the pair below is
# what keeps the two from merging back together.


async def test_no_responder_degrades_to_a_proposal() -> None:
    """**§22.4 precondition 6.** The path looked wired and the broker had
    nobody on it, so the ratified consequence applies unchanged: no execution,
    the decision stays non-executing, fail-safe preserved."""
    dispatcher = RecordingDispatcher(
        raises=ActionDispatchUnavailable("no subscriber on action.execute")
    )
    result = await _decide(_request(), dispatcher=dispatcher)

    assert result.outcome is DecisionOutcome.PROPOSE
    assert result.log_entry.outcome is DecisionOutcome.PROPOSE
    # Fail-safe: still reachable by explicit approval rather than discarded.
    assert result.suggestion is not None


async def test_no_responder_is_never_recorded_as_a_timeout() -> None:
    """**The point of D-1.** `TIMEOUT` stays reserved for the bounded
    15-second no-reply condition, which carries the hedge *"may still have
    executed"*. Nothing reached a responder here."""
    dispatcher = RecordingDispatcher(
        raises=ActionDispatchUnavailable("no subscriber on action.execute")
    )
    result = await _decide(_request(), dispatcher=dispatcher)

    assert result.outcome is not DecisionOutcome.TIMEOUT
    assert result.log_entry.outcome is not DecisionOutcome.TIMEOUT
    assert result.outcome is not DecisionOutcome.EXECUTE
    assert result.log_entry.outcome is not DecisionOutcome.EXECUTE


async def test_no_responder_is_not_retried_and_dispatches_once() -> None:
    """One attempt, and the decision ends there."""
    dispatcher = RecordingDispatcher(
        raises=ActionDispatchUnavailable("no subscriber on action.execute")
    )
    await _decide(_request(), dispatcher=dispatcher)

    assert len(dispatcher.payloads) == 1


async def test_the_log_row_explains_why_it_did_not_execute() -> None:
    """**The auditability requirement.** Reusing the existing proposal
    persistence is only acceptable if the row is still specific: an ordinary
    approval requirement and an unreachable executor must not read alike."""
    dispatcher = RecordingDispatcher(
        raises=ActionDispatchUnavailable(
            "no subscriber on action.execute for action X; the request reached "
            "nobody, so the action was not executed, and this is not retried"
        )
    )
    result = await _decide(_request(), dispatcher=dispatcher)

    reason = (result.log_entry.reason or "").lower()
    assert "no subscriber" in reason
    assert "was not executed" in reason
    # It must not borrow the timeout's hedge, which would be the opposite claim.
    assert "may still have executed" not in reason
    assert "no reply" not in reason


async def test_an_ordinary_proposal_is_not_labelled_unavailable() -> None:
    """The specific reason appears **only** on the unavailable path — a Level-1
    proposal keeps the plain wording it has always had."""
    result = await _decide(_request(), level=AutonomyLevel.SUGGESTIVE)

    reason = (result.log_entry.reason or "").lower()
    assert result.outcome is DecisionOutcome.PROPOSE
    assert "no subscriber" not in reason
    assert reason == "proposed for explicit user approval; nothing is executed"


# --- the Level-1 comparison: X-4 / X-8 --------------------------------------


async def test_x4_the_identical_request_at_level_one_proposes_and_dispatches_nothing() -> None:
    """**X-4, the negative half of AC-8.** Same request, same policies, same
    grants — only the level differs."""
    request = _request()
    policies = [_auto_execute()]

    level_two = RecordingDispatcher()
    executed = await _decide(request, policies=policies, dispatcher=level_two)

    level_one = RecordingDispatcher()
    proposed = await _decide(
        request, level=AutonomyLevel.SUGGESTIVE, policies=policies, dispatcher=level_one
    )

    assert executed.outcome is DecisionOutcome.EXECUTE
    assert len(level_two.payloads) == 1
    assert proposed.outcome is DecisionOutcome.PROPOSE
    assert level_one.payloads == []


async def test_x8_both_runs_consult_the_same_gates_in_the_same_order() -> None:
    """**X-8: "no code path differs"** up to the single dispatch point. Both
    runs read trust — the last gate before dispatch — so the divergence is at
    the dispatch point and nowhere earlier."""
    from tests.fakes.trust_source import SpyTrustSource

    request = _request()
    policies = [_auto_execute()]

    spy_two = SpyTrustSource()
    await decide(
        request,
        level=AutonomyLevel.ASSISTED,
        policies=policies,
        grants=[_open_grant()],
        trust_source=spy_two,
        dispatcher=RecordingDispatcher(),
    )

    spy_one = SpyTrustSource()
    await decide(
        request,
        level=AutonomyLevel.SUGGESTIVE,
        policies=policies,
        grants=[_open_grant()],
        trust_source=spy_one,
        dispatcher=RecordingDispatcher(),
    )

    assert spy_two.reads == spy_one.reads == [USER]


# --- the 4D behaviour a missing dispatcher preserves ------------------------


async def test_a_caller_that_supplies_no_dispatcher_keeps_4d_behaviour() -> None:
    """`dispatcher` defaults to `None`, so every 4D caller is unchanged: at
    Levels 0-1 nothing can execute regardless of policy."""
    result = await decide(
        _request(),
        level=AutonomyLevel.SUGGESTIVE,
        policies=[_auto_execute()],
        grants=[_open_grant()],
        trust_source=StubTrustSource(),
    )

    assert result.outcome is DecisionOutcome.PROPOSE


async def test_level_two_without_a_wired_dispatcher_raises_rather_than_executing() -> None:
    """**TDD 4F §16 control 3.** An execution-eligible level with no wired path
    fails loudly instead of quietly acquiring permission."""
    with pytest.raises(AssertionError, match="not a flag"):
        await decide(
            _request(),
            level=AutonomyLevel.ASSISTED,
            policies=[_auto_execute()],
            grants=[_open_grant()],
            trust_source=StubTrustSource(),
        )
