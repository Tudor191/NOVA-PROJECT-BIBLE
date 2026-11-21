"""`POST /v1/action/approvals/{id}/decide` -- the stopgap decision
endpoint (TDD 3D §4 point 4), served directly by this engine's own FastAPI
app since `api-gateway` does not exist yet
(`docs/design/phase-3/03-gateway-web-prerequisite.md`). Named deliberately
to mirror doc 11's reserved `/v1/autonomy/approvals/{id}/decide` naming
convention, under `action-engine`'s own namespace instead."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/v1/action", tags=["approvals"])


class PendingApprovalResponse(BaseModel):
    """One approval still waiting on a human, as the Approvals panel reads it."""

    action_id: UUID
    risk: str
    requested_at: datetime


@router.get("/approvals", response_model=list[PendingApprovalResponse])
async def list_approvals(request: Request, limit: int = 50) -> list[PendingApprovalResponse]:
    """Phase 4B -- the Approvals panel's initial state.

    Undecided only, oldest first. The panel then keeps itself current from
    `action.approval.requested` / `.decided` over `ws-gateway` rather than
    re-polling this: doc 04's "reads are pushed, never polled" applies to a
    queue whose whole purpose is to change while someone is looking at it.
    """
    approvals = await request.app.state.repository.list_pending_approvals(limit=limit)
    return [
        PendingApprovalResponse(
            action_id=approval.action_id,
            risk=approval.risk,
            requested_at=approval.requested_at,
        )
        for approval in approvals
    ]


class ApprovalDecisionRequest(BaseModel):
    approved: bool
    reason: str | None = None


class ApprovalDecisionResponse(BaseModel):
    action_id: UUID
    decision: str


@router.post("/approvals/{action_id}/decide")
async def decide_approval(
    action_id: UUID, body: ApprovalDecisionRequest, request: Request
) -> ApprovalDecisionResponse:
    repository = request.app.state.repository
    pending = await repository.find_pending_approval(action_id)
    if pending is None:
        raise HTTPException(status_code=404, detail="no pending approval for this action_id")
    if pending.decision is not None:
        raise HTTPException(status_code=409, detail="this approval has already been decided")
    decision = "approved" if body.approved else "denied"
    await repository.decide_pending_approval(
        action_id, decision=decision, decided_at=datetime.now(UTC)
    )
    return ApprovalDecisionResponse(action_id=action_id, decision=decision)
