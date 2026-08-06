"""`POST /v1/models/synthesize` and `POST /v1/models/synthesize/stream`
(docs/design/phase-2d/01-communication-engine.md §0.3). Mirrors
`api/generate.py`'s exact split: the non-streaming endpoint is what
`communication-engine` actually calls (via the `ai_model.synthesize.request`
Event-Bus RPC, per ADR-020/ADR-004 -- `EventBus.request()` returns a single
`EventEnvelope`, never a stream); `/synthesize/stream` is HTTP/SSE-only, for a
direct external caller, and -- like `/generate/stream` -- does not walk the
fallback chain mid-stream, for the same reason: a failure after synthesis has
already started emitting audio isn't a meaningful recovery point.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from nova_contracts import RequestCompletedPayload, RequestFailedPayload, RequestOutcome
from pydantic import BaseModel, ConfigDict

from nova_ai_model_orchestration_engine.domain import cost_tracker
from nova_ai_model_orchestration_engine.domain import router as routing
from nova_ai_model_orchestration_engine.domain.fallback import FallbackExhaustedError
from nova_ai_model_orchestration_engine.domain.models import (
    SynthesizeRequest,
    UsageRecord,
)
from nova_ai_model_orchestration_engine.domain.ports import OutboxEvent

router = APIRouter(prefix="/v1/models", tags=["synthesize"])


class SynthesizeResponse(BaseModel):
    model_config = ConfigDict(ser_json_bytes="base64", val_json_bytes="base64")

    audio_bytes: bytes
    audio_format: str
    structural_confidence: float
    model_id: UUID
    provider: str


@router.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize(body: SynthesizeRequest, request: Request) -> SynthesizeResponse:
    state = request.app.state
    models = await state.registry_repository.list_all()
    start = time.perf_counter()
    try:
        model, result = await routing.synthesize_and_record(
            body,
            models,
            get_connector=state.connector_factory.get_connector,
            usage_repository=state.usage_repository,
        )
    except FallbackExhaustedError as exc:
        state.metrics.requests_total.add(1, {"outcome": "failed"})
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        state.metrics.synthesize_request_duration_seconds.record(time.perf_counter() - start)
    state.metrics.requests_total.add(1, {"outcome": "success"})
    return SynthesizeResponse(
        audio_bytes=result.audio_bytes,
        audio_format=result.audio_format,
        structural_confidence=result.structural_confidence,
        model_id=model.id,
        provider=model.provider,
    )


@router.post("/synthesize/stream")
async def synthesize_stream(body: SynthesizeRequest, request: Request) -> StreamingResponse:
    state = request.app.state
    models = await state.registry_repository.list_all()
    try:
        decision = routing.plan_synthesize_routing(models, privacy_hint=body.privacy_hint)
    except FallbackExhaustedError as exc:
        raise HTTPException(
            status_code=503, detail="No eligible model for this request"
        ) from exc
    model = next(m for m in models if m.id == decision.selected_model_id)
    connector = state.connector_factory.get_connector(model)

    input_tokens = routing.approximate_token_count(body.text)

    async def event_source() -> AsyncIterator[str]:
        start = time.perf_counter()
        audio_parts: list[bytes] = []
        try:
            async for chunk in connector.synthesize_stream(body):
                if chunk.delta_audio_bytes:
                    audio_parts.append(chunk.delta_audio_bytes)
                yield f"data: {chunk.model_dump_json()}\n\n"
        except Exception as exc:  # noqa: BLE001 -- any stream failure ends the response as failed
            latency_ms = (time.perf_counter() - start) * 1000
            record = UsageRecord(
                correlation_id=body.correlation_id,
                requesting_engine=body.requesting_engine,
                provider=model.provider,
                model_id=model.id,
                routing_decision=decision,
                estimated_complexity=0.0,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=0,
                estimated_cost=0.0,
                retry_count=0,
                fallback_used=False,
                privacy_classification=body.privacy_hint,
                outcome="failed",
            )
            outbox = OutboxEvent(
                subject="ai_model.request.failed",
                payload=RequestFailedPayload(
                    correlation_id=body.correlation_id,
                    requesting_engine=body.requesting_engine,
                    attempted_model_ids=[model.id],
                    final_error=str(exc),
                ).model_dump(mode="json"),
                correlation_id=body.correlation_id,
            )
            await state.usage_repository.record_usage(record, outbox_event=outbox)
            state.metrics.requests_total.add(1, {"outcome": "failed"})
            state.metrics.synthesize_request_duration_seconds.record(latency_ms / 1000)
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
            return

        latency_ms = (time.perf_counter() - start) * 1000
        cost = cost_tracker.estimate_cost(model, input_tokens=input_tokens, output_tokens=0)
        record = UsageRecord(
            correlation_id=body.correlation_id,
            requesting_engine=body.requesting_engine,
            provider=model.provider,
            model_id=model.id,
            routing_decision=decision,
            estimated_complexity=0.0,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=0,
            estimated_cost=cost,
            retry_count=0,
            fallback_used=False,
            privacy_classification=body.privacy_hint,
            outcome="success",
        )
        outbox = OutboxEvent(
            subject="ai_model.request.completed",
            payload=RequestCompletedPayload(
                correlation_id=body.correlation_id,
                requesting_engine=body.requesting_engine,
                provider=model.provider,
                model_id=model.id,
                input_tokens=input_tokens,
                output_tokens=0,
                estimated_cost=cost,
                latency_ms=latency_ms,
                retry_count=0,
                fallback_used=False,
                outcome=RequestOutcome.SUCCESS,
            ).model_dump(mode="json"),
            correlation_id=body.correlation_id,
        )
        await state.usage_repository.record_usage(record, outbox_event=outbox)
        state.metrics.requests_total.add(1, {"outcome": "success"})
        state.metrics.synthesize_request_duration_seconds.record(latency_ms / 1000)

    return StreamingResponse(event_source(), media_type="text/event-stream")
