"""`/internal/health` and `/internal/readiness` -- byte-identical across 9 of
10 engines (docs/architecture/11-api-architecture.md §3; Project Health
Review, August 2026; `docs/design/nova-service-kit/
boilerplate-extraction-proposal.md` Extraction A). Zero parameters,
deliberately: `nova-core` reads real boot-sequence state
(`request.app.state.host`) for this endpoint, a genuine semantic difference
kept explicit by keeping its own separate `api/health.py`, not by adding a
generic override mechanism here for a difference only one engine has.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    ready: bool


def make_health_router() -> APIRouter:
    router = APIRouter(prefix="/internal", tags=["health"])

    @router.get("/health")
    async def health() -> HealthResponse:
        return HealthResponse(status="healthy")

    @router.get("/readiness")
    async def readiness(request: Request) -> ReadinessResponse:
        return ReadinessResponse(ready=bool(getattr(request.app.state, "ready", False)))

    return router
