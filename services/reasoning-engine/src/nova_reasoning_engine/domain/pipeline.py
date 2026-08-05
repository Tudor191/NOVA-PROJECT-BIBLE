"""The Cognitive Pipeline (docs/design/phase-2b/00-reasoning-engine.md §2, §4)
-- Bible Part 8's fourteen-step pipeline, implemented literally. This is the
engine's single entry point: every reasoning mode (§6) is a *strategy*
`run()` selects and configures via `ModeConfig`, not a separate pipeline.

On "Execute": per §4, this pipeline's "Execute" step means finalizing and
returning the `Decision`, never literal action-taking (Action Engine/NAOS's
job). "Review results"/"Learn" are out of a synchronous call's scope (§4,
§25) -- `trace.py` persists the full record so a future outcome-reporting
mechanism can act on it once one exists.
"""

from __future__ import annotations

import time
from uuid import UUID

from nova_contracts import PrivacyLevel

from nova_reasoning_engine.domain import (
    alternative_generation,
    constraint_evaluator,
    context_assembly,
    decision_matrix,
    evidence_collection,
    failure_recovery,
    goal_evaluator,
    hypothesis_generation,
    modes,
)
from nova_reasoning_engine.domain import confidence as confidence_module
from nova_reasoning_engine.domain import explanation as explanation_module
from nova_reasoning_engine.domain import trace as trace_module
from nova_reasoning_engine.domain.models import (
    Alternative,
    ContextBundle,
    Decision,
    Evidence,
    HypothesisGenerationRequest,
    ReasoningMode,
    ReasoningProcess,
    ReasoningRequest,
    ReasoningTrace,
)
from nova_reasoning_engine.domain.ports import (
    GoalsPort,
    KnowledgePort,
    MemoryPort,
    ModelOrchestrationPort,
    PersonalContextPort,
    ReasoningRepository,
    WorldModelPort,
)

__all__ = [
    "DEFAULT_OVERRIDE_THRESHOLD",
    "DEFAULT_VERIFY_THRESHOLD",
    "run",
]

DEFAULT_VERIFY_THRESHOLD = 0.6
"""§10: at or above this composite confidence, the pipeline proceeds
automatically. A tunable constant, not routed through `pydantic-settings`
inside `domain/` -- the same "Settings value, never hardcoded into the
scoring function itself" intent as the Decision Matrix's own weights,
applied here as a caller-overridable default instead."""

DEFAULT_OVERRIDE_THRESHOLD = 0.35
"""§10, §18: below this composite confidence, the pipeline stops short of
`decided` and requests Human Override rather than proceeding."""


async def _resolve_reactive(
    request: ReasoningRequest, context: ContextBundle, process: ReasoningProcess
) -> tuple[Decision, list[Alternative], list[Evidence], dict[UUID, str]]:
    """Reactive mode (§6, table row 1): no hypothesis generation, no model
    call -- a direct answer drawn from whatever context was already
    retrieved. `alternatives_considered` stays empty, per the mode's own
    Expected Outputs column."""
    if context.knowledge:
        source, ref = "knowledge", context.knowledge[0].name
    elif context.memories:
        source, ref = "memory", context.memories[0].summary
    else:
        source, ref = "none", "no relevant information was found"

    alternative = Alternative(
        hypothesis_id=process.id,
        description=ref,
        constraint_status="eligible",
    )
    explanation = explanation_module.DecisionExplanation(
        chosen_reason=f"Answered directly from {source} ({ref!r}); Reactive mode performs no "
        "hypothesis generation or decision matrix scoring.",
        remaining_uncertainty="None assessed -- Reactive mode skips confidence estimation's full "
        "formula (§10) in favor of a fixed high-confidence default.",
    )
    decision = Decision(
        reasoning_process_id=process.id,
        selected_alternative_id=alternative.id,
        explanation=explanation,
        confidence_score=0.9 if source != "none" else 0.1,
    )
    return decision, [alternative], [], {}


