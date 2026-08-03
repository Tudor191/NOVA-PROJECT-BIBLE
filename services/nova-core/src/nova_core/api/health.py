"""`/internal/health` and `/internal/readiness` -- every engine's standard liveness
and readiness surface (docs/architecture/11-api-architecture.md §3). Never exposed
through the public API Gateway; reachable only inside the private network (or
localhost in local-first embedded mode).
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from nova_core.domain.boot import NovaHost

router = APIRouter(prefix="/internal", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    uptime_seconds: float
    boot_phase: int | None


class ReadinessResponse(BaseModel):
    ready: bool
    boot_phase: int | None


@router.get("/health")
async def health(request: Request) -> HealthResponse:
    host: NovaHost = request.app.state.host
    phase = host.current_phase
    return HealthResponse(
        status=host.status.value,
        uptime_seconds=host.uptime_seconds,
        boot_phase=int(phase) if phase is not None else None,
    )


@router.get("/readiness")
async def readiness(request: Request) -> ReadinessResponse:
    host: NovaHost = request.app.state.host
    phase = host.current_phase
    return ReadinessResponse(
        ready=host.is_ready, boot_phase=int(phase) if phase is not None else None
    )
