"""`POST /v1/models/transcribe` (docs/design/phase-2d/01-communication-engine.md
§0.3): the same routing/fallback machinery as `/v1/models/generate`, filtered to
`speech_to_text`-capable candidates. Non-streaming only -- speech-to-text
operates on one bounded utterance per call (§0.3's boundary: the caller decides
utterance boundaries via its own Transport VAD, this engine never sources audio
chunking decisions)."""

from __future__ import annotations

import time
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from nova_ai_model_orchestration_engine.domain import router as routing
from nova_ai_model_orchestration_engine.domain.fallback import FallbackExhaustedError
from nova_ai_model_orchestration_engine.domain.models import TranscribeRequest

router = APIRouter(prefix="/v1/models", tags=["transcribe"])


class TranscribeResponse(BaseModel):
    text: str
    detected_language: str | None
    structural_confidence: float
    model_id: UUID
    provider: str


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(body: TranscribeRequest, request: Request) -> TranscribeResponse:
    state = request.app.state
    models = await state.registry_repository.list_all()
    start = time.perf_counter()
    try:
        model, result = await routing.transcribe_and_record(
            body,
            models,
            get_connector=state.connector_factory.get_connector,
            usage_repository=state.usage_repository,
        )
    except FallbackExhaustedError as exc:
        state.metrics.requests_total.add(1, {"outcome": "failed"})
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        state.metrics.transcribe_request_duration_seconds.record(time.perf_counter() - start)
    state.metrics.requests_total.add(1, {"outcome": "success"})
    return TranscribeResponse(
        text=result.text,
        detected_language=result.detected_language,
        structural_confidence=result.structural_confidence,
        model_id=model.id,
        provider=model.provider,
    )
