"""`POST /v1/models/detect-wake-phrase` (docs/design/phase-2d/
03-perception-engine.md §0.2): the same routing/fallback machinery as
`/v1/models/transcribe`, filtered to `wake_phrase_detection`-capable
candidates. Non-streaming only -- one bounded audio window per call, the
caller (`perception-engine`) owns windowing."""

from __future__ import annotations

import time
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from nova_ai_model_orchestration_engine.domain import router as routing
from nova_ai_model_orchestration_engine.domain.fallback import FallbackExhaustedError
from nova_ai_model_orchestration_engine.domain.models import WakePhraseRequest

router = APIRouter(prefix="/v1/models", tags=["wake_phrase"])


class WakePhraseResponse(BaseModel):
    matched: bool
    structural_confidence: float
    model_id: UUID
    provider: str


@router.post("/detect-wake-phrase", response_model=WakePhraseResponse)
async def detect_wake_phrase(body: WakePhraseRequest, request: Request) -> WakePhraseResponse:
    state = request.app.state
    models = await state.registry_repository.list_all()
    start = time.perf_counter()
    try:
        model, result = await routing.detect_wake_phrase_and_record(
            body,
            models,
            get_connector=state.connector_factory.get_connector,
            usage_repository=state.usage_repository,
        )
    except FallbackExhaustedError as exc:
        state.metrics.requests_total.add(1, {"outcome": "failed"})
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        state.metrics.wake_phrase_request_duration_seconds.record(time.perf_counter() - start)
    state.metrics.requests_total.add(1, {"outcome": "success"})
    return WakePhraseResponse(
        matched=result.matched,
        structural_confidence=result.structural_confidence,
        model_id=model.id,
        provider=model.provider,
    )
