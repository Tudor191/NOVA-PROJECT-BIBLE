"""`/v1/world/snapshot*` and `/v1/world/predictions` routes (docs/design/
phase-1/03-world-model-engine.md §14). World State Snapshots are a
coarse-grained, point-in-time version of the *entire* context (§12),
restorable wholesale rather than replayed field-by-field.

`GET /v1/world/predictions` lives here rather than in its own file: §1's file
tree lists `api/snapshots.py` but no dedicated predictions module, and both
routes are "point-in-time state" queries against the same
`WorldHistoryRepository`.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from nova_world_model_engine.domain import temporal
from nova_world_model_engine.domain.models import Prediction, Snapshot

router = APIRouter(prefix="/v1/world", tags=["world"])


class TriggerSnapshotRequest(BaseModel):
    user_id: UUID


@router.post("/snapshot", response_model=Snapshot, status_code=201)
async def trigger_snapshot(body: TriggerSnapshotRequest, request: Request) -> Snapshot:
    state = request.app.state
    context = await state.context_repository.get_context(body.user_id)
    snapshot_data = context.model_dump(mode="json") if context is not None else {}
    snapshot = Snapshot(user_id=body.user_id, snapshot_data=snapshot_data, trigger="manual")
    created = await state.history_repository.create_snapshot(snapshot)
    state.metrics.snapshots_taken_total.add(1, {"trigger": "manual"})
    return created


@router.get("/snapshots", response_model=list[Snapshot])
async def list_snapshots(
    request: Request, user_id: UUID, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> list[Snapshot]:
    state = request.app.state
    return await state.history_repository.list_snapshots(user_id=user_id, limit=limit)


@router.get("/predictions", response_model=list[Prediction])
async def list_predictions(
    request: Request, user_id: UUID, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> list[Prediction]:
    state = request.app.state
    return await temporal.recent_predictions(state.history_repository, user_id=user_id, limit=limit)
