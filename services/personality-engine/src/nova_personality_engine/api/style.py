"""`GET /v1/personality/style` (docs/design/phase-2d/02-personality-engine.md
Sec11) -- HTTP mirror of the `personality.style.select` Event-Bus RPC
(`events/handlers.py`). Prefixed `/v1/personality` per the Phase 2D-A Gate
Review's API-consistency finding -- see `identity.py`'s docstring.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from nova_personality_engine.domain.models import CommunicationStyle
from nova_personality_engine.domain.style_selector import select_style

router = APIRouter(prefix="/v1/personality", tags=["style"])


class StyleResponse(BaseModel):
    style: CommunicationStyle
    verbosity: str
    technical_depth: str


@router.get("/style", response_model=StyleResponse)
async def style(
    request: Request, situation_hint: str | None = None, channel: str | None = None
) -> StyleResponse:
    state = request.app.state
    if state.core_identity is None:
        raise HTTPException(status_code=503, detail="Core identity is not loaded.")

    started = time.perf_counter()
    selected, verbosity, technical_depth = select_style(
        situation_hint=situation_hint, channel=channel, memory_profile=state.memory_profile
    )
    state.metrics.style_select_duration_seconds.record(time.perf_counter() - started)

    return StyleResponse(style=selected, verbosity=verbosity, technical_depth=technical_depth)
