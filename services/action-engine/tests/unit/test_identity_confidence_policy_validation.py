"""`api.identity_confidence_policy.IdentityConfidencePolicyRequest` -- the
validator that decides what may be written to an **authorization threshold**
(Phase 4F.4, TDD 4F.4 §6.3 and §16.5).

**The unit tier, deliberately.** The integration tier asserts that bad input
produces `422` through the whole app; that proves the rule is *wired*. This
file exercises the validator as the plain Pydantic model it is -- no FastAPI,
no client, no repository, no fake -- and asserts the three properties the
status code cannot show:

1. **The accepted key set is derived from `RiskLevel`, not written out.** The
   integration tests only ever send `low` and `moderate`, so a hardcoded subset
   would pass every one of them and silently reject a tier an operator is
   entitled to configure.
2. **The rejection tells the operator the remedy.** §16.5's rule only removes
   no security capability *because* omitting a tier is how maximum strictness
   is expressed -- an error that does not say so turns a safe design into a
   confusing one.
3. **The ceiling is a strict comparison on the float itself**, checked at the
   smallest representable step above `0.75` rather than at a round `0.76`.
"""

from __future__ import annotations

import math

import pytest
from nova_action_engine.api.identity_confidence_policy import (
    MAX_CONFIGURABLE_CONFIDENCE,
    IdentityConfidencePolicyRequest,
)
from nova_contracts.events.planning import RiskLevel
from pydantic import ValidationError


def _request(mapping: dict[str, float]) -> IdentityConfidencePolicyRequest:
    return IdentityConfidencePolicyRequest(minimum_confidence_by_risk=mapping)


# --- the accepted key set comes from the enum --------------------------------


@pytest.mark.parametrize("level", list(RiskLevel))
def test_every_risk_level_value_is_a_configurable_tier(level: RiskLevel) -> None:
    """**Parametrized over `RiskLevel` itself**, so adding a sixth tier to the
    contract makes this fail until the write surface can express it -- rather
    than leaving an operator unable to configure a tier stage 3 will gate on."""
    request = _request({level.value: 0.5})

    assert request.minimum_confidence_by_risk == {level.value: 0.5}


def test_the_validator_accepts_all_five_tiers_at_once() -> None:
    """The complete map, which no other test writes: a policy that configures
    every tier is a legitimate configuration, not an over-broad one."""
    complete = {level.value: 0.5 for level in RiskLevel}

    assert _request(complete).minimum_confidence_by_risk == complete
    assert len(complete) == 5


# --- rejection messages carry the remedy -------------------------------------


def test_an_above_ceiling_rejection_names_omission_as_the_remedy() -> None:
    """**§16.5's central claim, asserted.** The rule is only capability-neutral
    because strictness is expressed by leaving a tier out; an error that stops
    at "rejected" would make the surface look strictly less capable than the
    fail-closed default it sits on top of."""
    with pytest.raises(ValidationError) as caught:
        _request({"low": 0.9})

    message = str(caught.value)
    assert "omit the tier" in message
    assert "1.0" in message
    assert str(MAX_CONFIGURABLE_CONFIDENCE) in message


def test_an_unknown_tier_rejection_lists_the_tiers_that_exist() -> None:
    """An unrecognised key is silently ignored by stage 3's lookup, so the
    operator has to be told which keys are real -- otherwise the natural next
    attempt is another guess."""
    with pytest.raises(ValidationError) as caught:
        _request({"catastrophic": 0.5})

    message = str(caught.value)
    assert "unknown risk tier" in message
    for level in RiskLevel:
        assert level.value in message


# --- the ceiling boundary, at float resolution -------------------------------


def test_the_ceiling_itself_is_accepted() -> None:
    """`0.75` is reachable by a real single signal, so it is a configuration
    that can actually admit an action."""
    assert _request({"low": MAX_CONFIGURABLE_CONFIDENCE}).minimum_confidence_by_risk == {
        "low": MAX_CONFIGURABLE_CONFIDENCE
    }


def test_the_smallest_float_above_the_ceiling_is_rejected() -> None:
    """The comparison is `>`, not `>=` with a tolerance: one ULP above the
    ceiling is already unsatisfiable, and rounding it back in would store a
    policy that can never pass."""
    one_ulp_above = math.nextafter(MAX_CONFIGURABLE_CONFIDENCE, math.inf)

    assert one_ulp_above > MAX_CONFIGURABLE_CONFIDENCE
    with pytest.raises(ValidationError):
        _request({"low": one_ulp_above})


def test_zero_is_accepted_and_is_not_confused_with_absence() -> None:
    """`0.0` is falsy, which is exactly the kind of value a truthiness check
    would drop. It is a legitimate -- maximally permissive -- threshold, and
    the gate must store it rather than treat it as "unset"."""
    assert _request({"low": 0.0}).minimum_confidence_by_risk == {"low": 0.0}


def test_an_empty_map_is_valid_at_the_model_level() -> None:
    """The model must not reject what §16.5 defines as the deliberate
    "strict everywhere" configuration; whether stage 3 then denies is proven
    against real Postgres, not here."""
    assert _request({}).minimum_confidence_by_risk == {}
