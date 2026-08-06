"""The Executive Decision Trace (docs/design/phase-2c/
00-executive-cognition-engine.md §18) -- assembles structured metadata
*about* an arbitration decision, built incrementally as arbitration runs,
persisted on every outcome. Not the domain content of what was arbitrated:
never a copy of a coordinated engine's own conclusion.
"""

from __future__ import annotations

from uuid import UUID

from nova_executive_cognition_engine.domain.models import (
    ArbitrationOutcome,
    ArbitrationResult,
    CognitivePriorityScore,
    ConflictSignals,
    ContenderSummary,
    ExecutiveDecisionTrace,
    ExecutiveDecisionType,
    ExecutiveRequest,
)

__all__ = ["build_trace", "rejected_reasons_from_results"]


def build_trace(
    *,
    correlation_id: UUID,
    decision_type: ExecutiveDecisionType,
    contenders: list[ExecutiveRequest],
    scores: dict[UUID, CognitivePriorityScore],
    policies_applied: list[str],
    outcome: ArbitrationOutcome,
    execution_duration_ms: float,
    winner_correlation_id: UUID | None = None,
    rejected_reasons: dict[UUID, str] | None = None,
    conflict_resolution_signals: ConflictSignals | None = None,
) -> ExecutiveDecisionTrace:
    """§18, in full. `winner_correlation_id`/`rejected_reasons` mirror
    Reasoning Engine's own `Decision`/`DecisionExplanation` field names and
    shape -- the direct analog for arbitration outcomes instead of
    hypothesis outcomes."""
    return ExecutiveDecisionTrace(
        correlation_id=correlation_id,
        decision_type=decision_type,
        contending_requests=[
            ContenderSummary(
                requesting_engine=request.requesting_engine,
                request_kind=request.request_kind,
                correlation_id=request.correlation_id,
            )
            for request in contenders
        ],
        priority_scores=scores,
        policies_applied=policies_applied,
        conflict_resolution_signals=conflict_resolution_signals,
        winner_correlation_id=winner_correlation_id,
        rejected_reasons=rejected_reasons or {},
        outcome=outcome,
        execution_duration_ms=execution_duration_ms,
    )


def rejected_reasons_from_results(results: list[ArbitrationResult]) -> dict[UUID, str]:
    """§16 -- "why was another task delayed?" answered per losing contender,
    citing the specific outcome it received rather than a generic message."""
    reasons: dict[UUID, str] = {}
    for result in results:
        if result.outcome is ArbitrationOutcome.PROCEED:
            continue
        if result.outcome is ArbitrationOutcome.WAIT:
            reasons[result.correlation_id] = (
                f"lower composite priority score ({result.priority_score.composite:.4f}); "
                f"retry after {result.retry_after_ms}ms"
            )
        elif result.outcome is ArbitrationOutcome.PROCEED_REDUCED:
            reasons[result.correlation_id] = (
                f"lower composite priority score ({result.priority_score.composite:.4f}); "
                f"granted a reduced budget instead of the full request"
            )
    return reasons
