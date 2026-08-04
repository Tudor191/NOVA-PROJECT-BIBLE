"""`/v1/decisions*` routes -- docs/design/phase-1/01-memory-engine.md §14."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from nova_memory_engine.domain import decision
from nova_memory_engine.domain.models import DecisionRecord

router = APIRouter(prefix="/v1/decisions", tags=["decisions"])


@router.get("/search", response_model=list[DecisionRecord])
async def search_decisions(
    request: Request, user_id: UUID, limit: int = Query(default=50, ge=1, le=200)
) -> list[DecisionRecord]:
    return await decision.search(request.app.state.memory_repository, user_id=user_id, limit=limit)


@router.get("/{decision_id}", response_model=DecisionRecord)
async def get_decision(decision_id: UUID, request: Request) -> DecisionRecord:
    record = await decision.get(request.app.state.memory_repository, decision_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return record
