"""`GET /v1/usage` -- Part 7 "Retrieve Statistics" (docs/design/phase-2a/
00-ai-model-orchestration-engine.md §14), filterable by time range, model, and
requesting engine."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from nova_ai_model_orchestration_engine.domain.models import UsageRecord

router = APIRouter(prefix="/v1/usage", tags=["usage"])


@router.get("", response_model=list[UsageRecord])
async def list_usage(
    request: Request,
    model_id: UUID | None = None,
    requesting_engine: str | None = None,
    correlation_id: UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[UsageRecord]:
    state = request.app.state
    return await state.usage_repository.list_usage(
        model_id=model_id,
        requesting_engine=requesting_engine,
        correlation_id=correlation_id,
        since=since,
        until=until,
        limit=limit,
    )
