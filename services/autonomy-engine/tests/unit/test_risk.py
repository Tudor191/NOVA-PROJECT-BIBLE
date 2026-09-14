"""`RISK_ORDER` is the Bible's scale, complete, and ordered by tier -- not by
string."""

from __future__ import annotations

import pytest
from nova_autonomy_engine.domain.risk import RISK_ORDER, risk_at_least, risk_at_most, risk_rank
from nova_contracts.events.planning import RiskLevel


def test_risk_order_covers_the_canonical_scale_exactly() -> None:
    """A tier added to `nova_contracts`' canonical scale without being ordered
    here must fail the suite rather than silently defaulting to one end."""
    assert set(RISK_ORDER) == set(RiskLevel)
    assert len(RISK_ORDER) == len(RiskLevel)


def test_risk_order_is_bible_part_14s_order() -> None:
    """docs/bible/part-14-autonomy-engine.md:271-279, verbatim."""
    assert [level.value for level in RISK_ORDER] == [
        "negligible",
        "low",
        "moderate",
        "high",
        "critical",
    ]


def test_ordering_is_by_tier_not_lexicographic() -> None:
    """The trap this module exists to prevent: `RiskLevel` is a `StrEnum`, so
    the naive comparison gets the two most consequential tiers backwards."""
    # The naive form: "critical" sorts before "low", so the most severe tier
    # compares as *less* than a mild one.
    assert (RiskLevel.CRITICAL >= RiskLevel.LOW) is False
    assert risk_at_least(RiskLevel.CRITICAL, RiskLevel.LOW) is True
    assert risk_rank(RiskLevel.CRITICAL) > risk_rank(RiskLevel.LOW)


@pytest.mark.parametrize(
    ("risk", "floor", "expected"),
    [
        (RiskLevel.MODERATE, RiskLevel.MODERATE, True),
        (RiskLevel.HIGH, RiskLevel.MODERATE, True),
        (RiskLevel.CRITICAL, RiskLevel.MODERATE, True),
        (RiskLevel.LOW, RiskLevel.MODERATE, False),
        (RiskLevel.NEGLIGIBLE, RiskLevel.MODERATE, False),
    ],
)
def test_min_risk_is_a_floor(risk: RiskLevel, floor: RiskLevel, expected: bool) -> None:
    """A policy written at `moderate` covers moderate **and worse**. Reading it
    as equality would leave `critical` unmatched -- the dangerous direction."""
    assert risk_at_least(risk, floor) is expected


@pytest.mark.parametrize(
    ("risk", "ceiling", "expected"),
    [
        (RiskLevel.NEGLIGIBLE, RiskLevel.LOW, True),
        (RiskLevel.LOW, RiskLevel.LOW, True),
        (RiskLevel.MODERATE, RiskLevel.LOW, False),
        (RiskLevel.CRITICAL, RiskLevel.LOW, False),
    ],
)
def test_max_risk_is_a_ceiling(risk: RiskLevel, ceiling: RiskLevel, expected: bool) -> None:
    assert risk_at_most(risk, ceiling) is expected
