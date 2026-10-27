"""Ordering helpers for the canonical `RiskLevel` scale.

`RiskLevel` is a `StrEnum`, so `>=` between two members compares *strings*
(`"critical" >= "low"` is `False`). Every risk comparison in this engine --
a policy's `min_risk` floor, a grant's `max_risk` ceiling -- needs the
Bible's *tier* ordering instead, so it goes through here rather than being
open-coded at each site where a lexicographic slip would silently invert a
security decision.

The scale itself is **not redefined**: `RISK_ORDER` lists the members of
`nova_contracts.events.planning.RiskLevel` in Bible Part 14's own order
(`docs/bible/part-14-autonomy-engine.md:271-279`), and
`tests/unit/test_risk.py` asserts the tuple covers the enum exactly -- so
adding a tier to the canonical scale without ordering it here fails the
suite rather than defaulting to the end of the list.
"""

from __future__ import annotations

from nova_contracts.events.planning import RiskLevel

__all__ = ["RISK_ORDER", "risk_at_least", "risk_at_most", "risk_rank"]

RISK_ORDER: tuple[RiskLevel, ...] = (
    RiskLevel.NEGLIGIBLE,
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.CRITICAL,
)
"""Least to most severe, Bible Part 14's order."""

_RANK: dict[RiskLevel, int] = {level: index for index, level in enumerate(RISK_ORDER)}


def risk_rank(risk: RiskLevel) -> int:
    """Position of `risk` in the Bible's scale, `0` for `negligible`."""
    return _RANK[risk]


def risk_at_least(risk: RiskLevel, floor: RiskLevel) -> bool:
    """`True` when `risk` is as severe as `floor` or worse -- a policy's
    `min_risk` is a floor, so `min_risk=moderate` matches moderate, high and
    critical."""
    return _RANK[risk] >= _RANK[floor]


def risk_at_most(risk: RiskLevel, ceiling: RiskLevel) -> bool:
    """`True` when `risk` is no worse than `ceiling` -- a grant's `max_risk`
    is a ceiling, so `max_risk=low` admits negligible and low only."""
    return _RANK[risk] <= _RANK[ceiling]
