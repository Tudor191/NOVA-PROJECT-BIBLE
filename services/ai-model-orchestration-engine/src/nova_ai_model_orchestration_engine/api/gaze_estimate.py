"""`POST /v1/models/estimate-gaze` (docs/design/phase-2d/03-perception-engine.md
§0.2): the same routing/fallback machinery as `/v1/models/transcribe`,
filtered to `gaze_estimation`-capable candidates. `image_bytes` carries one
already-detected face crop, the same boundary as `/v1/models/embed-face`."""

from __future__ import annotations

import time
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from nova_ai_model_orchestration_engine.domain import router as routing
from nova_ai_model_orchestration_engine.domain.fallback import FallbackExhaustedError
from nova_ai_model_orchestration_engine.domain.models import GazeEstimateRequest

router = APIRouter(prefix="/v1/models", tags=["gaze_estimate"])


class GazeEstimateResponse(BaseModel):
    gaze_direction: str
    structural_confidence: float
    model_id: UUID
    provider: str


@router.post("/estimate-gaze", response_model=GazeEstimateResponse)
async def estimate_gaze(body: GazeEstimateRequest, request: Request) -> GazeEstimateResponse:
    state = request.app.state
    models = await state.registry_repository.list_all()
    start = time.perf_counter()
    try:
        model, result = await routing.estimate_gaze_and_record(
            body,
            models,
            get_connector=state.connector_factory.get_connector,
            usage_repository=state.usage_repository,
        )
    except FallbackExhaustedError as exc:
        state.metrics.requests_total.add(1, {"outcome": "failed"})
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        state.metrics.gaze_estimate_request_duration_seconds.record(time.perf_counter() - start)
    state.metrics.requests_total.add(1, {"outcome": "success"})
    return GazeEstimateResponse(
        gaze_direction=result.gaze_direction,
        structural_confidence=result.structural_confidence,
        model_id=model.id,
        provider=model.provider,
    )
