"""Policy Engine -- TDD 4D §6, Bible Part 14 "POLICY ENGINE".

Bible Part 14: *"Policies override autonomous decisions... Policies remain
absolute unless modified by the user."* Four binding properties, each with a
negative control behind it:

1. **Deny wins.** The first matching enabled `deny` ends the pipeline and no
   later gate can overturn it (TDD §16 control 6). `evaluate_policies` keeps
   scanning after a deny only to finish *recording* the remaining policies --
   never to reconsider the verdict.
2. **Consulted, not merely fired, is what gets recorded.** Every enabled
   policy contributes a `PolicyCheck` with `matched` either way, because a
   log that only lists what fired cannot distinguish a policy that did not
   match from a policy that did not exist (TDD §6 item 3).
3. **An empty policy set is not permissive.** `denied=False` means *"no
   policy overrode the level's own behaviour"* -- and at Levels 0-1 the
   level's own behaviour is never execution. The type deliberately has no
   `allowed` field for a caller to misread.
4. **Deterministic.** Evaluation order is the caller's order, every branch is
   a pure comparison, and nothing here reads a clock, a random source or an
   environment variable. The same policy set and request always produce the
   same verdict and the same `checks` list.

**There is still no `allow` effect** (`PolicyEffect`, `models.py`), and no
branch here can turn a denial into a permission. 4F.5 added `AUTO_EXECUTE`,
which is a different thing: it is *affirmative* rather than *permissive*, it is
evaluated only after `denied` and `requires_approval` are both known, and it is
inert above `RiskLevel.LOW`. Doctrine item 3 is unchanged by it -- an empty
policy set still yields `auto_execute=False`, so absence is still not
permission.

Disabled policies are **not consulted at all** -- they are absent from
`checks` rather than recorded as `matched=False`, which would conflate "this
policy was off" with "this policy was on and did not match".
"""

from __future__ import annotations

from collections.abc import Sequence

from nova_contracts.events.planning import RiskLevel
from pydantic import BaseModel, Field

from nova_autonomy_engine.domain.models import (
    PermissionCategory,
    Policy,
    PolicyCheck,
    PolicyEffect,
    PolicyMatch,
)
from nova_autonomy_engine.domain.risk import risk_at_least, risk_at_most

__all__ = ["PolicyEvaluation", "evaluate_policies", "policy_matches"]


class PolicyEvaluation(BaseModel):
    """The Policy stage's verdict.

    Note what this type does **not** have: any field meaning "allowed".
    `denied is False` says only that no policy overrode the level's behaviour
    (TDD §6 item 4). `requires_approval` is recorded for the log; at Levels
    0-1 it is already the behaviour, so it changes no outcome -- it exists so
    that when 4F enables Level 2 the signal is already being carried and
    logged rather than needing to be retrofitted.
    """

    denied: bool = False
    reason: str | None = None
    requires_approval: bool = False
    auto_execute: bool = False
    """**4F.5 (D-4F5-1).** `True` only when a matching, enabled `AUTO_EXECUTE`
    policy fired **at or below `RiskLevel.LOW`**, nothing denied, and no
    `REQUIRE_APPROVAL` policy also matched.

    **It defaults to `False` and absence never changes it**, which is what
    keeps an empty policy set non-permissive: `evaluate_gates` lowers
    `GateReport.requires_approval` only when this is `True`, so "no policy"
    leaves approval required rather than granting execution.

    Note the asymmetry with `requires_approval` above: that field is a record
    for the log, while this one is load-bearing. It is a *necessary* condition
    for dispatch, never a sufficient one -- TDD 4F.5 §22.4 lists six more."""
    checks: list[PolicyCheck] = Field(default_factory=list)


def policy_matches(
    match: PolicyMatch,
    *,
    category: PermissionCategory,
    risk: RiskLevel,
    capability_class: str | None,
) -> bool:
    """A policy matches when **every** constraint it declares is satisfied.

    `None` on any axis means *"do not constrain on this axis"*, so an
    all-`None` match matches everything -- a legitimate "deny all" policy
    rather than a misconfiguration. `min_risk` is a **floor** (`risk_at_least`),
    so a policy written at `moderate` also covers `high` and `critical`;
    reading it as an equality test would leave the most severe requests
    unmatched, which is the dangerous direction of that mistake.
    """
    if match.category is not None and match.category != category:
        return False
    if match.min_risk is not None and not risk_at_least(risk, match.min_risk):
        return False
    return not (match.capability_class is not None and match.capability_class != capability_class)


def evaluate_policies(
    policies: Sequence[Policy],
    *,
    category: PermissionCategory,
    risk: RiskLevel,
    capability_class: str | None = None,
) -> PolicyEvaluation:
    """Evaluate every **enabled** policy, recording each, and deny if any
    matching policy denies.

    The loop does not `break` on the first deny: the verdict is fixed at that
    point and cannot change (there is no `allow` effect to change it), but the
    remaining enabled policies still belong in `checks` so the decision log
    shows the full set that was consulted. The *reason* names the first
    matching deny, which is the one a reader should look at.
    """
    checks: list[PolicyCheck] = []
    denied = False
    reason: str | None = None
    requires_approval = False
    auto_execute_matched = False

    for policy in policies:
        if not policy.enabled:
            continue
        matched = policy_matches(
            policy.match, category=category, risk=risk, capability_class=capability_class
        )
        checks.append(
            PolicyCheck(
                policy_id=policy.id, name=policy.name, effect=policy.effect, matched=matched
            )
        )
        if not matched:
            continue
        if policy.effect is PolicyEffect.DENY:
            if not denied:
                denied = True
                reason = (
                    f"policy {policy.name!r} denies category={category.value} "
                    f"risk={risk.value}"
                )
        elif policy.effect is PolicyEffect.REQUIRE_APPROVAL:
            requires_approval = True
        elif policy.effect is PolicyEffect.AUTO_EXECUTE:
            # Recorded as matched above either way; whether it *counts* is
            # decided once, after the loop, so ordering cannot change it.
            auto_execute_matched = True

    # 4F.5: three independent conditions narrow a matching AUTO_EXECUTE down to
    # an actual permission, and every one of them is a deliberate refusal.
    #
    #   `not denied`            -- deny wins unconditionally (item 1 of this
    #                              module's doctrine), at any policy ordering.
    #   `not requires_approval` -- a tier the operator marked for approval is
    #                              not auto-executed because a second policy
    #                              also matched. The stricter effect wins.
    #   `risk_at_most(low)`     -- the effect is inert above `low`, so Bible
    #                              Part 14's "low risk actions execute
    #                              automatically" cannot be widened by policy.
    #
    # `risk_at_most` is inclusive of `negligible`: "low risk" in the Bible's
    # sense is the tiers at or below `low`, not `low` alone. Reading it as
    # equality would leave `negligible` stricter than `low`, which is
    # incoherent rather than merely conservative.
    auto_execute = (
        auto_execute_matched
        and not denied
        and not requires_approval
        and risk_at_most(risk, RiskLevel.LOW)
    )

    return PolicyEvaluation(
        denied=denied,
        reason=reason,
        requires_approval=requires_approval,
        auto_execute=auto_execute,
        checks=checks,
    )
