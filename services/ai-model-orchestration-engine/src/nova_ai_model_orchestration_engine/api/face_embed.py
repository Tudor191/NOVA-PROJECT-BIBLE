"""`POST /v1/models/embed-face` (docs/design/phase-2d/03-perception-engine.md
§0.2): the same routing/fallback machinery as `/v1/models/transcribe`,
filtered to `face_embedding`-capable candidates. `image_bytes` carries one
already-detected face crop, never a full frame -- face detection itself is
the connector's own concern."""

from __future__ import annotations

import time
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from nova_ai_model_orchestration_engine.domain import router as routing
from nova_ai_model_orchestration_engine.domain.fallback import FallbackExhaustedError
from nova_ai_model_orchestration_engine.domain.models import FaceEmbedRequest

router = APIRouter(prefix="/v1/models", tags=["face_embed"])


class FaceEmbedResponse(BaseModel):
    embedding: list[float]
    model_id: UUID
    provider: str


@router.post("/embed-face", response_model=FaceEmbedResponse)
async def embed_face(body: FaceEmbedRequest, request: Request) -> FaceEmbedResponse:
    state = request.app.state
    models = await state.registry_repository.list_all()
    start = time.perf_counter()
    try:
        model, result = await routing.embed_face_and_record(
            body,
            models,
            get_connector=state.connector_factory.get_connector,
            usage_repository=state.usage_repository,
        )
    except FallbackExhaustedError as exc:
        state.metrics.requests_total.add(1, {"outcome": "failed"})
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        state.metrics.face_embed_request_duration_seconds.record(time.perf_counter() - start)
    state.metrics.requests_total.add(1, {"outcome": "success"})
    return FaceEmbedResponse(embedding=result.embedding, model_id=model.id, provider=model.provider)
