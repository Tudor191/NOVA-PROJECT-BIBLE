"""Cognitive coordination (docs/design/phase-2c/00-executive-cognition-engine.md
§3, §4) -- the top-level entry point tying together priority scoring (§6),
arbitration (§7), goal correlation (§8), and trace assembly (§18) for one
incoming `ExecutiveRequest`, arbitrated against whatever other requests the
caller supplies as currently in flight. §0.3, §0.4's honest Phase 2C scope:
a per-request pipeline, not yet a continuous background loop -- there is no
idle-time loop here, because Cognitive State Engine (§0.4, Phase 4) does not
yet exist to give one real work to do between requests.
"""

from __future__ import annotations

import time
from uuid import UUID

from nova_executive_cognition_engine.domain import arbitration, goal_correlation, priority
from nova_executive_cognition_engine.domain import trace as trace_module
from nova_executive_cognition_engine.domain.models import (
    ArbitrationOutcome,
    ArbitrationResult,
    ExecutiveDecisionTrace,
    ExecutiveDecisionType,
    ExecutiveRequest,
    Goal,
)
from nova_executive_cognition_engine.domain.ports import ExecutiveRepository, GoalsPort, OutboxEvent

__all__ = ["arbitrate_request"]


async def _score_all(
    contenders: list[ExecutiveRequest],
    *,
    goals_by_id: dict[UUID, Goal],
    repository: ExecutiveRepository,
) -> dict[UUID, priority.CognitivePriorityScore]:
    scores: dict[UUID, priority.CognitivePriorityScore] = {}
    for contender in contenders:
        goal = goals_by_id.get(contender.goal_id) if contender.goal_id is not None else None
        if goal is None and contender.goal_id is not None and contender.goal_tier is not None:
            # §5.7, §8, ADR-029: GoalsPort is a placeholder returning `[]`
            # until Planning Engine exists, so a caller-supplied `goal_tier`
            # (ExecutiveRequest.goal_tier) takes precedence over the
            # (currently always-empty) port lookup -- the same precedence
            # Reasoning Engine's own caller-supplied goals already have over
            # its GoalsPort result (that design's §7.1). This synthesizes no
            # conclusion beyond what the caller itself asserted.
            goal = Goal(
                id=contender.goal_id,
                description="",
                priority=0.0,
                goal_tier=contender.goal_tier,
            )
        siblings = (
            await repository.requests_for_goal(
                contender.goal_id, exclude_correlation_id=contender.correlation_id
            )
            if contender.goal_id is not None
            else []
        )
        alignment = goal_correlation.long_term_alignment(contender, goal, siblings)
        scores[contender.correlation_id] = priority.score(contender, long_term_alignment=alignment)
    return scores


def _outbox_event(trace: ExecutiveDecisionTrace) -> OutboxEvent:
    subject = (
        "executive.decision.completed"
        if trace.outcome
        in (
            ArbitrationOutcome.PROCEED,
            ArbitrationOutcome.PROCEED_REDUCED,
            ArbitrationOutcome.WAIT,
            ArbitrationOutcome.ESCALATED,
        )
        else "executive.decision.failed"
    )
    return OutboxEvent(
        subject=subject,
        payload={
            "executive_decision_id": str(trace.id),
            "correlation_id": str(trace.correlation_id),
            "decision_type": trace.decision_type.value,
            "contending_requests": [c.model_dump(mode="json") for c in trace.contending_requests],
            "winner_correlation_id": (
                str(trace.winner_correlation_id) if trace.winner_correlation_id else None
            ),
            "outcome": trace.outcome.value,
            "execution_duration_ms": trace.execution_duration_ms,
            "schema_version": 1,
        },
        correlation_id=trace.correlation_id,
    )


async def arbitrate_request(
    request: ExecutiveRequest,
    *,
    other_contenders: list[ExecutiveRequest],
    goals_port: GoalsPort,
    repository: ExecutiveRepository,
    user_id: UUID,
    resource_budget_ceiling: float = arbitration.DEFAULT_RESOURCE_BUDGET_CEILING,
) -> tuple[ArbitrationResult, ExecutiveDecisionTrace]:
    """§3's Executive Cycle, honestly scoped to what one served RPC call can
    do: Observe (record the request, §19), Evaluate Objectives (resolve its
    goal, §8), Determine Priorities (§6), Allocate Cognitive Resources (§7),
    persist the decision (§18), return it. "Coordinate Specialized Systems"
    is deliberately absent from this function -- this engine returns a
    decision to the caller, it never itself invokes the winner (§4)."""
    start = time.monotonic()
    await repository.record_request(request)

    all_contenders = [request, *other_contenders]
    goals = await goals_port.current_goals(user_id=user_id)
    goals_by_id = {goal.id: goal for goal in goals}

    scores = await _score_all(all_contenders, goals_by_id=goals_by_id, repository=repository)
    results = arbitration.arbitrate(
        all_contenders, scores=scores, resource_budget_ceiling=resource_budget_ceiling
    )
    results_by_id = {result.correlation_id: result for result in results}
    this_result = results_by_id[request.correlation_id]

    winner_correlation_id = next(
        (
            result.correlation_id
            for result in results
            if result.outcome is ArbitrationOutcome.PROCEED
        ),
        None,
    )
    rejected_reasons = trace_module.rejected_reasons_from_results(results)
    policies_applied = sorted({name for result in results for name in result.policies_applied})

    duration_ms = (time.monotonic() - start) * 1000
    decision_trace = trace_module.build_trace(
        correlation_id=request.correlation_id,
        decision_type=ExecutiveDecisionType.RESOURCE_ARBITRATION,
        contenders=all_contenders,
        scores=scores,
        policies_applied=policies_applied,
        outcome=this_result.outcome,
        execution_duration_ms=duration_ms,
        winner_correlation_id=winner_correlation_id,
        rejected_reasons=rejected_reasons,
    )
    finalized = await repository.finalize_decision(
        trace=decision_trace, outbox_event=_outbox_event(decision_trace)
    )
    return this_result, finalized
