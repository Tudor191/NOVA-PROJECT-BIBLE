"""`executive.arbitrate.request` and `executive.outcome.report` served RPC
handlers (docs/design/phase-2c/00-executive-cognition-engine.md §5.1-§5.2,
§7.3, §23) -- the Event Bus counterparts to `POST /v1/executive/arbitrate`
(`api/arbitrate.py`), for callers that prefer request/reply over HTTP. Both
translate the same wire payload to a domain model and call the same
`domain.coordinate.arbitrate_request`, mirroring Reasoning Engine's own
`main.py`/`api/reason.py` split rather than introducing a new shared layer
between `api/` and `events/`.
"""

from __future__ import annotations

from fastapi import FastAPI
from nova_contracts import (
    EventEnvelope,
    ExecutiveArbitrateReplyPayload,
    ExecutiveOutcomeReportPayload,
    ExecutiveOutcomeReportReplyPayload,
    ExecutiveRequestPayload,
)

from nova_executive_cognition_engine.domain.coordinate import arbitrate_request
from nova_executive_cognition_engine.domain.models import ExecutiveRequest

__all__ = ["make_arbitrate_request_handler", "make_outcome_report_handler"]


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


def make_arbitrate_request_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> ExecutiveArbitrateReplyPayload:
        state = app.state
        payload = ExecutiveRequestPayload.model_validate(envelope.payload)
        domain_request = _to_domain_request(payload)
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

    return handle


def make_outcome_report_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> ExecutiveOutcomeReportReplyPayload:
        state = app.state
        payload = ExecutiveOutcomeReportPayload.model_validate(envelope.payload)
        await state.repository.record_outcome_report(
            correlation_id=payload.correlation_id,
            outcome=payload.outcome.value,
            actual_duration_ms=payload.actual_duration_ms,
            note=payload.note,
        )
        state.contender_registry.resolve(payload.correlation_id)
        return ExecutiveOutcomeReportReplyPayload(acknowledged=True)

    return handle
