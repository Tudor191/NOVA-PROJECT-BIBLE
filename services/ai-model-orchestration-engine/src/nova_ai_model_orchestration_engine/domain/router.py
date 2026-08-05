"""Bible Part 7's "Orchestration Principle" nine-step pipeline
(docs/design/phase-2a/00-ai-model-orchestration-engine.md §7), split into a pure
planning half and an impure execution half per ADR-021:

- `plan_routing` is a pure function of `(request, models, historical_success_rates)`
  -- no I/O, no randomness, no hidden state. Given the same inputs it always
  returns the same `RoutingDecision`, and every candidate's score is fully
  visible in that decision, never just the winner.
- `route_and_execute` is the impure orchestration: it calls `plan_routing` for the
  decision, then actually calls connectors, walking the fallback chain (Part 7
  "Fallback Strategy") on failure.

Complexity estimation is a structural heuristic (context size, tool count, task
type), explicitly not model-driven -- classifying a request's complexity by
calling a model would be circular, the same honesty precedent as Knowledge
Engine's `summarization.py` and World Model's `prediction.py`.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from uuid import UUID

from nova_contracts import RequestCompletedPayload, RequestFailedPayload, RequestOutcome

from nova_ai_model_orchestration_engine.domain import capability_matrix, cost_tracker
from nova_ai_model_orchestration_engine.domain.fallback import FallbackExhaustedError
from nova_ai_model_orchestration_engine.domain.models import (
    GenerateRequest,
    GenerateResult,
    Modality,
    ModelDescriptor,
    PrivacyLevel,
    RoutingDecision,
    ScoredCandidate,
    UsageRecord,
)
from nova_ai_model_orchestration_engine.domain.ports import (
    ModelConnector,
    OutboxEvent,
    UsageRepository,
)

__all__ = [
    "ExecutionOutcome",
    "embed_and_record",
    "estimate_complexity",
    "execute_and_record",
    "plan_embedding_routing",
    "plan_routing",
    "route_and_embed",
    "route_and_execute",
]

_TASK_BASE_COMPLEXITY: dict[str, float] = {
    "general_conversation": 0.2,
    "translation": 0.2,
    "creativity": 0.3,
    "programming": 0.6,
    "code_review": 0.6,
    "research": 0.6,
    "tool_usage": 0.5,
    "reasoning": 0.8,
    "planning": 0.8,
    "mathematics": 0.7,
    "long_context": 0.5,
    "vision": 0.4,
    "speech": 0.4,
}

_CONTEXT_TOKENS_AT_MAX_COMPLEXITY = 32_000
"""A request whose context is at or above this size contributes the maximum
weight to its complexity estimate -- a fixed reference point, not a learned
threshold (evidence-driven optimization would revise this once real request-size
distributions exist; nothing in Phase 2A does yet)."""

_TOOLS_AT_MAX_COMPLEXITY = 5

_APPROX_CHARS_PER_TOKEN = 4
"""This engine owns no tokenizer of its own (§0: it formats/fits already-declared
content, it doesn't source or measure it) -- `GenerateRequest.context` carries a
caller-supplied `token_estimate` for exactly this reason. `embed_and_record` has
no such caller-supplied estimate to work from (`EmbedRequestPayload.texts` is raw
strings), so it falls back to this well-known, explicitly-approximate
characters-per-token ratio rather than reporting character count as if it were a
real token count."""


def _approximate_token_count(text: str) -> int:
    return max(1, len(text) // _APPROX_CHARS_PER_TOKEN)


def estimate_complexity(request: GenerateRequest) -> float:
    """0.0-1.0. Weighted sum: 40% task type's inherent complexity, 30% context
    size relative to `_CONTEXT_TOKENS_AT_MAX_COMPLEXITY`, 30% tool count
    relative to `_TOOLS_AT_MAX_COMPLEXITY`. Pure arithmetic over the request
    alone -- no model call, no learned weights (yet -- design doc §20)."""
    task_component = _TASK_BASE_COMPLEXITY.get(request.task_type, 0.3)
    total_tokens = sum(c.token_estimate for c in request.context)
    context_component = min(total_tokens / _CONTEXT_TOKENS_AT_MAX_COMPLEXITY, 1.0)
    tools_component = min(len(request.tools) / _TOOLS_AT_MAX_COMPLEXITY, 1.0)
    return round(0.4 * task_component + 0.3 * context_component + 0.3 * tools_component, 4)


def _score(
    model: ModelDescriptor,
    *,
    dimension: capability_matrix.CapabilityDimension,
    historical_success_rate: float | None,
) -> ScoredCandidate:
    capability_score = model.capability_scores.score_for(dimension)
    # Cost/latency scores are inverted (lower cost/latency -> higher score) and
    # normalized against fixed reference points, the same "honest heuristic, not
    # a learned model" standard as complexity estimation above.
    cost_per_token = (model.cost_per_input_token or 0.0) + (model.cost_per_output_token or 0.0)
    cost_score = 1.0 / (1.0 + cost_per_token * 1000)  # local (cost=0) scores 1.0
    latency_ms = model.avg_latency_ms if model.avg_latency_ms is not None else 2000.0
    latency_score = 1.0 / (1.0 + latency_ms / 1000)
    success_component = historical_success_rate if historical_success_rate is not None else 0.5
    composite = (
        capability_score * 0.5 + cost_score * 0.15 + latency_score * 0.15 + success_component * 0.2
    )
    return ScoredCandidate(
        model_id=model.id,
        capability_score=capability_score,
        cost_score=cost_score,
        latency_score=latency_score,
        historical_success_rate=historical_success_rate,
        composite_score=round(composite, 6),
    )


def _explain(decision_fields: dict) -> str:
    """Derives a human-readable summary from already-computed structured
    fields -- never authored independently, so it can never claim something the
    structured data doesn't support (ADR-021)."""
    top = decision_fields["top_candidate"]
    reasons = [
        f"capability={top.capability_score:.2f}",
        f"cost={top.cost_score:.2f}",
        f"latency={top.latency_score:.2f}",
    ]
    if top.historical_success_rate is not None:
        reasons.append(f"historical_success={top.historical_success_rate:.2f}")
    base = (
        f"Selected model {top.model_id} (composite score {top.composite_score:.3f}) "
        f"from {decision_fields['candidate_count']} eligible candidate(s): {', '.join(reasons)}."
    )
    if decision_fields["privacy_constraint_applied"]:
        base += " Privacy classification restricted eligibility to local-safe models."
    if decision_fields["fallback_from"] is not None:
        base += f" Fell back from {decision_fields['fallback_from']} after a prior failure."
    return base


def plan_routing(
    request: GenerateRequest,
    models: list[ModelDescriptor],
    *,
    historical_success_rates: dict[UUID, float] | None = None,
    exclude: list[UUID] | None = None,
    fallback_from: UUID | None = None,
) -> RoutingDecision:
    """Pure. Ranks every eligible candidate (capability_matrix.eligible_candidates,
    excluding anything in `exclude` -- already-tried candidates in a fallback
    walk) by `_score`'s composite formula, ties broken by `model_id` ascending
    (ADR-021's stable tiebreak). Raises `FallbackExhaustedError` if nothing is
    eligible."""
    historical_success_rates = historical_success_rates or {}
    exclude = exclude or []
    dimension = capability_matrix.task_type_to_dimension(request.task_type)
    modality: Modality = "tool_calling" if request.tools else "text_generation"

    candidates_pool = capability_matrix.eligible_candidates(
        models, modality=modality, privacy_hint=request.privacy_hint
    )
    candidates_pool = [m for m in candidates_pool if m.id not in exclude]
    # Compare against modality/health eligibility alone (no privacy filter) to
    # detect whether the privacy classification itself narrowed the pool --
    # this is a diagnostic signal for RoutingDecision.privacy_constraint_applied
    # (ADR-021), not a second routing pass.
    modality_and_health_eligible = [
        m for m in models if modality in m.modalities and m.health_status != "unhealthy"
    ]
    privacy_constraint_applied = (
        len(candidates_pool) + len(exclude) < len(modality_and_health_eligible)
    )

    if not candidates_pool:
        raise FallbackExhaustedError([])

    scored = [
        _score(
            m,
            dimension=dimension,
            historical_success_rate=historical_success_rates.get(m.id),
        )
        for m in candidates_pool
    ]
    scored.sort(key=lambda c: (-c.composite_score, str(c.model_id)))

    complexity = estimate_complexity(request)
    explanation = _explain(
        {
            "top_candidate": scored[0],
            "candidate_count": len(scored),
            "privacy_constraint_applied": privacy_constraint_applied,
            "fallback_from": fallback_from,
        }
    )
    return RoutingDecision(
        candidates=scored,
        selected_model_id=scored[0].model_id,
        fallback_from=fallback_from,
        privacy_constraint_applied=privacy_constraint_applied,
        estimated_complexity=complexity,
        explanation=explanation,
    )


class ExecutionOutcome:
    __slots__ = ("result", "decision", "retry_count", "fallback_used")

    def __init__(
        self,
        *,
        result: GenerateResult,
        decision: RoutingDecision,
        retry_count: int,
        fallback_used: bool,
    ) -> None:
        self.result = result
        self.decision = decision
        self.retry_count = retry_count
        self.fallback_used = fallback_used


async def route_and_execute(
    request: GenerateRequest,
    models: list[ModelDescriptor],
    *,
    get_connector: Callable[[ModelDescriptor], ModelConnector],
    historical_success_rates: dict[UUID, float] | None = None,
    max_attempts: int = 3,
) -> ExecutionOutcome:
    """Impure: plans a route (pure), executes it, and walks Part 7's fallback
    chain -- retry, select another model -- on failure, up to `max_attempts`
    total tries. Raises `FallbackExhaustedError` if every attempt fails."""
    models_by_id = {m.id: m for m in models}
    tried: list[UUID] = []
    decision = plan_routing(request, models, historical_success_rates=historical_success_rates)
    last_error: Exception | None = None

    for attempt in range(max_attempts):
        candidate_model = models_by_id[decision.selected_model_id]
        connector = get_connector(candidate_model)
        try:
            result = await connector.generate(request)
            return ExecutionOutcome(
                result=result, decision=decision, retry_count=attempt, fallback_used=attempt > 0
            )
        except Exception as exc:  # noqa: BLE001 -- any connector failure triggers fallback
            last_error = exc
            tried.append(decision.selected_model_id)
            try:
                decision = plan_routing(
                    request,
                    models,
                    historical_success_rates=historical_success_rates,
                    exclude=tried,
                    fallback_from=tried[-1],
                )
            except FallbackExhaustedError:
                break

    raise FallbackExhaustedError(decision.candidates) from last_error


async def execute_and_record(
    request: GenerateRequest,
    models: list[ModelDescriptor],
    *,
    get_connector: Callable[[ModelDescriptor], ModelConnector],
    usage_repository: UsageRepository,
    historical_success_rates: dict[UUID, float] | None = None,
    max_attempts: int = 3,
) -> ExecutionOutcome:
    """Part 7 step 9, "Store Experience": wraps `route_and_execute`, always
    persisting exactly one `UsageRecord` (ADR-021's mandated structured
    telemetry) -- success, fallback-recovered success, or exhausted failure
    alike -- riding along with a same-transaction outbox row so
    `ai_model.request.completed`/`.failed` dispatch reliably (design doc §17).
    Re-raises `FallbackExhaustedError` after recording, so a caller's error
    handling is otherwise unchanged from calling `route_and_execute` directly."""
    models_by_id = {m.id: m for m in models}
    start = time.perf_counter()
    try:
        outcome = await route_and_execute(
            request,
            models,
            get_connector=get_connector,
            historical_success_rates=historical_success_rates,
            max_attempts=max_attempts,
        )
    except FallbackExhaustedError as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        attempted_ids = [c.model_id for c in exc.attempted]
        fallback_decision = RoutingDecision(
            candidates=exc.attempted,
            selected_model_id=attempted_ids[0] if attempted_ids else UUID(int=0),
            privacy_constraint_applied=False,
            estimated_complexity=estimate_complexity(request),
            explanation=str(exc),
        )
        record = UsageRecord(
            correlation_id=request.correlation_id,
            requesting_engine=request.requesting_engine,
            provider="unknown",
            model_id=attempted_ids[0] if attempted_ids else UUID(int=0),
            routing_decision=fallback_decision,
            estimated_complexity=fallback_decision.estimated_complexity,
            latency_ms=latency_ms,
            input_tokens=0,
            output_tokens=0,
            estimated_cost=0.0,
            retry_count=max_attempts,
            fallback_used=True,
            privacy_classification=request.privacy_hint,
            outcome="failed",
        )
        outbox = OutboxEvent(
            subject="ai_model.request.failed",
            payload=RequestFailedPayload(
                correlation_id=request.correlation_id,
                requesting_engine=request.requesting_engine,
                attempted_model_ids=attempted_ids,
                final_error=str(exc),
            ).model_dump(mode="json"),
            correlation_id=request.correlation_id,
        )
        await usage_repository.record_usage(record, outbox_event=outbox)
        raise

    model = models_by_id[outcome.decision.selected_model_id]
    latency_ms = (time.perf_counter() - start) * 1000
    cost = cost_tracker.estimate_cost(
        model,
        input_tokens=outcome.result.input_tokens,
        output_tokens=outcome.result.output_tokens,
    )
    record = UsageRecord(
        correlation_id=request.correlation_id,
        requesting_engine=request.requesting_engine,
        provider=model.provider,
        model_id=model.id,
        routing_decision=outcome.decision,
        estimated_complexity=outcome.decision.estimated_complexity,
        latency_ms=latency_ms,
        input_tokens=outcome.result.input_tokens,
        output_tokens=outcome.result.output_tokens,
        estimated_cost=cost,
        retry_count=outcome.retry_count,
        fallback_used=outcome.fallback_used,
        privacy_classification=request.privacy_hint,
        outcome="fallback" if outcome.fallback_used else "success",
    )
    outbox = OutboxEvent(
        subject="ai_model.request.completed",
        payload=RequestCompletedPayload(
            correlation_id=request.correlation_id,
            requesting_engine=request.requesting_engine,
            provider=model.provider,
            model_id=model.id,
            input_tokens=outcome.result.input_tokens,
            output_tokens=outcome.result.output_tokens,
            estimated_cost=cost,
            latency_ms=latency_ms,
            retry_count=outcome.retry_count,
            fallback_used=outcome.fallback_used,
            outcome=RequestOutcome.FALLBACK if outcome.fallback_used else RequestOutcome.SUCCESS,
        ).model_dump(mode="json"),
        correlation_id=request.correlation_id,
    )
    await usage_repository.record_usage(record, outbox_event=outbox)
    return outcome


def _embedding_score(model: ModelDescriptor) -> tuple[float, float]:
    """Ranks embedding-eligible candidates by cost then latency only --
    embedding has no Part 7 capability dimension to score against (§10: this
    engine's embedding capability wraps a single connector's embedding
    endpoint, not a modeled skill)."""
    cost_per_token = (model.cost_per_input_token or 0.0) + (model.cost_per_output_token or 0.0)
    latency_ms = model.avg_latency_ms if model.avg_latency_ms is not None else 2000.0
    return (cost_per_token, latency_ms)


def plan_embedding_routing(
    models: list[ModelDescriptor],
    *,
    privacy_hint: PrivacyLevel,
    exclude: list[UUID] | None = None,
) -> ModelDescriptor:
    """Pure. Cheapest, then lowest-latency eligible embedding candidate.
    Raises `FallbackExhaustedError` if nothing is eligible (§10, §7 -- the same
    routing/fallback machinery as generation, filtered to `embedding`-capable
    candidates)."""
    exclude = exclude or []
    candidates = capability_matrix.eligible_candidates(
        models, modality="embedding", privacy_hint=privacy_hint
    )
    candidates = [m for m in candidates if m.id not in exclude]
    if not candidates:
        raise FallbackExhaustedError([])
    candidates.sort(key=lambda m: (*_embedding_score(m), str(m.id)))
    return candidates[0]


async def route_and_embed(
    texts: list[str],
    models: list[ModelDescriptor],
    *,
    privacy_hint: PrivacyLevel,
    get_connector: Callable[[ModelDescriptor], ModelConnector],
    max_attempts: int = 3,
) -> tuple[ModelDescriptor, list[list[float]]]:
    """Impure: the embedding counterpart to `route_and_execute` -- same
    fallback-walk shape, calling `connector.embed()` instead of `.generate()`."""
    tried: list[UUID] = []
    last_error: Exception | None = None
    for _ in range(max_attempts):
        model = plan_embedding_routing(models, privacy_hint=privacy_hint, exclude=tried)
        connector = get_connector(model)
        try:
            embeddings = await connector.embed(texts)
            return model, embeddings
        except Exception as exc:  # noqa: BLE001 -- any connector failure triggers fallback
            last_error = exc
            tried.append(model.id)
    raise FallbackExhaustedError([]) from last_error


async def embed_and_record(
    texts: list[str],
    models: list[ModelDescriptor],
    *,
    privacy_hint: PrivacyLevel,
    requesting_engine: str,
    correlation_id: UUID,
    get_connector: Callable[[ModelDescriptor], ModelConnector],
    usage_repository: UsageRepository,
    max_attempts: int = 3,
) -> tuple[ModelDescriptor, list[list[float]]]:
    """The embedding counterpart to `execute_and_record` -- same
    always-record-telemetry guarantee, adapted to embedding's simpler request
    shape (no task type/tool count, so `estimated_complexity` is `0.0`: not a
    real estimate, just "not applicable" for this request kind)."""
    start = time.perf_counter()
    try:
        model, embeddings = await route_and_embed(
            texts, models, privacy_hint=privacy_hint, get_connector=get_connector,
            max_attempts=max_attempts,
        )
    except FallbackExhaustedError as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        record = UsageRecord(
            correlation_id=correlation_id,
            requesting_engine=requesting_engine,
            provider="unknown",
            model_id=UUID(int=0),
            routing_decision=RoutingDecision(
                candidates=[],
                selected_model_id=UUID(int=0),
                privacy_constraint_applied=False,
                estimated_complexity=0.0,
                explanation=str(exc),
            ),
            estimated_complexity=0.0,
            latency_ms=latency_ms,
            input_tokens=0,
            output_tokens=0,
            estimated_cost=0.0,
            retry_count=max_attempts,
            fallback_used=True,
            privacy_classification=privacy_hint,
            outcome="failed",
        )
        outbox = OutboxEvent(
            subject="ai_model.request.failed",
            payload=RequestFailedPayload(
                correlation_id=correlation_id,
                requesting_engine=requesting_engine,
                attempted_model_ids=[],
                final_error=str(exc),
            ).model_dump(mode="json"),
            correlation_id=correlation_id,
        )
        await usage_repository.record_usage(record, outbox_event=outbox)
        raise

    latency_ms = (time.perf_counter() - start) * 1000
    input_tokens = sum(_approximate_token_count(t) for t in texts)
    cost = cost_tracker.estimate_cost(model, input_tokens=input_tokens, output_tokens=0)
    record = UsageRecord(
        correlation_id=correlation_id,
        requesting_engine=requesting_engine,
        provider=model.provider,
        model_id=model.id,
        routing_decision=RoutingDecision(
            candidates=[],
            selected_model_id=model.id,
            privacy_constraint_applied=False,
            estimated_complexity=0.0,
            explanation=f"Selected {model.id} for embedding: cheapest eligible candidate.",
        ),
        estimated_complexity=0.0,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=0,
        estimated_cost=cost,
        retry_count=0,
        fallback_used=False,
        privacy_classification=privacy_hint,
        outcome="success",
    )
    outbox = OutboxEvent(
        subject="ai_model.request.completed",
        payload=RequestCompletedPayload(
            correlation_id=correlation_id,
            requesting_engine=requesting_engine,
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
        correlation_id=correlation_id,
    )
    await usage_repository.record_usage(record, outbox_event=outbox)
    return model, embeddings
