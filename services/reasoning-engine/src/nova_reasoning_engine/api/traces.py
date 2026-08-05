"""`GET /v1/reasoning/traces` and `GET /v1/reasoning/traces/{id}` (docs/
design/phase-2b/00-reasoning-engine.md §19, §23) -- the debugging,
explainability, and performance-optimization surface the structured
reasoning trace exists to support.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from nova_reasoning_engine.domain.models import ReasoningTrace

router = APIRouter(prefix="/v1/reasoning", tags=["traces"])


@router.get("/traces", response_model=list[ReasoningTrace])
async def list_traces(
    request: Request, user_id: UUID | None = None, limit: int = 100
) -> list[ReasoningTrace]:
    return await request.app.state.repository.list_traces(user_id=user_id, limit=limit)


@router.get("/traces/{trace_id}", response_model=ReasoningTrace)
async def get_trace(trace_id: UUID, request: Request) -> ReasoningTrace:
    trace = await request.app.state.repository.get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"No trace found with id {trace_id!r}")
    return trace
