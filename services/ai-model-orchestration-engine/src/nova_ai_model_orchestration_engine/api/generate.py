"""`POST /v1/models/generate` and `POST /v1/models/generate/stream`
(docs/design/phase-2a/00-ai-model-orchestration-engine.md §14). Both accept the
same `GenerateRequest` shape and call the same routing pipeline -- streaming is
the one path that never becomes an Event Bus contract (§13), HTTP/SSE only, and
(unlike the non-streaming path) does not walk the fallback chain mid-stream:
once a model has started emitting tokens, switching models mid-response isn't a
meaningful recovery (no precedent in Part 7's fallback description covers a
partially-streamed response), so a stream failure is recorded as a failed
request rather than silently retried on a second model.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from nova_contracts import RequestCompletedPayload, RequestFailedPayload, RequestOutcome

from nova_ai_model_orchestration_engine.domain import cost_tracker
from nova_ai_model_orchestration_engine.domain import router as routing
from nova_ai_model_orchestration_engine.domain.fallback import FallbackExhaustedError
from nova_ai_model_orchestration_engine.domain.models import (
    GenerateRequest,
    GenerateResult,
    UsageRecord,
)
from nova_ai_model_orchestration_engine.domain.ports import OutboxEvent

router = APIRouter(prefix="/v1/models", tags=["generate"])


@router.post("/generate", response_model=GenerateResult)
async def generate(body: GenerateRequest, request: Request) -> GenerateResult:
    state = request.app.state
    models = await state.registry_repository.list_all()
    start = time.perf_counter()
    try:
        outcome = await routing.execute_and_record(
            body,
            models,
            get_connector=state.connector_factory.get_connector,
            usage_repository=state.usage_repository,
        )
    except FallbackExhaustedError as exc:
        state.metrics.requests_total.add(1, {"outcome": "failed"})
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        state.metrics.generate_request_duration_seconds.record(time.perf_counter() - start)

    state.metrics.requests_total.add(
        1, {"outcome": "fallback" if outcome.fallback_used else "success"}
    )
    if outcome.fallback_used:
        state.metrics.fallback_used_total.add(1)
    state.metrics.retries_total.add(outcome.retry_count)
    state.metrics.input_tokens_total.add(outcome.result.input_tokens)
    state.metrics.output_tokens_total.add(outcome.result.output_tokens)
    return outcome.result


@router.post("/generate/stream")
async def generate_stream(body: GenerateRequest, request: Request) -> StreamingResponse:
    state = request.app.state
    models = await state.registry_repository.list_all()
    try:
        decision = routing.plan_routing(body, models)
    except FallbackExhaustedError as exc:
        raise HTTPException(
            status_code=503, detail="No eligible model for this request"
        ) from exc
    model = next(m for m in models if m.id == decision.selected_model_id)
    connector = state.connector_factory.get_connector(model)

    input_tokens = sum(c.token_estimate for c in body.context)

    async def event_source() -> AsyncIterator[str]:
        start = time.perf_counter()
        text_parts: list[str] = []
        try:
            async for chunk in connector.stream(body):
                if chunk.delta_text:
                    text_parts.append(chunk.delta_text)
                yield f"data: {chunk.model_dump_json()}\n\n"
        except Exception as exc:  # noqa: BLE001 -- any stream failure ends the response as failed
            latency_ms = (time.perf_counter() - start) * 1000
            record = UsageRecord(
                correlation_id=body.correlation_id,
                requesting_engine=body.requesting_engine,
                provider=model.provider,
                model_id=model.id,
                routing_decision=decision,
                estimated_complexity=decision.estimated_complexity,
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
            state.metrics.generate_request_duration_seconds.record(latency_ms / 1000)
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
            return

        latency_ms = (time.perf_counter() - start) * 1000
        output_text = "".join(text_parts)
        output_tokens = routing.approximate_token_count(output_text) if output_text else 0
        cost = cost_tracker.estimate_cost(
            model, input_tokens=input_tokens, output_tokens=output_tokens
        )
        record = UsageRecord(
            correlation_id=body.correlation_id,
            requesting_engine=body.requesting_engine,
            provider=model.provider,
            model_id=model.id,
            routing_decision=decision,
            estimated_complexity=decision.estimated_complexity,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
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
                output_tokens=output_tokens,
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
        state.metrics.generate_request_duration_seconds.record(latency_ms / 1000)
        state.metrics.input_tokens_total.add(input_tokens)
        state.metrics.output_tokens_total.add(output_tokens)

    return StreamingResponse(event_source(), media_type="text/event-stream")
