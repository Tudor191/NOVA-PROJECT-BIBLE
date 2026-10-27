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


@router.get("", response_model=list[TaskGraph])
async def list_plans(request: Request, limit: int = 50) -> list[TaskGraph]:
    """Phase 4B: the Planning panel's initial state.

    Declared **before** `/{task_graph_id}` because FastAPI matches routes in
    declaration order and `""` would otherwise never be reached -- the
    dynamic route would take `/v1/plans` and fail parsing the empty string
    as a UUID.

    `list_all` carries a disclosed gap this endpoint inherits rather than
    hides: `task_graph` has no ownership column, so there is no `user_id` to
    filter by and every graph is returned. That is out of 4B's scope to fix
    (it is a schema change), and the panel shows what the system actually
    holds rather than pretending a filter exists.

    Newest first, so a panel opening on a long history shows current work
    rather than the oldest plan the instance ever made -- ordered by the
    repository, which is the only layer that can: `TaskGraph` exposes no
    timestamp, the column lives on the row alone.
    """
    return await request.app.state.repository.list_all(limit=limit)


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
