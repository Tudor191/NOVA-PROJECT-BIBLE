"""`/internal/health` and `/internal/readiness`
(docs/architecture/11-api-architecture.md §3)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/internal", tags=["health"])


class HealthResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    ready: bool


@router.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(status="healthy")


@router.get("/readiness")
async def readiness(request: Request) -> ReadinessResponse:
    return ReadinessResponse(ready=bool(getattr(request.app.state, "ready", False)))
