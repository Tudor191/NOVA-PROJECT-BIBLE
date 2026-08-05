"""`POST /v1/models/embed` (docs/design/phase-2a/00-ai-model-orchestration-engine.md
§10, §14): the same routing/fallback machinery as generation, filtered to
`embedding`-capable candidates -- this engine *is* an embedding provider, not a
consumer of one (§10)."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from nova_contracts import PrivacyLevel
from pydantic import BaseModel

from nova_ai_model_orchestration_engine.domain import router as routing
from nova_ai_model_orchestration_engine.domain.fallback import FallbackExhaustedError

router = APIRouter(prefix="/v1/models", tags=["embed"])


class EmbedRequest(BaseModel):
    texts: list[str]
    requesting_engine: str
    privacy_hint: PrivacyLevel = PrivacyLevel.INTERNAL


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]
    model_id: UUID
    provider: str


@router.post("/embed", response_model=EmbedResponse)
async def embed(body: EmbedRequest, request: Request) -> EmbedResponse:
    state = request.app.state
    models = await state.registry_repository.list_all()
    try:
        model, embeddings = await routing.embed_and_record(
            body.texts,
            models,
            privacy_hint=body.privacy_hint,
            requesting_engine=body.requesting_engine,
            correlation_id=uuid4(),
            get_connector=state.connector_factory.get_connector,
            usage_repository=state.usage_repository,
        )
    except FallbackExhaustedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    state.metrics.requests_total.add(1, {"outcome": "success"})
    return EmbedResponse(embeddings=embeddings, model_id=model.id, provider=model.provider)
