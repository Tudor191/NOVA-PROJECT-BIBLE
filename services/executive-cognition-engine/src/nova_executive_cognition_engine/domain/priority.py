"""The Cognitive Priority Matrix (docs/design/phase-2c/
00-executive-cognition-engine.md §6, §6.1) -- Bible Part 6's seven factors
plus `long_term_alignment` (ADR-029), a fixed, structural weighted formula.
Never a model call (§0.2): this engine has no independent way to know how
urgent a request "really" is beyond what the requester declares (ADR-028's
epistemic-deference boundary), and `long_term_alignment` is this engine's
own arithmetic over data it already holds (§8), never a guess.
"""

from __future__ import annotations

from dataclasses import dataclass

from nova_executive_cognition_engine.domain.models import CognitivePriorityScore, ExecutiveRequest

__all__ = ["PriorityWeights", "score"]


@dataclass(frozen=True)
class PriorityWeights:
    """§6's composite formula weights -- a `Settings` value in production
    (never hardcoded into the scoring function itself), the identical
    discipline the Decision Matrix (Reasoning Engine §15) already
    established. Defaults sum to 1.0 so `composite` stays in `[0.0, 1.0]`
    whenever every factor does. `long_term_alignment`'s weight is
    deliberately modest by default (ADR-029 Decision §2): its primary
    designed effect is breaking ties (§7), not outranking a genuinely more
    urgent or important request."""

    urgency: float = 0.20
    importance: float = 0.20
    risk: float = 0.15
    learning_value: float = 0.10
    user_impact: float = 0.15
    long_term_alignment: float = 0.05
    complexity: float = 0.10
    resource_cost: float = 0.05


DEFAULT_WEIGHTS = PriorityWeights()


def score(
    request: ExecutiveRequest,
    *,
    long_term_alignment: float,
    weights: PriorityWeights = DEFAULT_WEIGHTS,
) -> CognitivePriorityScore:
    """§6's composite formula. `complexity` and `resource_cost` are inverted
    (`1 - x`) before weighting: higher complexity or resource cost, all else
    equal, is a *cost* to pay, not a reason to go first (§6's own recorded
    reasoning) -- a cheap, quick, high-value request can win over an
    expensive, slow one of similar importance."""
    composite = (
        weights.urgency * request.urgency
        + weights.importance * request.importance
        + weights.risk * request.risk
        + weights.learning_value * request.learning_value
        + weights.user_impact * request.user_impact
        + weights.long_term_alignment * long_term_alignment
        + weights.complexity * (1.0 - request.complexity)
        + weights.resource_cost * (1.0 - request.resource_cost)
    )
    return CognitivePriorityScore(
        urgency=request.urgency,
        importance=request.importance,
        complexity=request.complexity,
        risk=request.risk,
        learning_value=request.learning_value,
        resource_cost=request.resource_cost,
        user_impact=request.user_impact,
        long_term_alignment=long_term_alignment,
        composite=round(composite, 6),
    )
