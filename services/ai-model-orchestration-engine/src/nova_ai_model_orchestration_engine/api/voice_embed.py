"""`POST /v1/models/embed-voice` (docs/design/phase-2d/03-perception-engine.md
§0.2): the same routing/fallback machinery as `/v1/models/transcribe`,
filtered to `voice_embedding`-capable candidates. Distinct from
`/v1/models/embed` (text embedding) -- never interchangeable."""

from __future__ import annotations

import time
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from nova_ai_model_orchestration_engine.domain import router as routing
from nova_ai_model_orchestration_engine.domain.fallback import FallbackExhaustedError
from nova_ai_model_orchestration_engine.domain.models import VoiceEmbedRequest

router = APIRouter(prefix="/v1/models", tags=["voice_embed"])


class VoiceEmbedResponse(BaseModel):
    embedding: list[float]
    model_id: UUID
    provider: str


@router.post("/embed-voice", response_model=VoiceEmbedResponse)
async def embed_voice(body: VoiceEmbedRequest, request: Request) -> VoiceEmbedResponse:
    state = request.app.state
    models = await state.registry_repository.list_all()
    start = time.perf_counter()
    try:
        model, result = await routing.embed_voice_and_record(
            body,
            models,
            get_connector=state.connector_factory.get_connector,
            usage_repository=state.usage_repository,
        )
    except FallbackExhaustedError as exc:
        state.metrics.requests_total.add(1, {"outcome": "failed"})
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        state.metrics.voice_embed_request_duration_seconds.record(time.perf_counter() - start)
    state.metrics.requests_total.add(1, {"outcome": "success"})
    return VoiceEmbedResponse(
        embedding=result.embedding, model_id=model.id, provider=model.provider
    )
