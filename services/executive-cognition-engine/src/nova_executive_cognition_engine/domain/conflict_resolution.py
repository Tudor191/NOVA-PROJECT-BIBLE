"""Conflict detection and resolution (docs/design/phase-2c/
00-executive-cognition-engine.md §10) -- genuine disagreement between two
engines' *conclusions*, never resource contention (that is `arbitration.py`'s
job, §7). Every step below compares a magnitude a specialized engine has
already published; none of them ever reads, interprets, or judges the
substantive content of either side's conclusion, per ADR-028.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from nova_executive_cognition_engine.domain.models import ConflictSignals, ExecutivePolicy

__all__ = ["ConflictSide", "resolve_conflict"]


@dataclass(frozen=True)
class ConflictSide:
    """One side of a genuine conflict -- only already-published magnitudes,
    never the domain content behind them (§10, ADR-028)."""

    correlation_id: UUID
    evidence_count: int = 0
    confidence_score: float | None = None
    risk: float | None = None
    user_objective_match: bool = False
    historical_success_rate: float | None = None


def resolve_conflict(
    side_a: ConflictSide, side_b: ConflictSide, *, policies: list[ExecutivePolicy]
) -> tuple[UUID | None, ConflictSignals]:
    """§10's five-signal procedure, applied in order. Returns
    `(winner_correlation_id, signals)` -- `winner_correlation_id` is `None`
    when all five signals are inconclusive, meaning the conflict is
    `ESCALATED` (§7, §13) rather than resolved by this engine's own
    judgment. A tie after all five signals is not evidence either side is
    wrong -- it is the point at which this engine's own competence to
    arbitrate ends (ADR-028)."""
    signals = ConflictSignals()

    if side_a.evidence_count != side_b.evidence_count:
        winner = side_a if side_a.evidence_count > side_b.evidence_count else side_b
        signals.evidence_comparison = (
            f"{winner.correlation_id} cited more evidence "
            f"({side_a.evidence_count} vs {side_b.evidence_count})"
        )
        return winner.correlation_id, signals
    signals.evidence_comparison = "tied"

    if (
        side_a.confidence_score is not None
        and side_b.confidence_score is not None
        and side_a.confidence_score != side_b.confidence_score
    ):
        winner = side_a if side_a.confidence_score > side_b.confidence_score else side_b
        signals.confidence_comparison = (
            f"{winner.correlation_id} scored higher confidence "
            f"({side_a.confidence_score} vs {side_b.confidence_score})"
        )
        return winner.correlation_id, signals
    signals.confidence_comparison = "tied or unavailable"

    safety_policy_applies = any(
        p.name == "safety_overrides_speed" and p.applies_to in ("conflict_resolution", "both")
        for p in policies
    )
    if (
        safety_policy_applies
        and side_a.risk is not None
        and side_b.risk is not None
        and side_a.risk != side_b.risk
    ):
        winner = side_a if side_a.risk < side_b.risk else side_b
        signals.policy_applied = "safety_overrides_speed"
        return winner.correlation_id, signals

    if side_a.user_objective_match != side_b.user_objective_match:
        winner = side_a if side_a.user_objective_match else side_b
        signals.user_objective_signal = (
            f"{winner.correlation_id} matches the declared user objective"
        )
        return winner.correlation_id, signals
    signals.user_objective_signal = "tied"

    if (
        side_a.historical_success_rate is not None
        and side_b.historical_success_rate is not None
        and side_a.historical_success_rate != side_b.historical_success_rate
    ):
        winner = (
            side_a if side_a.historical_success_rate > side_b.historical_success_rate else side_b
        )
        signals.historical_outcome_signal = (
            f"{winner.correlation_id} has a higher historical success rate for this kind of "
            f"request ({side_a.historical_success_rate} vs {side_b.historical_success_rate})"
        )
        return winner.correlation_id, signals
    signals.historical_outcome_signal = "tied or unavailable"

    return None, signals
