"""`/v1/models*` routes -- registry CRUD, dry-run select, out-of-cycle benchmark
trigger (docs/design/phase-2a/00-ai-model-orchestration-engine.md §14).

`/select` is registered before `/{model_id}` so FastAPI's literal-path match
wins over the `{model_id}: UUID` path converter -- otherwise `GET /v1/models/
select` would 422 trying to parse `"select"` as a UUID.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from nova_contracts import ModelRegistryChangedPayload, PrivacyLevel
from pydantic import BaseModel, Field

from nova_ai_model_orchestration_engine.domain import benchmark as benchmark_domain
from nova_ai_model_orchestration_engine.domain import router as routing
from nova_ai_model_orchestration_engine.domain.fallback import FallbackExhaustedError
from nova_ai_model_orchestration_engine.domain.models import (
    CapabilityDimension,
    CapabilityScores,
    GenerateRequest,
    Modality,
    ModelDescriptor,
    RoutingDecision,
    ToolSchema,
)
from nova_ai_model_orchestration_engine.domain.ports import OutboxEvent

router = APIRouter(prefix="/v1/models", tags=["models"])


class RegisterModelRequest(BaseModel):
    name: str
    version: str
    provider: str
    connector_type: str
    is_local: bool
    modalities: list[Modality]
    capability_scores: dict[CapabilityDimension, float] = Field(default_factory=dict)
    context_window: int
    max_output_tokens: int
    avg_latency_ms: float | None = None
    avg_quality_score: float | None = None
    hardware_requirements: dict[str, str] = Field(default_factory=dict)
    license: str | None = None
    cost_per_input_token: float | None = None
    cost_per_output_token: float | None = None
    max_privacy_tier: PrivacyLevel = PrivacyLevel.INTERNAL


class BenchmarkResponse(BaseModel):
    model_id: UUID
    avg_latency_ms: float
    avg_quality_score: float
    success_rate: float


@router.get("/select", response_model=RoutingDecision)
async def select_model(
    request: Request,
    task_type: str = "general_conversation",
    privacy_hint: PrivacyLevel = PrivacyLevel.INTERNAL,
    tool_count: int = 0,
) -> RoutingDecision:
    """Part 7's "Select Model" API: the routing decision that *would* be made,
    exposed for debugging/observability without executing anything (§14).
    `tool_count` synthesizes that many placeholder tool schemas so a caller can
    see how tool-calling requirements shift eligibility, without needing to
    supply real tool definitions for a dry run."""
    state = request.app.state
    models = await state.registry_repository.list_all()
    synthetic = GenerateRequest(
        context=[],
        tools=[
            ToolSchema(name=f"tool_{i}", description="", parameters_json_schema={})
            for i in range(tool_count)
        ],
        task_type=task_type,
        privacy_hint=privacy_hint,
        requesting_engine="dry-run",
    )
    try:
        return routing.plan_routing(synthetic, models)
    except FallbackExhaustedError as exc:
        raise HTTPException(
            status_code=404, detail="No eligible model for this request shape"
        ) from exc


@router.get("", response_model=list[ModelDescriptor])
async def list_models(
    request: Request,
    provider: str | None = None,
    modality: Modality | None = None,
    health_status: str | None = None,
) -> list[ModelDescriptor]:
    state = request.app.state
    return await state.registry_repository.list_all(
        provider=provider, modality=modality, health_status=health_status
    )


@router.post("", response_model=ModelDescriptor, status_code=201)
async def register_model(body: RegisterModelRequest, request: Request) -> ModelDescriptor:
    state = request.app.state
    model = ModelDescriptor(
        **body.model_dump(exclude={"capability_scores"}),
        capability_scores=CapabilityScores(scores=body.capability_scores),
    )
    correlation_id = uuid4()
    outbox = OutboxEvent(
        subject="ai_model.model.registered",
        payload=ModelRegistryChangedPayload(
            model_id=model.id, name=model.name, provider=model.provider
        ).model_dump(mode="json"),
        correlation_id=correlation_id,
    )
    registered = await state.registry_repository.register(model, outbox_event=outbox)
    state.metrics.models_registered_total.add(1)
    return registered


@router.get("/{model_id}", response_model=ModelDescriptor)
async def get_model(model_id: UUID, request: Request) -> ModelDescriptor:
    state = request.app.state
    model = await state.registry_repository.get(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.delete("/{model_id}", status_code=204)
async def deregister_model(model_id: UUID, request: Request) -> None:
    """A soft state (design doc §6): the row remains for historical
    `usage_record` foreign-key integrity; future routing simply never selects
    it again (its registry row is gone from `list_all`)."""
    state = request.app.state
    model = await state.registry_repository.get(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    correlation_id = uuid4()
    outbox = OutboxEvent(
        subject="ai_model.model.deregistered",
        payload=ModelRegistryChangedPayload(
            model_id=model.id, name=model.name, provider=model.provider
        ).model_dump(mode="json"),
        correlation_id=correlation_id,
    )
    await state.registry_repository.deregister(model_id, outbox_event=outbox)
    state.metrics.models_deregistered_total.add(1)


@router.post("/{model_id}/benchmark", response_model=BenchmarkResponse)
async def trigger_benchmark(model_id: UUID, request: Request) -> BenchmarkResponse:
    """Part 7 "Model Benchmarking": an out-of-cycle run of the same fixed
    evaluation set `workers/benchmark_worker.py` runs on its regular cadence
    (§14)."""
    state = request.app.state
    model = await state.registry_repository.get(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    connector = state.connector_factory.get_connector(model)
    result = await benchmark_domain.run_benchmark(connector)
    await state.registry_repository.update_benchmark(
        model_id, avg_latency_ms=result.avg_latency_ms, avg_quality_score=result.avg_quality_score
    )
    state.metrics.benchmark_runs_total.add(1)
    return BenchmarkResponse(
        model_id=model_id,
        avg_latency_ms=result.avg_latency_ms,
        avg_quality_score=result.avg_quality_score,
        success_rate=result.success_rate,
    )
