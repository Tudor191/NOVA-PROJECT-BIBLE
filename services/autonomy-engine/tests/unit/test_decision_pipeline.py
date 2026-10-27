"""The decision pipeline: gate order, the four outcomes, and **negative
controls 1, 6, 11 and 12** (TDD §16).

The ordering assertions use `SpyTrustSource` rather than reading a reason
string, so they test the control flow TDD §4.2 makes binding -- *"a policy
denial must be reachable without consulting trust"* -- and not the wording of a
message that could be kept while the flow changed underneath it.
"""

from __future__ import annotations

import itertools
from uuid import uuid4

import pytest
from nova_autonomy_engine.domain import decision as decision_module
from nova_autonomy_engine.domain import levels as levels_module
from nova_autonomy_engine.domain.decision import DecisionRequest, decide, evaluate_gates
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
from nova_autonomy_engine.domain.ports import ConversationalTrustRead
from nova_contracts.events.planning import RiskLevel

from tests.fakes.trust_source import SpyTrustSource, StubTrustSource

USER = uuid4()


def _request(
    *, category: PermissionCategory = PermissionCategory.CREATE, risk: RiskLevel = RiskLevel.LOW
) -> DecisionRequest:
    return DecisionRequest(
        user_id=USER, category=category, risk=risk, title="tidy the changelog"
    )


def _open_grant(category: PermissionCategory = PermissionCategory.CREATE) -> PermissionGrant:
    """The most permissive grant the Permission Matrix can express."""
    return PermissionGrant(user_id=USER, category=category, max_risk=RiskLevel.CRITICAL)


def _deny_all() -> Policy:
    return Policy(user_id=USER, name="deny everything", effect=PolicyEffect.DENY)


# --- §4.3's four outcomes ----------------------------------------------------
async def test_level_zero_observes_and_does_not_propose() -> None:
    """AC-5's first clause, negative half: Level 0 records the decision and
    produces no suggestion."""
    result = await decide(
        _request(),
        level=AutonomyLevel.OBSERVATION_ONLY,
        policies=[],
        grants=[_open_grant()],
        trust_source=StubTrustSource(),
    )
    assert result.outcome is DecisionOutcome.OBSERVE_ONLY
    assert result.suggestion is None
    assert result.log_entry.outcome is DecisionOutcome.OBSERVE_ONLY


async def test_level_one_proposes_and_never_executes() -> None:
    """AC-5: *"An autonomous suggestion at Autonomy Level 1 is proposed, not
    executed."* The suggestion is `proposed` and nothing else happens."""
    result = await decide(
        _request(),
        level=AutonomyLevel.SUGGESTIVE,
        policies=[],
        grants=[_open_grant()],
        trust_source=StubTrustSource(),
    )
    assert result.outcome is DecisionOutcome.PROPOSE
    assert result.suggestion is not None
    assert result.suggestion.status.value == "proposed"
    assert result.log_entry.outcome is DecisionOutcome.PROPOSE


async def test_a_deny_is_reachable_at_level_zero() -> None:
    """§4.3's table: `deny` is reachable at **every** level. Gating on the
    level first would hide the policy behind `observe_only`."""
    spy = SpyTrustSource()
    result = await decide(
        _request(),
        level=AutonomyLevel.OBSERVATION_ONLY,
        policies=[_deny_all()],
        grants=[_open_grant()],
        trust_source=spy,
    )
    assert result.outcome is DecisionOutcome.DENY
    assert result.gate == "policy"


# --- §4.2's binding order ----------------------------------------------------
async def test_a_policy_denial_is_reached_without_consulting_trust() -> None:
    """TDD §4.2, asserted on the control flow: the spy records nothing."""
    spy = SpyTrustSource()
    result = await decide(
        _request(),
        level=AutonomyLevel.SUGGESTIVE,
        policies=[_deny_all()],
        grants=[_open_grant()],
        trust_source=spy,
    )
    assert result.outcome is DecisionOutcome.DENY
    assert spy.was_consulted is False
    assert result.trust is None


