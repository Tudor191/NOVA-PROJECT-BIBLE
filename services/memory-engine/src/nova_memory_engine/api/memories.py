"""`/v1/memories*` routes -- thin, delegates to `domain/retrieval.py` and per-type
modules (docs/design/phase-1/01-memory-engine.md §14). Never touches SQLAlchemy or
Redis directly -- everything goes through the ports already wired onto
`request.app.state` in `main.py`.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from nova_contracts import MemorySearchResultPayload
from pydantic import BaseModel, Field

from nova_memory_engine.domain import long_term, retrieval
from nova_memory_engine.domain.models import MemoryRecord, MemoryType, PrivacyLevel
from nova_memory_engine.domain.ports import VersionConflictError

router = APIRouter(prefix="/v1/memories", tags=["memories"])


class CreateMemoryRequest(BaseModel):
    user_id: UUID
    memory_type: MemoryType
    content: str
    type_data: dict = Field(default_factory=dict)
    project_id: UUID | None = None
    confidence: float | None = None
    privacy_level: PrivacyLevel = PrivacyLevel.INTERNAL
    source: str | None = None
    source_ref: UUID | None = None
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)


class UpdateMemoryRequest(BaseModel):
    """`PATCH` body -- user correction (Part 3 "User Control"). Only set fields are
    applied; `id`, `user_id`, `memory_type`, and `lifecycle_state` are never
    editable here (lifecycle has its own explicit endpoints)."""

    content: str | None = None
    type_data: dict | None = None
    importance_score: float | None = Field(default=None, ge=0.0, le=1.0)
    privacy_level: PrivacyLevel | None = None
    project_id: UUID | None = None


class SearchResponse(BaseModel):
    results: list[MemorySearchResultPayload]
    """`MemorySearchResultPayload` (`nova-contracts`) is reused verbatim rather than
    a bespoke response DTO -- it's the same shape `memory.retrieve.request`'s reply
    uses (`main.py`), so a REST caller and a bus caller see identical results."""
    degraded: bool


@router.post("", response_model=MemoryRecord, status_code=201)
async def create_memory(body: CreateMemoryRequest, request: Request) -> MemoryRecord:
    """Mostly system/internal use -- most writes come from event subscribers, not
    this endpoint directly (docs/design/phase-1/01-memory-engine.md §14)."""
    state = request.app.state
    start = time.perf_counter()
    record = await long_term.write(
        state.memory_repository,
        user_id=body.user_id,
        memory_type=body.memory_type,
        content=body.content,
        type_data=body.type_data,
        project_id=body.project_id,
        confidence=body.confidence,
        privacy_level=body.privacy_level,
        source=body.source,
        source_ref=body.source_ref,
        importance_score=body.importance_score,
        correlation_id=uuid4(),
    )
    state.metrics.write_duration_seconds.record(time.perf_counter() - start)
    state.metrics.writes_total.add(1, {"memory_type": body.memory_type.value})
    return record


@router.get("/search", response_model=SearchResponse)
async def search_memories(
    request: Request,
    user_id: UUID,
    q: Annotated[
        str | None, Query(description="Raw text, embedded and run as semantic search.")
    ] = None,
    project_id: UUID | None = None,
    memory_type: MemoryType | None = None,
    include_relationships: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> SearchResponse:
    state = request.app.state
    start = time.perf_counter()
    result = await retrieval.retrieve(
        retrieval.RetrievalQuery(
            user_id=user_id,
            correlation_id=uuid4(),
            query_text=q,
            project_id=project_id,
            memory_type=memory_type,
            include_relationships=include_relationships,
            limit=limit,
        ),
        repository=state.memory_repository,
        vector_index=state.vector_index,
        embedding_provider=state.embedding_provider,
        event_publisher=state.bus,
    )
    state.metrics.retrieval_duration_seconds.record(time.perf_counter() - start)
    if result.degraded:
        state.metrics.retrieval_degraded_total.add(1)
    return SearchResponse(
        results=[
            MemorySearchResultPayload.model_validate(r, from_attributes=True)
            for r in result.results
        ],
        degraded=result.degraded,
    )


@router.get("/timeline", response_model=list[MemoryRecord])
async def timeline_memories(
    request: Request,
    user_id: UUID,
    project_id: UUID | None = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[MemoryRecord]:
    state = request.app.state
    return await state.memory_repository.list_by_timeline(
        user_id=user_id, project_id=project_id, start=from_, end=to, limit=limit
    )


@router.get("/{memory_id}", response_model=MemoryRecord)
async def get_memory(memory_id: UUID, user_id: UUID, request: Request) -> MemoryRecord:
    state = request.app.state
    record = await long_term.get(state.memory_repository, memory_id, user_id=user_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return record


@router.patch("/{memory_id}", response_model=MemoryRecord)
async def update_memory(
    memory_id: UUID, user_id: UUID, body: UpdateMemoryRequest, request: Request
) -> MemoryRecord:
    state = request.app.state
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        return await long_term.correct(
            state.memory_repository,
            memory_id,
            user_id=user_id,
            updates=updates,
            correlation_id=uuid4(),
        )
    except long_term.MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except VersionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/{memory_id}", response_model=MemoryRecord)
async def delete_memory(memory_id: UUID, user_id: UUID, request: Request) -> MemoryRecord:
    """Always moves to `scheduled_for_deletion` -- never an immediate hard delete
    (docs/design/phase-1/01-memory-engine.md §14)."""
    state = request.app.state
    try:
        return await long_term.schedule_deletion(
            state.memory_repository, memory_id, user_id=user_id, correlation_id=uuid4()
        )
    except long_term.MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{memory_id}/reactivate", response_model=MemoryRecord)
async def reactivate_memory(memory_id: UUID, user_id: UUID, request: Request) -> MemoryRecord:
    state = request.app.state
    try:
        return await long_term.reactivate(
            state.memory_repository, memory_id, user_id=user_id, correlation_id=uuid4()
        )
    except long_term.MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
