"""`POST /v1/executive/arbitrate` (docs/design/phase-2c/
00-executive-cognition-engine.md §5.1-§5.2, §7, §21, §23) -- the HTTP
counterpart to the `executive.arbitrate.request` served RPC
(`events/handlers.py`). Both translate the same wire payload to a domain
`ExecutiveRequest` and call the same `domain.coordinate.arbitrate_request`,
mirroring Reasoning Engine's own `api/reason.py`/`events/handlers.py` split
rather than introducing a new shared layer between `api/` and `events/`.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from nova_contracts import ExecutiveArbitrateReplyPayload, ExecutiveRequestPayload

from nova_executive_cognition_engine.domain.coordinate import arbitrate_request
from nova_executive_cognition_engine.domain.models import ExecutiveRequest

router = APIRouter(prefix="/v1/executive", tags=["arbitrate"])


def _to_domain_request(payload: ExecutiveRequestPayload) -> ExecutiveRequest:
    return ExecutiveRequest(
        requesting_engine=payload.requesting_engine,
        request_kind=payload.request_kind,
        user_id=payload.user_id,
        correlation_id=payload.correlation_id,
        urgency=payload.urgency,
        importance=payload.importance,
        complexity=payload.complexity,
        risk=payload.risk,
        learning_value=payload.learning_value,
        resource_cost=payload.resource_cost,
        user_impact=payload.user_impact,
        deadline=payload.deadline,
        goal_id=payload.goal_id,
        goal_tier=payload.goal_tier,
    )


@router.post("/arbitrate", response_model=ExecutiveArbitrateReplyPayload)
async def arbitrate(
    body: ExecutiveRequestPayload, request: Request
) -> ExecutiveArbitrateReplyPayload:
    state = request.app.state
    domain_request = _to_domain_request(body)
    other_contenders = state.contender_registry.contenders_for(domain_request)

    result, trace = await arbitrate_request(
        domain_request,
        other_contenders=other_contenders,
        goals_port=state.goals_port,
        repository=state.repository,
        resource_budget_ceiling=state.settings.executive_engine_resource_budget_ceiling,
    )

    state.metrics.arbitration_decisions_total.add(1, {"outcome": result.outcome.value})
    state.metrics.composite_priority_score.record(result.priority_score.composite)
    state.metrics.long_term_alignment_score.record(result.priority_score.long_term_alignment)
    state.metrics.arbitration_duration_seconds.record(trace.execution_duration_ms / 1000)
    for policy in result.policies_applied:
        state.metrics.policies_applied_total.add(1, {"policy": policy})

    return ExecutiveArbitrateReplyPayload(
        correlation_id=result.correlation_id,
        executive_decision_id=trace.id,
        outcome=result.outcome,
        retry_after_ms=result.retry_after_ms,
        reduced_budget_hint=result.reduced_budget_hint,
        priority_score=result.priority_score,
    )
