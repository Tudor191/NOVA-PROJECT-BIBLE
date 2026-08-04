"""Acquisition -- accept raw input from any source, hand off to normalization
(docs/design/phase-1/02-knowledge-engine.md §1-3). Must never decide truth or
confidence itself (that's `validation.py`'s job) -- this module only orchestrates
the pipeline sequence traced in §3's sequence diagram: normalize -> validate ->
check_for_conflicts -> (create-or-corroborate | record contradiction).
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid4

from nova_contracts import ContradictionPayload
from pydantic import BaseModel

from nova_knowledge_engine.domain import contradiction, graph_operations, normalization, validation
from nova_knowledge_engine.domain.models import Contradiction, KnowledgeNode, SourceAttribution
from nova_knowledge_engine.domain.normalization import RawInformation
from nova_knowledge_engine.domain.ports import KnowledgeMetadataRepository, OutboxEvent

ACQUISITION_ACTOR = "knowledge-engine.acquisition"


class AcquisitionResult(BaseModel):
    outcome: Literal["created", "corroborated", "conflict"]
    node: KnowledgeNode | None = None
    conflict: Contradiction | None = None


async def ingest(
    repository: KnowledgeMetadataRepository,
    raw: RawInformation,
    *,
    correlation_id: UUID | None = None,
) -> AcquisitionResult:
    """The full pipeline (§3)."""
    correlation_id = correlation_id or uuid4()
    candidate = normalization.normalize(raw)
    validated = await validation.validate(candidate, repository=repository)

    conflict = await contradiction.check_for_conflicts(validated, repository=repository)
    if conflict is not None:
        outbox = OutboxEvent(
            subject="knowledge.contradiction.detected",
            payload=ContradictionPayload(
                contradiction_id=conflict.id,
                node_a_id=conflict.node_a_id,
                node_b_id=conflict.node_b_id,
                description=conflict.description,
                status=conflict.status,
            ).model_dump(mode="json"),
            correlation_id=correlation_id,
        )
        recorded = await repository.create_contradiction(conflict, outbox_event=outbox)
        return AcquisitionResult(outcome="conflict", conflict=recorded)

    source = SourceAttribution(
        node_id=candidate.node_id,
        source_type=candidate.source_type,
        source_ref=candidate.source_ref,
        excerpt=candidate.excerpt,
        confidence_contribution=validated.confidence,
    )

    if validated.existing is None:
        node = KnowledgeNode(
            node_id=candidate.node_id,
            label=candidate.label,
            name=candidate.name,
            domain=candidate.domain,
            scope=candidate.scope,
            project_id=candidate.project_id,
            user_id=candidate.user_id,
            confidence=validated.confidence,
            privacy_level=candidate.privacy_level,
        )
        created = await graph_operations.create_node(
            repository,
            node=node,
            source=source,
            actor=ACQUISITION_ACTOR,
            correlation_id=correlation_id,
        )
        return AcquisitionResult(outcome="created", node=created)

    existing = validated.existing
    updated_node = existing.model_copy(update={"confidence": validated.confidence})
    corroborated = await graph_operations.corroborate_node(
        repository,
        node=updated_node,
        expected_version=existing.version,
        source=source,
        actor=ACQUISITION_ACTOR,
        correlation_id=correlation_id,
    )
    return AcquisitionResult(outcome="corroborated", node=corroborated)
