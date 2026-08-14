"""`reasoning.reason.request` served RPC handler (docs/design/phase-2b/
00-reasoning-engine.md §23) -- the Event Bus counterpart to `POST /v1/
reasoning/reason` (`api/reason.py`), for callers (e.g. a future Planning
Engine, §7.1) that prefer request/reply over HTTP. Both translate the same
wire payload to a domain `ReasoningRequest` and call the same
`domain.pipeline.run`, mirroring the AI Model Orchestration Engine's own
`main.py`/`api/generate.py` split rather than introducing a new shared
layer between `api/` and `events/`.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI
from nova_contracts import EventEnvelope, ReasoningReplyPayload, ReasoningRequestPayload

from nova_reasoning_engine.domain import modes, pipeline
from nova_reasoning_engine.domain.models import Constraint, Goal, ReasoningRequest
from nova_reasoning_engine.observability import record_multistep_recursion_metrics

__all__ = ["make_reason_request_handler"]


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


def make_reason_request_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> ReasoningReplyPayload:
        state = app.state
        payload = ReasoningRequestPayload.model_validate(envelope.payload)
        request = _to_domain_request(payload)

        try:
            decision, trace, chosen = await pipeline.run(
                request,
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
            return ReasoningReplyPayload(
                reasoning_process_id=UUID(int=0),
                outcome="failed",
                error=str(exc),
            )

        record_multistep_recursion_metrics(trace, state.metrics)
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

    return handle
