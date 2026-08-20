"""`GET /v1/plans/{task_graph_id}` and `POST /v1/plans/{task_graph_id}/approve`
(TDD 3B §5, `docs/architecture/11-api-architecture.md:49-50`) --
`phase-3b-planning-persistence` precursor. Exposed directly at this
engine's own FastAPI app, no `api-gateway` exists yet -- the same stopgap
precedent as `action-engine`'s `api/approvals.py` (TDD 3D §2).

Scoped honestly per TDD 3B §5: approval only records `TaskGraph.approved_at`
-- it does not gate any dispatch, since no `agent-os/kernel` (TDD 3E) exists
yet to consume it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from nova_planning_engine.domain.models import TaskGraph
from nova_planning_engine.domain.ports import TaskGraphNotFoundError

router = APIRouter(prefix="/v1/plans", tags=["plans"])


@router.get("/{task_graph_id}", response_model=TaskGraph)
async def get_plan(task_graph_id: UUID, request: Request) -> TaskGraph:
    graph = await request.app.state.repository.find_by_id(task_graph_id)
    if graph is None:
        raise HTTPException(
            status_code=404, detail=f"No task graph found with id {task_graph_id!r}"
        )
    return graph


@router.post("/{task_graph_id}/approve", response_model=TaskGraph)
async def approve_plan(task_graph_id: UUID, request: Request) -> TaskGraph:
    try:
        return await request.app.state.repository.set_approved_at(
            task_graph_id, approved_at=datetime.now(UTC)
        )
    except TaskGraphNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"No task graph found with id {task_graph_id!r}"
        ) from exc