async def test_a_permission_denial_is_reached_without_consulting_trust() -> None:
    spy = SpyTrustSource()
    result = await decide(
        _request(),
        level=AutonomyLevel.SUGGESTIVE,
        policies=[],
        grants=[],  # absent grant -> fail closed
        trust_source=spy,
    )
    assert result.outcome is DecisionOutcome.DENY
    assert result.gate == "permission"
    assert spy.was_consulted is False


async def test_trust_is_consulted_only_once_both_gates_pass() -> None:
    spy = SpyTrustSource()
    result = await decide(
        _request(),
        level=AutonomyLevel.SUGGESTIVE,
        policies=[],
        grants=[_open_grant()],
        trust_source=spy,
    )
    assert spy.reads == [USER]
    assert result.trust is not None


def test_a_deny_is_attributable_to_exactly_one_gate() -> None:
    """§4.2's stated purpose for fixing the order. A policy deny reports the
    policy gate even when the permission gate would also have denied."""
    report = evaluate_gates(_request(), policies=[_deny_all()], grants=[])
    assert report.denied is True
    assert report.gate == "policy"


# --- Negative control 6 ------------------------------------------------------
async def test_control_6_no_later_gate_overturns_a_policy_deny() -> None:
    """**Negative control 6**, at the pipeline level: the most permissive
    grant and a perfect trust score together cannot rescue a denied request."""
    result = await decide(
        _request(),
        level=AutonomyLevel.SUGGESTIVE,
        policies=[_deny_all()],
        grants=[_open_grant()],
        trust_source=StubTrustSource(correction_frequency=0.0, window_session_count=1000),
    )
    assert result.outcome is DecisionOutcome.DENY


# --- TDD §13: a failing policy engine fails closed ---------------------------
async def test_a_policy_evaluation_that_raises_denies(monkeypatch: pytest.MonkeyPatch) -> None:
    """TDD §13: *"A policy engine that fails open is not a policy engine."*"""

    def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("policy store unreachable")

    monkeypatch.setattr(decision_module, "evaluate_policies", _boom)
    spy = SpyTrustSource()
    result = await decide(
        _request(),
        level=AutonomyLevel.SUGGESTIVE,
        policies=[],
        grants=[_open_grant()],
        trust_source=spy,
    )
    assert result.outcome is DecisionOutcome.DENY
    assert result.gate == "policy"
    assert "policy store unreachable" in (result.reason or "")
    assert spy.was_consulted is False


