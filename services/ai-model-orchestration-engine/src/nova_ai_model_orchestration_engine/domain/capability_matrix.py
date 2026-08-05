"""Per-model capability scoring -- Bible Part 7 "Model Capability Matrix"
(docs/design/phase-2a/00-ai-model-orchestration-engine.md §2). Pure lookups/
comparisons over `ModelDescriptor.capability_scores`; no I/O, no provider calls.
"""

from __future__ import annotations

from nova_ai_model_orchestration_engine.domain.models import (
    CapabilityDimension,
    Modality,
    ModelDescriptor,
    PrivacyLevel,
)

__all__ = ["eligible_candidates", "task_type_to_dimension"]

# Maps a free-text `GenerateRequest.task_type` to the Part 7 capability dimension
# it's scored against. Deliberately a small, explicit table, not a classifier --
# unrecognized task types fall back to "general_conversation" rather than raising,
# since a caller declaring a task type this engine doesn't recognize is a normal,
# expected case (§7 of the design doc's routing pipeline still must produce a
# result), not an error.
_TASK_TYPE_DIMENSION: dict[str, CapabilityDimension] = {
    "general_conversation": "general_conversation",
    "programming": "programming",
    "code_review": "programming",
    "reasoning": "reasoning",
    "mathematics": "mathematics",
    "translation": "translation",
    "vision": "vision",
    "speech": "speech",
    "planning": "planning",
    "creativity": "creativity",
    "research": "research",
    "tool_usage": "tool_usage",
    "long_context": "long_context",
}


def task_type_to_dimension(task_type: str) -> CapabilityDimension:
    return _TASK_TYPE_DIMENSION.get(task_type, "general_conversation")


def _privacy_rank(level: PrivacyLevel) -> int:
    order = [
        PrivacyLevel.PUBLIC,
        PrivacyLevel.INTERNAL,
        PrivacyLevel.CONFIDENTIAL,
        PrivacyLevel.HIGHLY_SENSITIVE,
    ]
    return order.index(level)


def eligible_candidates(
    models: list[ModelDescriptor],
    *,
    modality: Modality,
    privacy_hint: PrivacyLevel,
) -> list[ModelDescriptor]:
    """Every registered, healthy model that supports `modality` and is permitted
    to serve a request classified at `privacy_hint` (Part 7 "Privacy Management").
    A model's `max_privacy_tier` is the *highest* (most sensitive) tier it may
    serve -- a `HIGHLY_SENSITIVE` request is only eligible for a model whose
    ceiling is `HIGHLY_SENSITIVE` itself (in practice, a local model), never a
    cloud model capped lower, per the design doc §18's hard gate with no
    override."""
    return [
        m
        for m in models
        if modality in m.modalities
        and m.health_status != "unhealthy"
        and _privacy_rank(m.max_privacy_tier) >= _privacy_rank(privacy_hint)
    ]