def _self_evaluation_gap_penalty(
    *, evidence_count: int, alternative_count: int, alternatives_below_minimum: bool
) -> float:
    """A lightweight, bounded structural critique pass (Self-evaluation mode,
    §6), triggered automatically for medium-confidence decisions (§10) rather
    than a full recursive re-invocation of this pipeline -- Bible Part 8's
    "Self Questioning" applied as a real, if intentionally narrow, gap check.
    A richer self-critique pass is a natural future refinement (§25), not
    invented here beyond what a real signal supports."""
    penalty = 0.0
    if evidence_count == 0:
        penalty += 0.05
    if alternative_count < 2:
        penalty += 0.05
    if alternatives_below_minimum:
        penalty += 0.05
    return penalty


async def run(
    request: ReasoningRequest,
    *,
    memory_port: MemoryPort,
    knowledge_port: KnowledgePort,
    world_model_port: WorldModelPort,
    personal_context_port: PersonalContextPort,
    goals_port: GoalsPort,
    model_port: ModelOrchestrationPort,
    repository: ReasoningRepository,
    privacy_hint: PrivacyLevel = PrivacyLevel.INTERNAL,
    verify_threshold: float = DEFAULT_VERIFY_THRESHOLD,
    override_threshold: float = DEFAULT_OVERRIDE_THRESHOLD,
) -> tuple[Decision, ReasoningTrace]:
    """Runs the full fourteen-step cognitive pipeline for one `ReasoningRequest`
    and returns its `Decision` plus `ReasoningTrace` (§4, §19). Raises
    `modes.NotImplementedModeError` for `ReasoningMode.COLLABORATIVE` (§6,
    §25) -- the caller (`api/reason.py`, task #66) translates this into a
    clear "not yet available" response."""
    start = time.monotonic()

    # Step: Understand intent.
    mode, level = modes.resolve_mode_and_level(
        reasoning_mode_hint=request.reasoning_mode_hint,
        reasoning_level_hint=request.reasoning_level_hint,
        goals=request.goals,
        constraints=request.constraints,
    )
    config = modes.config_for(mode)  # raises NotImplementedModeError for Collaborative

    process = ReasoningProcess(
        correlation_id=request.correlation_id,
        requesting_engine=request.requesting_engine,
        user_id=request.user_id,
        parent_process_id=request.parent_process_id,
        objective_text=request.objective_text,
        reasoning_mode=mode,
        reasoning_level=level,
        status="context_assembling",
    )
    await repository.create_process(process)

    # Steps: Load memories, Load World Model, Retrieve knowledge.
    context_degraded = False
    try:
        context = await context_assembly.assemble_context(
            user_id=request.user_id,
            objective_text=request.objective_text,
            memory_port=memory_port,
            knowledge_port=knowledge_port,
            world_model_port=world_model_port,
            personal_context_port=personal_context_port,
            goals_port=goals_port,
            caller_goals=request.goals,
            constraints=request.constraints,
        )
    except Exception:  # noqa: BLE001 -- any upstream port failure degrades, never crashes
        # §17: a context-assembly failure recommends "restart" (retried by a caller, not
        # looped here) and moves the lifecycle to `degraded` (§5) rather than aborting --
        # the pipeline still attempts a reduced-confidence decision from whatever the
        # remaining steps can produce.
        context_degraded = True
        context = ContextBundle(goals=request.goals, constraints=request.constraints)
        await repository.transition_process(process.id, status="degraded")

    if mode is ReasoningMode.REACTIVE:
        decision, alternatives, all_evidence, rejected_reasons = await _resolve_reactive(
            request, context, process
        )
        confidence = confidence_module.estimate_confidence(
            evidence=[],
            memories=context.memories,
            knowledge=context.knowledge,
            alternatives=alternatives,
            degraded_steps=1 if context_degraded else 0,
            total_steps=1,
        )
        confidence = confidence.model_copy(update={"composite": decision.confidence_score})
        outcome = "degraded" if context_degraded else "decided"
        await repository.transition_process(
            process.id, status="degraded" if context_degraded else "decided"
        )
        result_trace = trace_module.build_trace(
            process=process,
            context=context,
            confidence=confidence,
            execution_duration_ms=(time.monotonic() - start) * 1000,
            model_used=None,
            alternatives=alternatives,
            alternatives_rejected=rejected_reasons,
            final_decision_explanation=decision.explanation.chosen_reason,
            outcome=outcome,  # type: ignore[arg-type]
        )
        await repository.finalize(process=process, decision=decision, trace=result_trace)
        return decision, result_trace

    await repository.transition_process(process.id, status="hypotheses_generating")

    # Step: Generate hypotheses.
    try:
        hypotheses, model_used = await hypothesis_generation.generate_hypotheses(
            HypothesisGenerationRequest(
                objective=request.objective_text,
                context=context,
                minimum_hypotheses=config.minimum_hypotheses,
                thinking_mode_hint=request.thinking_mode_hint,
            ),
            reasoning_process_id=process.id,
            model_port=model_port,
            requesting_engine=request.requesting_engine,
            correlation_id=request.correlation_id,
            privacy_hint=privacy_hint,
        )
    except hypothesis_generation.HypothesisGenerationError as exc:
        return await _fail(
            repository=repository,
            process=process,
            context=context,
            stage="hypotheses_generating",
            reason=str(exc),
            start=start,
        )

    # Step: Evaluate alternatives (verification + generation).
    verified_hypotheses, evidence = evidence_collection.collect_evidence(hypotheses, context)
    await repository.transition_process(process.id, status="alternatives_evaluating")

    alternatives, all_hypotheses, all_evidence, below_minimum = (
        await alternative_generation.generate_alternatives(
            verified_hypotheses,
            evidence,
            context,
            reasoning_process_id=process.id,
            objective=request.objective_text,
            minimum=config.minimum_hypotheses,
            model_port=model_port,
            requesting_engine=request.requesting_engine,
            correlation_id=request.correlation_id,
            thinking_mode_hint=request.thinking_mode_hint,
            privacy_hint=privacy_hint,
        )
    )

    await repository.record_hypotheses(all_hypotheses)
    await repository.record_evidence(all_evidence)

    if not alternatives:
        return await _fail(
            repository=repository,
            process=process,
            context=context,
            stage="alternatives_evaluating",
            reason="no supported hypotheses survived evidence collection",
            start=start,
        )

    # Step: Estimate risks / Constraint Evaluation -- hard gate before scoring.
    gated_alternatives, violations = constraint_evaluator.apply_hard_constraints(
        alternatives, context.constraints
    )
    eligible = [a for a in gated_alternatives if a.constraint_status == "eligible"]

    if not eligible:
        return await _fail(
            repository=repository,
            process=process,
            context=context,
            stage="decision_scoring",
            reason="no feasible alternative: every alternative violated a hard constraint",
            start=start,
        )

    # Step: Choose strategy -- Decision Matrix scoring (§15) + Goal Evaluation (§8).
    evidence_by_id = {e.id: e for e in all_evidence}
    scored: list[Alternative] = []
    for alt in eligible:
        goal_alignment = goal_evaluator.goal_alignment_score(alt, context.goals)
        matrix_scores = decision_matrix.score_alternative(
            alt, evidence_by_id=evidence_by_id, goal_alignment=goal_alignment
        )
        scored.append(alt.model_copy(update={"matrix_scores": matrix_scores}))

    ranked = decision_matrix.rank_alternatives(scored)
    chosen = ranked[0]

    unscored_rejected = [a for a in gated_alternatives if a.constraint_status != "eligible"]
    await repository.record_alternatives(scored + unscored_rejected)
    await repository.transition_process(process.id, status="decision_scoring")

    # Step: Validate internally -- re-confirm the chosen alternative still has support.
    validated_internally = bool(chosen.supporting_evidence_ids)

    # Step: Estimate confidence (§10).
    chosen_evidence = [
        evidence_by_id[eid] for eid in chosen.supporting_evidence_ids if eid in evidence_by_id
    ]
    confidence = confidence_module.estimate_confidence(
        evidence=chosen_evidence,
        memories=context.memories,
        knowledge=context.knowledge,
        alternatives=scored,
        degraded_steps=(1 if context_degraded else 0) + (0 if validated_internally else 1),
        total_steps=2,
    )
    if config.default_confidence_penalty:
        penalized = max(0.0, confidence.composite - config.default_confidence_penalty)
        confidence = confidence.model_copy(update={"composite": penalized})

    if confidence.composite >= verify_threshold:
        status = "decided"
        outcome = "decided"
    elif confidence.composite >= override_threshold:
        gap_penalty = _self_evaluation_gap_penalty(
            evidence_count=len(chosen_evidence),
            alternative_count=len(eligible),
            alternatives_below_minimum=below_minimum,
        )
        confidence = confidence.model_copy(
            update={"composite": max(0.0, confidence.composite - gap_penalty)}
        )
        status = "decided"
        outcome = "decided"
    else:
        status = "awaiting_human_override"
        outcome = "degraded"

    if context_degraded and outcome == "decided":
        outcome = "degraded"

    explanation = explanation_module.derive_explanation(
        chosen=chosen,
        alternatives=gated_alternatives,
        evidence_by_id=evidence_by_id,
        constraint_violations=violations,
        confidence=confidence,
    )
    decision = Decision(
        reasoning_process_id=process.id,
        selected_alternative_id=chosen.id,
        explanation=explanation,
        confidence_score=confidence.composite,
    )

    await repository.transition_process(process.id, status=status)  # type: ignore[arg-type]

    result_trace = trace_module.build_trace(
        process=process,
        context=context,
        confidence=confidence,
        execution_duration_ms=(time.monotonic() - start) * 1000,
        model_used=model_used,
        alternatives=scored,
        alternatives_rejected=explanation.rejected_reasons,
        final_decision_explanation=explanation.chosen_reason,
        outcome=outcome,  # type: ignore[arg-type]
    )
    await repository.finalize(process=process, decision=decision, trace=result_trace)
    return decision, result_trace


