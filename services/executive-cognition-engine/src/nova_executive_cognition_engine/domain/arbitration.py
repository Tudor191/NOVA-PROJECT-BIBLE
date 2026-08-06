"""Decision arbitration (docs/design/phase-2c/00-executive-cognition-engine.md
§7) -- given one or more simultaneously-contending `ExecutiveRequest`s,
produces an `ArbitrationOutcome` for each. Resource contention only (two
requests want the same scarce budget, but their goals don't disagree);
genuine disagreement between two engines' conclusions is
`conflict_resolution.py`'s job (§10), never this module's.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from nova_executive_cognition_engine.domain.models import (
    ArbitrationOutcome,
    ArbitrationResult,
    CognitivePriorityScore,
    ExecutiveRequest,
)

__all__ = ["DEFAULT_HIGH_RISK_THRESHOLD", "DEFAULT_RESOURCE_BUDGET_CEILING", "arbitrate"]

DEFAULT_RESOURCE_BUDGET_CEILING = 1.0
"""§7 step 5, §20: a `Settings`-tunable, abstract ceiling on `resource_cost`
-- Phase 2C has no real capacity signal to consult (§5.1), so this is an
advisory assumption, not an enforced admission-control limit (that is a
named Phase 6 extension, §24, Cognitive Load Management)."""

DEFAULT_HIGH_RISK_THRESHOLD = 0.7
"""§12's `safety_overrides_speed` policy: a request at or above this `risk`
is never `PROCEED_REDUCED`."""

_BASE_RETRY_AFTER_MS = 250.0


def _tie_break_key(
    request: ExecutiveRequest, score: CognitivePriorityScore
) -> tuple[float, datetime, float, str]:
    """§7 step 4: composite score (descending, via the caller's own sort
    reversal), then `deadline` (nearer wins), then `long_term_alignment`
    (ADR-029 -- higher wins), then `correlation_id` (deterministic,
    arbitrary, stable)."""
    deadline = request.deadline or datetime.max.replace(tzinfo=UTC)
    return (
        -score.composite,
        deadline,
        -score.long_term_alignment,
        str(request.correlation_id),
    )


def arbitrate(
    contenders: list[ExecutiveRequest],
    *,
    scores: dict[UUID, CognitivePriorityScore],
    resource_budget_ceiling: float = DEFAULT_RESOURCE_BUDGET_CEILING,
    high_risk_threshold: float = DEFAULT_HIGH_RISK_THRESHOLD,
) -> list[ArbitrationResult]:
    """§7's algorithm. Every contender must already have a `CognitivePriorityScore`
    in `scores` (§6, computed by `priority.score`) -- this function only
    ranks and assigns outcomes, it never scores (ADR-028: comparing
    already-published magnitudes, never forming a new judgment)."""
    if not contenders:
        return []

    ranked = sorted(contenders, key=lambda r: _tie_break_key(r, scores[r.correlation_id]))

    results: list[ArbitrationResult] = []
    consumed_budget = 0.0
    minimum_forced_grant = resource_budget_ceiling * 0.1
    """§12 `user_goals_override_optimization`'s fallback grant when the
    budget is already fully consumed but the policy still forbids an
    outright `WAIT` -- a small, non-zero allocation, never the full
    request, since there genuinely is no remaining budget to grant more."""

    for rank, request in enumerate(ranked):
        priority_score = scores[request.correlation_id]

        if rank == 0:
            consumed_budget += request.resource_cost
            results.append(
                ArbitrationResult(
                    correlation_id=request.correlation_id,
                    outcome=ArbitrationOutcome.PROCEED,
                    priority_score=priority_score,
                )
            )
            continue

        has_active_goal = request.goal_id is not None
        """§12 `user_goals_override_optimization`: a request tied to an
        explicit, active user goal is never `WAIT`-ed behind a
        background/no-goal request, regardless of composite score."""

        remaining_budget = resource_budget_ceiling - consumed_budget
        fits_remaining_budget = remaining_budget > 0.0
        eligible_for_reduced = fits_remaining_budget or has_active_goal
        policies_applied = (
            ["user_goals_override_optimization"]
            if (has_active_goal and not fits_remaining_budget)
            else []
        )

        if not eligible_for_reduced:
            results.append(
                ArbitrationResult(
                    correlation_id=request.correlation_id,
                    outcome=ArbitrationOutcome.WAIT,
                    priority_score=priority_score,
                    retry_after_ms=_BASE_RETRY_AFTER_MS * rank,
                )
            )
            continue

        if priority_score.risk >= high_risk_threshold:
            # §12 `safety_overrides_speed`: never PROCEED_REDUCED at high risk --
            # full budget or WAIT, never a degraded allocation that could compound it.
            results.append(
                ArbitrationResult(
                    correlation_id=request.correlation_id,
                    outcome=ArbitrationOutcome.WAIT,
                    priority_score=priority_score,
                    retry_after_ms=_BASE_RETRY_AFTER_MS * rank,
                    policies_applied=[*policies_applied, "safety_overrides_speed"],
                )
            )
            continue

        reduced_budget_hint = (
            min(remaining_budget, request.resource_cost)
            if fits_remaining_budget
            else minimum_forced_grant
        )
        consumed_budget += reduced_budget_hint
        results.append(
            ArbitrationResult(
                correlation_id=request.correlation_id,
                outcome=ArbitrationOutcome.PROCEED_REDUCED,
                priority_score=priority_score,
                reduced_budget_hint=reduced_budget_hint,
                policies_applied=policies_applied,
            )
        )

    by_correlation_id = {result.correlation_id: result for result in results}
    return [by_correlation_id[request.correlation_id] for request in contenders]
