"""Procedural Memory -- docs/design/phase-1/01-memory-engine.md §2. How to do
things: steps, preconditions, tools. Delegates persistence to `long_term.py`."""

from __future__ import annotations

from uuid import UUID

from nova_memory_engine.domain import long_term
from nova_memory_engine.domain.models import MemoryRecord, MemoryType, PrivacyLevel, ProceduralData
from nova_memory_engine.domain.ports import MemoryRepository


async def remember(
    repository: MemoryRepository,
    *,
    user_id: UUID,
    content: str,
    correlation_id: UUID,
    steps: list[str] | None = None,
    preconditions: list[str] | None = None,
    tools_required: list[str] | None = None,
    project_id: UUID | None = None,
    confidence: float | None = None,
    privacy_level: PrivacyLevel = PrivacyLevel.INTERNAL,
    source: str | None = None,
    source_ref: UUID | None = None,
    importance_score: float = 0.5,
) -> MemoryRecord:
    data = ProceduralData(
        steps=steps or [],
        preconditions=preconditions or [],
        tools_required=tools_required or [],
    )
    return await long_term.write(
        repository,
        user_id=user_id,
        memory_type=MemoryType.PROCEDURAL,
        content=content,
        type_data=data.model_dump(mode="json"),
        project_id=project_id,
        confidence=confidence,
        privacy_level=privacy_level,
        source=source,
        source_ref=source_ref,
        importance_score=importance_score,
        correlation_id=correlation_id,
    )
