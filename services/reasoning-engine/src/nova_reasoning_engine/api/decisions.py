"""`GET /v1/reasoning/decisions/{id}`, `GET /v1/reasoning/decisions/{id}/
explain`, and `POST /v1/reasoning/decisions/{id}/override` (docs/design/
phase-2b/00-reasoning-engine.md §16, §18, §23).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from nova_contracts import HumanOverrideAppliedPayload

from nova_reasoning_engine.domain.models import Decision, DecisionExplanation, HumanOverrideRequest
from nova_reasoning_engine.domain.ports import OutboxEvent

router = APIRouter(prefix="/v1/reasoning/decisions", tags=["decisions"])


@router.get("/{decision_id}", response_model=Decision)
async def get_decision(decision_id: UUID, request: Request) -> Decision:
    decision = await request.app.state.repository.get_decision(decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail=f"No decision found with id {decision_id!r}")
    return decision


@router.get("/{decision_id}/explain", response_model=DecisionExplanation)
async def explain_decision(decision_id: UUID, request: Request) -> DecisionExplanation:
    """§16: "the explanation should be available on demand" -- a real
    endpoint, not a claim."""
    decision = await request.app.state.repository.get_decision(decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail=f"No decision found with id {decision_id!r}")
    return decision.explanation


@router.post("/{decision_id}/override", response_model=Decision)
async def override_decision(
    decision_id: UUID, body: HumanOverrideRequest, request: Request
) -> Decision:
    """§18: `confirm` moves `awaiting_human_override -> decided` unchanged;
    `redirect` forces the user-selected alternative to the top (recorded as
    a human override, never presented as the matrix's own choice); `reject`
    moves to `abandoned`, ending the process without a further `Decision`."""
    state = request.app.state
    existing = await state.repository.get_decision(decision_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"No decision found with id {decision_id!r}")
    if body.action == "redirect" and body.redirect_alternative_id is None:
        raise HTTPException(
            status_code=400, detail="redirect_alternative_id is required when action='redirect'"
        )

    outbox_event = OutboxEvent(
        subject="reasoning.human_override.applied",
        payload=HumanOverrideAppliedPayload(
            reasoning_process_id=body.reasoning_process_id,
            action=body.action,
            redirect_alternative_id=body.redirect_alternative_id,
            note=body.note,
        ).model_dump(mode="json"),
        correlation_id=body.reasoning_process_id,
    )
    updated = await state.repository.apply_override(
        decision_id, body, outbox_event=outbox_event
    )

    new_status = "abandoned" if body.action == "reject" else "decided"
    await state.repository.transition_process(
        updated.reasoning_process_id, status=new_status, completed_at=datetime.now(UTC)
    )
    state.metrics.human_overrides_total.add(1, {"action": body.action.value})

    return updated
