"""The Reasoning Trace (docs/design/phase-2b/00-reasoning-engine.md §19) --
assembles the structured `ReasoningTrace` from everything the pipeline
touched, on every run, success or failure alike. Not chain-of-thought
exposure: structured metadata *about* the reasoning process, never a
transcript *of* it.
"""

from __future__ import annotations

from uuid import UUID

from nova_reasoning_engine.domain.models import (
    Alternative,
    ConfidenceBreakdown,
    ContextBundle,
    ReasoningOutcome,
    ReasoningProcess,
    ReasoningTrace,
)

__all__ = ["build_trace", "world_model_entities"]


def world_model_entities(context: ContextBundle) -> list[str]:
    """§7.2 -- entity/object IDs referenced. `WorldModelSnapshot` (Phase 2B)
    carries Active Context fields, not a list of discrete object IDs, so the
    honest best-effort here is every non-null field that identifies a
    specific entity (project, device, task, activity) rather than free-text
    like `objective`."""
    wm = context.world_model
    if wm is None:
        return []
    return [
        str(value)
        for value in (wm.project_id, wm.device, wm.task, wm.activity)
        if value is not None
    ]


def build_trace(
    *,
    process: ReasoningProcess,
    context: ContextBundle,
    confidence: ConfidenceBreakdown,
    execution_duration_ms: float,
    model_used: str | None,
    alternatives: list[Alternative],
    alternatives_rejected: dict[UUID, str],
    final_decision_explanation: str,
    outcome: ReasoningOutcome,
    steps: list[ReasoningTrace] | None = None,
) -> ReasoningTrace:
    """§19, in full. `steps` is populated only for multi-step processes
    (§11)."""
    return ReasoningTrace(
        reasoning_process_id=process.id,
        correlation_id=process.correlation_id,
        reasoning_mode=process.reasoning_mode,
        reasoning_level=process.reasoning_level,
        retrieved_memory_ids=[m.memory_id for m in context.memories],
        knowledge_ids=[k.node_id for k in context.knowledge],
        world_model_entities=world_model_entities(context),
        goals_considered=[g.id for g in context.goals],
        constraints_considered=context.constraints,
        selected_capabilities=[],
        confidence_score=confidence.composite,
        confidence_breakdown=confidence,
        execution_duration_ms=execution_duration_ms,
        model_used=model_used,
        alternatives_evaluated=[a.id for a in alternatives],
        alternatives_rejected=alternatives_rejected,
        final_decision_explanation=final_decision_explanation,
        steps=steps or [],
        outcome=outcome,
    )
