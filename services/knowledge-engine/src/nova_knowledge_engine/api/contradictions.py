"""`/v1/knowledge/contradictions*` routes (docs/design/phase-1/
02-knowledge-engine.md §14). Resolution is always human/operator-initiated here --
`domain/contradiction.py` never auto-resolves (§1's "Must never" column)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from nova_contracts import ContradictionPayload
from pydantic import BaseModel

from nova_knowledge_engine.domain.models import Contradiction
from nova_knowledge_engine.domain.ports import OutboxEvent

router = APIRouter(prefix="/v1/knowledge/contradictions", tags=["knowledge"])


class ResolveContradictionRequest(BaseModel):
    resolution: str


@router.get("", response_model=list[Contradiction])
async def list_contradictions(
    request: Request,
    status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[Contradiction]:
    state = request.app.state
    return await state.repository.list_contradictions(status=status, limit=limit)


@router.get("/{contradiction_id}", response_model=Contradiction)
async def get_contradiction(contradiction_id: UUID, request: Request) -> Contradiction:
    state = request.app.state
    contradiction = await state.repository.get_contradiction(contradiction_id)
    if contradiction is None:
        raise HTTPException(status_code=404, detail="Contradiction not found")
    return contradiction


@router.post("/{contradiction_id}/resolve", response_model=Contradiction)
async def resolve_contradiction(
    contradiction_id: UUID, body: ResolveContradictionRequest, request: Request
) -> Contradiction:
    state = request.app.state
    existing = await state.repository.get_contradiction(contradiction_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Contradiction not found")
    outbox = OutboxEvent(
        subject="knowledge.contradiction.resolved",
        payload=ContradictionPayload(
            contradiction_id=contradiction_id,
            node_a_id=existing.node_a_id,
            node_b_id=existing.node_b_id,
            description=existing.description,
            status="resolved",
            resolution=body.resolution,
        ).model_dump(mode="json"),
        correlation_id=uuid4(),
    )
    return await state.repository.resolve_contradiction(
        contradiction_id, resolution=body.resolution, outbox_event=outbox
    )
