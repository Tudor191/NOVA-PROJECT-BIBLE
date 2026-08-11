"""`POST /v1/reasoning/reason` and `POST /v1/reasoning/reason/stream`
(docs/design/phase-2b/00-reasoning-engine.md §21, §23). Both accept the same
`ReasoningRequestPayload` shape and call the same `domain.pipeline.run` --
streaming is the one path that reports pipeline-stage progress in real time
(via `pipeline.run`'s `on_stage` callback) rather than token-by-token
generation, the same streaming-endpoint precedent the AI Model Orchestration
Engine's own `POST /v1/models/generate/stream` established, reused here for
"visible progress for longer reasoning sessions" (Part 8, §21).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from nova_contracts import ReasoningReplyPayload, ReasoningRequestPayload

from nova_reasoning_engine.domain import modes, pipeline
from nova_reasoning_engine.domain.models import Constraint, Goal, ReasoningRequest

router = APIRouter(prefix="/v1/reasoning", tags=["reason"])


def _to_domain_request(payload: ReasoningRequestPayload) -> ReasoningRequest:
    return ReasoningRequest(
        objective_text=payload.objective_text,
        user_id=payload.user_id,
        requesting_engine=payload.requesting_engine,
        correlation_id=payload.correlation_id,
        reasoning_mode_hint=payload.reasoning_mode_hint,
        reasoning_level_hint=payload.reasoning_level_hint,
        thinking_mode_hint=payload.thinking_mode_hint,
        goals=[
            Goal(id=g.id, description=g.description, priority=g.priority) for g in payload.goals
        ],
        constraints=[
            Constraint(kind=c.kind, description=c.description, hard=c.hard)
            for c in payload.constraints
        ],
        parent_process_id=payload.parent_process_id,
    )


@router.post("/reason", response_model=ReasoningReplyPayload)
async def reason(body: ReasoningRequestPayload, request: Request) -> ReasoningReplyPayload:
    state = request.app.state
    domain_request = _to_domain_request(body)

    try:
        decision, trace, chosen = await pipeline.run(
            domain_request,
            memory_port=state.memory_port,
            knowledge_port=state.knowledge_port,
            world_model_port=state.world_model_port,
            personal_context_port=state.personal_context_port,
            goals_port=state.goals_port,
            model_port=state.model_orchestration_port,
            repository=state.repository,
            verify_threshold=state.settings.confidence_verify_threshold,
            override_threshold=state.settings.confidence_override_threshold,
        )
    except modes.NotImplementedModeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc

    state.metrics.reasoning_requests_total.add(1, {"outcome": trace.outcome})
    state.metrics.confidence_score.record(decision.confidence_score)
    state.metrics.reasoning_request_duration_seconds.record(
        trace.execution_duration_ms / 1000, {"reasoning_mode": trace.reasoning_mode.value}
    )

    return ReasoningReplyPayload(
        reasoning_process_id=trace.reasoning_process_id,
        decision_id=decision.id,
        chosen_description=chosen.description if chosen is not None else None,
        explanation=decision.explanation.chosen_reason,
        confidence_score=decision.confidence_score,
        outcome=trace.outcome,
        trace_id=trace.id,
        is_correction=decision.is_correction,
    )


@router.post("/reason/stream")
async def reason_stream(body: ReasoningRequestPayload, request: Request) -> StreamingResponse:
    state = request.app.state
    domain_request = _to_domain_request(body)

    async def event_source() -> AsyncIterator[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()

        async def on_stage(stage: str) -> None:
            await queue.put(json.dumps({"stage": stage}))

        async def run_pipeline() -> None:
            try:
                decision, trace, chosen = await pipeline.run(
                    domain_request,
                    memory_port=state.memory_port,
                    knowledge_port=state.knowledge_port,
                    world_model_port=state.world_model_port,
                    personal_context_port=state.personal_context_port,
                    goals_port=state.goals_port,
                    model_port=state.model_orchestration_port,
                    repository=state.repository,
                    verify_threshold=state.settings.confidence_verify_threshold,
                    override_threshold=state.settings.confidence_override_threshold,
                    on_stage=on_stage,
                )
            except modes.NotImplementedModeError as exc:
                await queue.put(json.dumps({"__error__": str(exc)}))
                return
            state.metrics.reasoning_requests_total.add(1, {"outcome": trace.outcome})
            state.metrics.confidence_score.record(decision.confidence_score)
            reply = ReasoningReplyPayload(
                reasoning_process_id=trace.reasoning_process_id,
                decision_id=decision.id,
                chosen_description=chosen.description if chosen is not None else None,
                explanation=decision.explanation.chosen_reason,
                confidence_score=decision.confidence_score,
                outcome=trace.outcome,
                trace_id=trace.id,
                is_correction=decision.is_correction,
            )
            await queue.put(json.dumps({"__complete__": reply.model_dump(mode="json")}))

        task = asyncio.create_task(run_pipeline())
        try:
            while True:
                item = json.loads(await queue.get())
                if "__error__" in item:
                    yield f"event: error\ndata: {json.dumps({'error': item['__error__']})}\n\n"
                    return
                if "__complete__" in item:
                    yield f"event: complete\ndata: {json.dumps(item['__complete__'])}\n\n"
                    return
                yield f"data: {json.dumps(item)}\n\n"
        finally:
            await task

    return StreamingResponse(event_source(), media_type="text/event-stream")
