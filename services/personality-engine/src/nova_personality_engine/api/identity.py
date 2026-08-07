"""`GET /v1/personality/identity` and `GET /v1/personality/identity/snapshot`
(docs/design/phase-2d/02-personality-engine.md Sec11). Both read
`app.state.core_identity`/`app.state.memory_profile`, loaded once at startup
(Sec8: a load failure has no runtime fallback -- see `main.py`).

Prefixed `/v1/personality` per the Phase 2D-A Gate Review's API-consistency
finding: every prior engine's public API follows `/v1/<domain>/...`
(`/v1/executive/...`, `/v1/reasoning/...`, `/v1/knowledge/...`); this
engine's original bare-path routes were a real, unintentional deviation,
corrected immediately per the user's own standing instruction to fix a
Gate-Review-identified inconsistency rather than carry it forward as debt."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from nova_personality_engine.domain.models import CoreIdentity, IdentitySnapshot
from nova_personality_engine.domain.style_selector import select_style

router = APIRouter(prefix="/v1/personality", tags=["identity"])


@router.get("/identity", response_model=CoreIdentity)
async def identity(request: Request) -> CoreIdentity:
    core_identity: CoreIdentity | None = request.app.state.core_identity
    if core_identity is None:
        raise HTTPException(status_code=503, detail="Core identity is not loaded.")
    return core_identity


@router.get("/identity/snapshot", response_model=IdentitySnapshot)
async def identity_snapshot(request: Request) -> IdentitySnapshot:
    """Design doc Sec13's fast-path support: a single cacheable summary
    `communication-engine` fetches periodically rather than calling
    `validate_response`/`style.select` synchronously per utterance for
    low-stakes acknowledgment content."""
    state = request.app.state
    core_identity: CoreIdentity | None = state.core_identity
    if core_identity is None:
        raise HTTPException(status_code=503, detail="Core identity is not loaded.")
    style, verbosity, technical_depth = select_style(
        situation_hint=None, channel=None, memory_profile=state.memory_profile
    )
    return IdentitySnapshot(
        traits=core_identity.traits,
        default_style=style,
        verbosity=verbosity,
        technical_depth=technical_depth,
    )
