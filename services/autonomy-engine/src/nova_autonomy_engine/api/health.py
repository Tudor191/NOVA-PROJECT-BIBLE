"""`/internal/health` and `/internal/readiness`
(docs/architecture/11-api-architecture.md §3).

**Readiness actually probes the database.** A readiness endpoint that only
reports a flag set at startup reports a degraded service as healthy, which TDD
§16 control 12 forbids -- so this one calls `AutonomyRepository.ping()` and
reports **not ready** when it raises.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/internal", tags=["health"])


class HealthResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    ready: bool
    detail: str | None = None


@router.get("/health")
async def health() -> HealthResponse:
    """Liveness only: the process is up. It deliberately does **not** touch the
    database, so a database outage restarts nothing."""
    return HealthResponse(status="healthy")


@router.get("/readiness")
async def readiness(request: Request) -> ReadinessResponse:
    state = request.app.state
    if not getattr(state, "ready", False):
        return ReadinessResponse(ready=False, detail="lifespan has not completed startup")
    repository = getattr(state, "repository", None)
    if repository is None:
        return ReadinessResponse(ready=False, detail="no repository is configured")
    try:
        await repository.ping()
    except Exception as exc:  # noqa: BLE001 - any failure means not ready
        return ReadinessResponse(ready=False, detail=f"database unreachable: {exc!r}")
    return ReadinessResponse(ready=True)
