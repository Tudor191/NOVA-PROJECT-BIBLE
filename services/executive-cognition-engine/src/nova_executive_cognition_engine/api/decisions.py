"""`GET /v1/executive/decisions`, `GET /v1/executive/decisions/{id}`,
`GET /v1/executive/decisions/{id}/explain`, and `POST /v1/executive/
decisions/{id}/override` (docs/design/phase-2c/00-executive-cognition-engine.md
§13, §16, §18, §21, §23).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from nova_contracts import ExecutiveHumanOverrideAppliedPayload

from nova_executive_cognition_engine.domain.models import (
    ExecutiveDecisionTrace,
    HumanOverrideRequest,
)
from nova_executive_cognition_engine.domain.ports import OutboxEvent

router = APIRouter(prefix="/v1/executive/decisions", tags=["decisions"])


@router.get("", response_model=list[ExecutiveDecisionTrace])
async def list_decisions(
    request: Request, requesting_engine: str | None = None, limit: int = 100
) -> list[ExecutiveDecisionTrace]:
    return await request.app.state.repository.list_decisions(
        requesting_engine=requesting_engine, limit=limit
    )


@router.get("/{decision_id}", response_model=ExecutiveDecisionTrace)
async def get_decision(decision_id: UUID, request: Request) -> ExecutiveDecisionTrace:
    trace = await request.app.state.repository.get_decision(decision_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"No decision found with id {decision_id!r}")
    return trace


@router.get("/{decision_id}/explain", response_model=ExecutiveDecisionTrace)
async def explain_decision(decision_id: UUID, request: Request) -> ExecutiveDecisionTrace:
    """§16: "the explanation should be available on demand" -- a real
    endpoint, not a claim. Unlike Reasoning Engine (whose `Decision` and
    `ReasoningTrace` are separate objects, so `/explain` narrows to just
    `Decision.explanation`), this engine's `ExecutiveDecisionTrace` already
    *is* the narrow, queryable-field explanation §16's table describes
    (`priority_scores`, `rejected_reasons`, `conflict_resolution_signals`)
    -- there is no separate, wider object to narrow from, so this returns
    the same trace `GET /{decision_id}` does."""
    trace = await request.app.state.repository.get_decision(decision_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"No decision found with id {decision_id!r}")
    return trace


@router.post("/{decision_id}/override", response_model=ExecutiveDecisionTrace)
async def override_decision(
    decision_id: UUID, body: HumanOverrideRequest, request: Request
) -> ExecutiveDecisionTrace:
    """§13: `confirm` leaves the recorded decision unchanged; `redirect`
    records the user's chosen outcome in place of this engine's own (never
    presented as if the Priority Matrix itself had chosen it); `reject`
    marks the decision abandoned, recorded via `human_override` alone --
    `ArbitrationOutcome` has no separate "abandoned" state to move into
    (that is what an `executive.outcome.report` of `abandoned`, §7.3, is
    for), so `reject` changes no `ArbitrationOutcome` column, the same
    "only redirect mutates the recorded outcome" precedent Reasoning
    Engine's own override handling already established."""
    state = request.app.state
    existing = await state.repository.get_decision(decision_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"No decision found with id {decision_id!r}")
    if body.action == "redirect" and body.redirect_outcome is None:
        raise HTTPException(
            status_code=400, detail="redirect_outcome is required when action='redirect'"
        )

    outbox_event = OutboxEvent(
        subject="executive.human_override.applied",
        payload=ExecutiveHumanOverrideAppliedPayload(
            executive_decision_id=body.executive_decision_id,
            action=body.action,
            redirect_outcome=body.redirect_outcome,
            note=body.note,
        ).model_dump(mode="json"),
        correlation_id=existing.correlation_id,
    )
    updated = await state.repository.apply_override(
        decision_id, body, outbox_event=outbox_event
    )
    state.metrics.human_overrides_total.add(1, {"action": body.action.value})
    return updated
