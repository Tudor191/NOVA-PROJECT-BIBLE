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

from collections.abc import Callable
from uuid import UUID

from nova_ai_model_orchestration_engine.domain import capability_matrix
from nova_ai_model_orchestration_engine.domain.fallback import FallbackExhaustedError
from nova_ai_model_orchestration_engine.domain.models import (
    GenerateRequest,
    GenerateResult,
    Modality,
    ModelDescriptor,
    RoutingDecision,
    ScoredCandidate,
)
from nova_ai_model_orchestration_engine.domain.ports import ModelConnector

__all__ = ["ExecutionOutcome", "estimate_complexity", "plan_routing", "route_and_execute"]

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
