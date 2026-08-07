"""`GET /memory` (docs/design/phase-2d/02-personality-engine.md Sec11) --
the current resolved Personality Memory profile (Sec6). Read-only this
phase -- no endpoint mutates it; it changes only via
`personality.memory.update` once Phase 2D-D's `digital-twin-engine` exists
(Sec7.2, ADR-030)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from nova_personality_engine.domain.models import MemoryProfile

router = APIRouter(tags=["memory"])


@router.get("/memory", response_model=MemoryProfile)
async def memory(request: Request) -> MemoryProfile:
    profile: MemoryProfile = request.app.state.memory_profile
    return profile
