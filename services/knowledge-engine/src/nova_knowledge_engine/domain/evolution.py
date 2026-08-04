"""Knowledge evolution -- the layer-maturity state machine (docs/design/phase-1/
02-knowledge-engine.md §6). Decides when a node's `layer` advances; never performs
the write itself -- returns a decision, `workers/maintenance_worker.py` executes it
via `graph_operations.advance_layer`.
"""

from __future__ import annotations

from dataclasses import dataclass

from nova_knowledge_engine.domain.models import KnowledgeLayer, UsageSummary

VERIFIED_MIN_CONFIDENCE = 0.7
VERIFIED_MIN_SOURCES = 1
CONNECTED_MIN_RELATIONSHIPS = 2
EXPERT_MIN_CONFIDENCE = 0.9
EXPERT_MIN_USAGE_COUNT = 5
STRATEGIC_MIN_DISTINCT_PROJECTS = 2


@dataclass(frozen=True, slots=True)
class EvolutionInput:
    layer: KnowledgeLayer
    confidence: float
    source_count: int
    relationship_count: int
    usage: UsageSummary


@dataclass(frozen=True, slots=True)
class LayerAdvanceDecision:
    node_id: str
    from_layer: KnowledgeLayer
    to_layer: KnowledgeLayer
    reason: str


def next_layer(node_id: str, evaluation: EvolutionInput) -> LayerAdvanceDecision | None:
    """Evaluates exactly the predicates in §6's state diagram, in order, advancing
    at most one layer per call -- `workers/maintenance_worker.py` calls this again
    on its next run if a node qualifies for a further advance. One hop per pass
    keeps each transition an individually audited `node_version_history` row
    (Part 10's versioning requirement), rather than silently skipping intermediate
    layers in one write."""
    layer = evaluation.layer

    if layer is KnowledgeLayer.RAW:
        return None  # Raw -> Processed happens at acquisition/normalization time.

    if layer is KnowledgeLayer.PROCESSED:
        if (
            evaluation.confidence >= VERIFIED_MIN_CONFIDENCE
            and evaluation.source_count >= VERIFIED_MIN_SOURCES
        ):
            return LayerAdvanceDecision(
                node_id=node_id,
                from_layer=layer,
                to_layer=KnowledgeLayer.VERIFIED,
                reason=(
                    f"confidence {evaluation.confidence:.2f} >= "
                    f"{VERIFIED_MIN_CONFIDENCE} AND {evaluation.source_count} "
                    f"corroborating source(s)"
                ),
            )
        return None

    if layer is KnowledgeLayer.VERIFIED:
        if evaluation.relationship_count >= CONNECTED_MIN_RELATIONSHIPS:
            return LayerAdvanceDecision(
                node_id=node_id,
                from_layer=layer,
                to_layer=KnowledgeLayer.CONNECTED,
                reason=f"{evaluation.relationship_count} graph relationships exist",
            )
        return None

    if layer is KnowledgeLayer.CONNECTED:
        if evaluation.usage.usage_count >= 1:
            return LayerAdvanceDecision(
                node_id=node_id,
                from_layer=layer,
                to_layer=KnowledgeLayer.APPLIED,
                reason="referenced by a completed task/decision",
            )
        return None

    if layer is KnowledgeLayer.APPLIED:
        if (
            evaluation.confidence >= EXPERT_MIN_CONFIDENCE
            and evaluation.usage.usage_count >= EXPERT_MIN_USAGE_COUNT
        ):
            return LayerAdvanceDecision(
                node_id=node_id,
                from_layer=layer,
                to_layer=KnowledgeLayer.EXPERT,
                reason=(
                    f"confidence {evaluation.confidence:.2f} >= "
                    f"{EXPERT_MIN_CONFIDENCE} AND usage_count "
                    f"{evaluation.usage.usage_count} >= {EXPERT_MIN_USAGE_COUNT}"
                ),
            )
        return None

    if layer is KnowledgeLayer.EXPERT:
        distinct_projects = len(set(evaluation.usage.distinct_project_ids))
        if distinct_projects >= STRATEGIC_MIN_DISTINCT_PROJECTS:
            return LayerAdvanceDecision(
                node_id=node_id,
                from_layer=layer,
                to_layer=KnowledgeLayer.STRATEGIC,
                reason=f"referenced across {distinct_projects} distinct projects",
            )
        return None

    return None  # STRATEGIC is terminal -- no forward edge in §6's diagram.
