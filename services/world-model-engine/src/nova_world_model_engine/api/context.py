"""`/v1/world/context` -- the hot path (docs/design/phase-1/03-world-model-engine.md
§7 step 1, §14, §15's tightest budget: p95 < 20ms). Thin: reads through
`domain/context.py` directly to `ContextRepository` -- no fan-out, no Postgres
involvement on this path, matching the direct-`HGETALL` discipline §7 requires.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from nova_world_model_engine.domain import context as context_domain

router = APIRouter(prefix="/v1/world", tags=["world"])


@router.get("/context")
async def get_context(
    user_id: UUID, request: Request, scope: str | None = None
) -> dict[str, Any]:
    """`scope=None` returns the full Active Context; `scope=agent:<category>`
    returns the Agent-Awareness-filtered view (§7 step 4). A user with no
    Active Context yet (never observed) is not an error -- it returns a
    near-empty, `confidence=0.0` context so callers can proceed with reduced
    confidence (§17's documented Thinking Pipeline fallback), distinct from
    Redis itself being unreachable, which fails fast with a 503."""
    state = request.app.state
    start = time.perf_counter()
    try:
        context = await context_domain.get_context(state.context_repository, user_id)
    except Exception as exc:
        state.metrics.context_degraded_total.add(1)
        raise HTTPException(
            status_code=503, detail="Active Context store unavailable"
        ) from exc
    finally:
        state.metrics.context_request_duration_seconds.record(time.perf_counter() - start)
    state.metrics.context_requests_total.add(1)

    if context is None:
        return {"user_id": str(user_id), "confidence": 0.0}
    return context_domain.scoped_view(context, scope=scope)
