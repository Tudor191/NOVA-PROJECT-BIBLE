"""Goal management (docs/design/phase-2c/00-executive-cognition-engine.md
§8) -- this engine does not decompose, create, validate, or store goals
(§5.7, ADR-027 §4). Its goal-management responsibility is exactly two
things, both over data it already holds, sourced from the same correlation
signal (one signal serving two purposes, not two overlapping ones): grouping
contending requests that share a `goal_id`, and computing `long_term_
alignment` (§6.1, ADR-029) from how established/repeated that goal is.
"""

from __future__ import annotations

from nova_executive_cognition_engine.domain.models import ExecutiveRequest, Goal

__all__ = ["long_term_alignment"]

_ESTABLISHED_GOAL_BASE = 0.7
"""§8: a goal the caller has explicitly flagged as durable/ongoing starts
from a high base alignment score."""

_AD_HOC_GOAL_BASE = 0.2
"""§8: an untagged, first-appearance goal still gets some credit for having
*a* goal at all (versus none), but far less than an established one."""

_SIBLING_BOOST_PER_REQUEST = 0.1
_SIBLING_BOOST_CAP = 0.3
"""§8: "a request serving a goal that already has an in-flight... sibling
request inherits a small priority boost" -- capped so a goal with many
siblings doesn't saturate `long_term_alignment` to 1.0 regardless of its own
`goal_tier`."""


def long_term_alignment(
    request: ExecutiveRequest, goal: Goal | None, sibling_requests: list[ExecutiveRequest]
) -> float:
    """§6.1, §8, ADR-029. `None` when the request has no `goal_id` at all --
    no signal to align with, never guessed at (mirrors ADR-028's
    epistemic-deference discipline: this engine only computes over data it
    genuinely has)."""
    if goal is None:
        return 0.0
    base = _ESTABLISHED_GOAL_BASE if goal.goal_tier == "established" else _AD_HOC_GOAL_BASE
    sibling_boost = min(_SIBLING_BOOST_CAP, _SIBLING_BOOST_PER_REQUEST * len(sibling_requests))
    return min(1.0, base + sibling_boost)