async def _fail(
    *,
    repository: ReasoningRepository,
    process: ReasoningProcess,
    context: ContextBundle,
    stage: str,
    reason: str,
    start: float,
) -> tuple[Decision, ReasoningTrace]:
    """Bible Part 8: "failure should improve future reasoning rather than
    terminate execution" -- every failure still produces a `Decision` (with
    no selected alternative) and a `ReasoningTrace` (§17, §19), never a
    process with no record."""
    recovery = failure_recovery.recommend_recovery(stage=stage, reason=reason, retry_count=0)
    explanation = explanation_module.DecisionExplanation(
        chosen_reason=f"No decision was produced: {recovery.reason}. Recommended recovery: "
        f"{recovery.action.value}.",
        remaining_uncertainty="Total -- no alternative survived to be scored.",
    )
    decision = Decision(
        reasoning_process_id=process.id,
        selected_alternative_id=None,
        explanation=explanation,
        confidence_score=0.0,
    )
    await repository.transition_process(process.id, status="failed")
    confidence = confidence_module.estimate_confidence(
        evidence=[], memories=context.memories, knowledge=context.knowledge, alternatives=[]
    )
    result_trace = trace_module.build_trace(
        process=process,
        context=context,
        confidence=confidence,
        execution_duration_ms=(time.monotonic() - start) * 1000,
        model_used=None,
        alternatives=[],
        alternatives_rejected={},
        final_decision_explanation=explanation.chosen_reason,
        outcome="failed",  # type: ignore[arg-type]
    )
    await repository.finalize(process=process, decision=decision, trace=result_trace)
    return decision, result_trace
