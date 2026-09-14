"""Policy Engine semantics, and **negative control 6** (TDD §16): *letting a
later gate overturn a policy `deny` must fail the suite*."""

from __future__ import annotations

from uuid import uuid4

from nova_autonomy_engine.domain.models import (
    PermissionCategory,
    Policy,
    PolicyEffect,
    PolicyMatch,
)
from nova_autonomy_engine.domain.policy import evaluate_policies, policy_matches
from nova_contracts.events.planning import RiskLevel

USER = uuid4()


def _policy(
    name: str,
    effect: PolicyEffect,
    match: PolicyMatch | None = None,
    *,
    enabled: bool = True,
) -> Policy:
    return Policy(
        user_id=USER, name=name, effect=effect, match=match or PolicyMatch(), enabled=enabled
    )


def test_there_is_no_allow_effect() -> None:
    """TDD §6: an `allow` effect could only matter at Level 2+, which 4D does
    not enable, so shipping it would ship an effect with no reachable
    behaviour."""
    assert {effect.value for effect in PolicyEffect} == {"deny", "require_approval"}


def test_an_empty_policy_set_is_not_permissive() -> None:
    """TDD §6 item 4. `denied=False` means only *"no policy overrode the
    level's own behaviour"*, and the type carries no field that says more."""
    result = evaluate_policies([], category=PermissionCategory.DEPLOY, risk=RiskLevel.CRITICAL)
    assert result.denied is False
    assert result.checks == []
    assert not hasattr(result, "allowed")


def test_an_all_none_match_matches_everything() -> None:
    """A "deny all" policy is legitimate, not a misconfiguration."""
    assert (
        policy_matches(
            PolicyMatch(), category=PermissionCategory.READ, risk=RiskLevel.NEGLIGIBLE,
            capability_class=None,
        )
        is True
    )


def test_min_risk_matches_the_floor_and_everything_worse() -> None:
    match = PolicyMatch(min_risk=RiskLevel.MODERATE)
    for risk in (RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.CRITICAL):
        assert policy_matches(
            match, category=PermissionCategory.DELETE, risk=risk, capability_class=None
        )
    for risk in (RiskLevel.NEGLIGIBLE, RiskLevel.LOW):
        assert not policy_matches(
            match, category=PermissionCategory.DELETE, risk=risk, capability_class=None
        )


def test_category_and_capability_class_narrow_the_match() -> None:
    match = PolicyMatch(category=PermissionCategory.DEPLOY, capability_class="cloud")
    assert policy_matches(
        match, category=PermissionCategory.DEPLOY, risk=RiskLevel.LOW, capability_class="cloud"
    )
    assert not policy_matches(
        match, category=PermissionCategory.DELETE, risk=RiskLevel.LOW, capability_class="cloud"
    )
    assert not policy_matches(
        match, category=PermissionCategory.DEPLOY, risk=RiskLevel.LOW, capability_class="desktop"
    )


# --- Negative control 6 ------------------------------------------------------
def test_control_6_a_matching_deny_wins_over_every_later_policy() -> None:
    """**Negative control 6.** No later policy can overturn a deny -- there is
    no effect in the vocabulary that could, and the verdict is latched."""
    policies = [
        _policy("no automatic deletion", PolicyEffect.DENY),
        _policy("ask first", PolicyEffect.REQUIRE_APPROVAL),
        _policy("ask again", PolicyEffect.REQUIRE_APPROVAL),
    ]
    result = evaluate_policies(
        policies, category=PermissionCategory.DELETE, risk=RiskLevel.LOW
    )
    assert result.denied is True
    assert "no automatic deletion" in (result.reason or "")


def test_control_6_a_deny_later_in_the_list_still_wins() -> None:
    """Order of authorship must not change the verdict."""
    policies = [
        _policy("ask first", PolicyEffect.REQUIRE_APPROVAL),
        _policy("never spend money", PolicyEffect.DENY),
    ]
    result = evaluate_policies(
        policies, category=PermissionCategory.PURCHASE, risk=RiskLevel.LOW
    )
    assert result.denied is True
    assert "never spend money" in (result.reason or "")


def test_every_consulted_policy_is_recorded_not_only_the_one_that_fired() -> None:
    """TDD §6 item 3. Without the non-firing entries a reader cannot tell a
    policy that did not match from a policy that did not exist."""
    deploy = PolicyMatch(category=PermissionCategory.DEPLOY)
    delete = PolicyMatch(category=PermissionCategory.DELETE)
    policies = [
        _policy("deploy curfew", PolicyEffect.DENY, deploy),
        _policy("delete guard", PolicyEffect.DENY, delete),
    ]
    result = evaluate_policies(policies, category=PermissionCategory.DEPLOY, risk=RiskLevel.LOW)
    assert [(check.name, check.matched) for check in result.checks] == [
        ("deploy curfew", True),
        ("delete guard", False),
    ]


def test_a_deny_does_not_truncate_the_record_of_what_was_consulted() -> None:
    policies = [
        _policy("deny all", PolicyEffect.DENY),
        _policy("also consulted", PolicyEffect.REQUIRE_APPROVAL),
    ]
    result = evaluate_policies(policies, category=PermissionCategory.READ, risk=RiskLevel.LOW)
    assert len(result.checks) == 2


def test_disabled_policies_are_not_consulted_at_all() -> None:
    """Absent from `checks` rather than recorded as `matched=False`, which
    would conflate "off" with "on and did not match"."""
    policies = [_policy("switched off", PolicyEffect.DENY, enabled=False)]
    result = evaluate_policies(policies, category=PermissionCategory.DELETE, risk=RiskLevel.HIGH)
    assert result.denied is False
    assert result.checks == []


def test_require_approval_is_recorded_without_denying() -> None:
    policies = [_policy("always ask before sending emails", PolicyEffect.REQUIRE_APPROVAL)]
    result = evaluate_policies(
        policies, category=PermissionCategory.COMMUNICATE, risk=RiskLevel.LOW
    )
    assert result.denied is False
    assert result.requires_approval is True
    assert result.checks[0].matched is True


def test_evaluation_is_deterministic() -> None:
    policies = [
        _policy("a", PolicyEffect.REQUIRE_APPROVAL),
        _policy("b", PolicyEffect.DENY, PolicyMatch(min_risk=RiskLevel.HIGH)),
    ]
    first = evaluate_policies(policies, category=PermissionCategory.MODIFY, risk=RiskLevel.HIGH)
    second = evaluate_policies(policies, category=PermissionCategory.MODIFY, risk=RiskLevel.HIGH)
    assert first == second
