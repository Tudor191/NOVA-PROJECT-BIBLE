"""`/v1/world/objects*` routes (docs/design/phase-1/03-world-model-engine.md
§14). Object *creation* is event-driven (perception subscribers via
`events/handlers.py`), not exposed as a public write API in Phase 1 -- §14's
route list has no `POST /v1/world/objects`, matching how "most writes come
from event subscribers" for Memory/Knowledge Engine too.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request

from nova_world_model_engine.domain import temporal
from nova_world_model_engine.domain.models import ObjectStateHistoryEntry

router = APIRouter(prefix="/v1/world/objects", tags=["world"])


@router.get("/{object_id}", response_model=ObjectStateHistoryEntry)
async def get_object(object_id: str, request: Request) -> ObjectStateHistoryEntry:
    """Returns the object's most recently observed state. Postgres's
    `object_state_history` is the fast, always-consistent source for "what do
    we currently believe" -- the latest row *is* current state (§12) -- so
    this route never needs to query Neo4j, which only carries `properties` a
    caller would need for a fuller picture, not the state itself, and may
    still be catching up via the saga (§17)."""
    state = request.app.state
    history = await temporal.object_history(state.history_repository, object_id, limit=1)
    if not history:
        raise HTTPException(status_code=404, detail="World Object not found")
    return history[0]


@router.get("/{object_id}/history", response_model=list[ObjectStateHistoryEntry])
async def get_object_history(
    object_id: str,
    request: Request,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[ObjectStateHistoryEntry]:
    state = request.app.state
    return await temporal.object_history(
        state.history_repository, object_id, since=since, until=until, limit=limit
    )