# --- Negative control 1 ------------------------------------------------------
async def test_control_3_a_flag_without_a_wired_path_still_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**TDD 4F §16 control 3**, which 4F.5 retargeted from 4D's control 1.

    *(4D asserted that making `permits_execution` return `True` **at all**
    raised, because no level was allowed to execute. 4F.5 enables Level 2, so
    the guard's meaning changes from "no level may execute" to "no level may
    execute without the wired execution path" -- the same protection against
    the same mistake.)*

    **Level 2 cannot execute by flag alone.** With no `ActionDispatchPort`
    supplied, an execution-eligible level raises rather than silently acquiring
    permission, so a flag-only enablement cannot produce a passing suite."""
    monkeypatch.setattr(levels_module, "permits_execution", lambda _level: True)
    monkeypatch.setattr(decision_module, "permits_execution", lambda _level: True)

    with pytest.raises(AssertionError, match="not a flag"):
        await decide(
            _request(),
            level=AutonomyLevel.SUGGESTIVE,
            policies=[],
            grants=[_open_grant()],
            trust_source=StubTrustSource(),
        )


# --- Negative controls 1 and 11, exhaustive ----------------------------------
@pytest.mark.parametrize("level", [AutonomyLevel.OBSERVATION_ONLY, AutonomyLevel.SUGGESTIVE])
async def test_controls_1_and_11_no_configuration_reaches_execute(level: AutonomyLevel) -> None:
    """**Negative controls 1 and 11**, swept over every category, every risk
    and every Permission Matrix ceiling at both selectable levels.

    This is where a privilege escalation would have to surface: if any grant
    the user can author produced `EXECUTE`, a 4D surface would be granting more
    than `action-engine`'s own pipeline permits. The most permissive
    configuration reachable through this engine is still only a **proposal
    awaiting explicit human approval**.
    """
    source = StubTrustSource(correction_frequency=0.0, window_session_count=1000)
    allowed = {DecisionOutcome.OBSERVE_ONLY, DecisionOutcome.PROPOSE, DecisionOutcome.DENY}
    swept = 0

    for category, risk, ceiling in itertools.product(
        PermissionCategory, RiskLevel, [None, *RiskLevel]
    ):
        result = await decide(
            _request(category=category, risk=risk),
            level=level,
            policies=[],
            grants=[PermissionGrant(user_id=USER, category=category, max_risk=ceiling)],
            trust_source=source,
        )
        assert result.outcome in allowed
        assert result.outcome is not DecisionOutcome.EXECUTE
        assert result.log_entry.outcome is not DecisionOutcome.EXECUTE
        swept += 1

    assert swept == 10 * 5 * 6


# --- Negative control 12 -----------------------------------------------------
async def test_control_12_a_degraded_trust_source_is_not_reported_as_a_clean_empty() -> None:
    """**Negative control 12.** An unreachable upstream must stay
    distinguishable from an upstream that answered "nothing yet" -- both give
    `score=None`, and only the status and detail separate them."""
    degraded = SpyTrustSource(
        ConversationalTrustRead(
            status=TrustInputStatus.UNAVAILABLE, detail="digital-twin-engine unreachable"
        )
    )
    result = await decide(
        _request(),
        level=AutonomyLevel.SUGGESTIVE,
        policies=[],
        grants=[_open_grant()],
        trust_source=degraded,
    )
    assert result.trust is not None
    assert result.trust.score is None
    assert result.trust.input_status is TrustInputStatus.UNAVAILABLE
    assert result.trust.detail == "digital-twin-engine unreachable"
    # And the decision still succeeded rather than failing: TDD §13 row 1.
    assert result.outcome is DecisionOutcome.PROPOSE


# --- The decision log --------------------------------------------------------
async def test_the_log_records_every_consulted_policy_and_the_fail_closed_confidence() -> None:
    policies = [
        Policy(
            user_id=USER,
            name="ask before deploying",
            effect=PolicyEffect.REQUIRE_APPROVAL,
            match=PolicyMatch(category=PermissionCategory.DEPLOY),
        ),
        Policy(user_id=USER, name="unrelated", effect=PolicyEffect.REQUIRE_APPROVAL,
               match=PolicyMatch(category=PermissionCategory.PURCHASE)),
    ]
    result = await decide(
        _request(category=PermissionCategory.DEPLOY),
        level=AutonomyLevel.SUGGESTIVE,
        policies=policies,
        grants=[_open_grant(PermissionCategory.DEPLOY)],
        trust_source=SpyTrustSource(),  # NO_DATA -> score None
    )
    assert [(check.name, check.matched) for check in result.log_entry.policy_checks] == [
        ("ask before deploying", True),
        ("unrelated", False),
    ]
    # `confidence` is REAL NOT NULL in doc 07, so an absent score records 0.0
    # in the log -- while the score itself stays None.
    assert result.log_entry.confidence == 0.0
    assert result.trust is not None
    assert result.trust.score is None


async def test_a_denied_decision_still_gets_a_log_row_with_a_real_subject_id() -> None:
    result = await decide(
        _request(),
        level=AutonomyLevel.SUGGESTIVE,
        policies=[_deny_all()],
        grants=[],
        trust_source=SpyTrustSource(),
    )
    assert result.log_entry.outcome is DecisionOutcome.DENY
    assert result.log_entry.subject_id is not None
    assert result.log_entry.reason


async def test_a_proposal_and_its_log_row_share_one_subject_id() -> None:
    """The foreign key the `real_infra` tier exercises: the log row points at
    the suggestion, so the parent INSERT must be ordered first (TDD §9)."""
    result = await decide(
        _request(),
        level=AutonomyLevel.SUGGESTIVE,
        policies=[],
        grants=[_open_grant()],
        trust_source=StubTrustSource(),
    )
    assert result.suggestion is not None
    assert result.log_entry.subject_id == result.suggestion.id
