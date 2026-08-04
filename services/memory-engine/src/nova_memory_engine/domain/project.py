"""Project Memory -- docs/design/phase-1/01-memory-engine.md §2. Cross-cutting,
not a distinct content shape: any long-term memory scoped to a `project_id`, filtered
at query time. This module exists as the named, documented entry point Part 3
expects, even though it delegates entirely to `long_term.py` with `project_id`
required."""

from __future__ import annotations

from uuid import UUID

from nova_memory_engine.domain import long_term
from nova_memory_engine.domain.models import MemoryRecord, MemoryType, PrivacyLevel, ProjectData
from nova_memory_engine.domain.ports import MemoryRepository


async def remember(
    repository: MemoryRepository,
    *,
    user_id: UUID,
    project_id: UUID,
    content: str,
    correlation_id: UUID,
    confidence: float | None = None,
    privacy_level: PrivacyLevel = PrivacyLevel.INTERNAL,
    source: str | None = None,
    source_ref: UUID | None = None,
    importance_score: float = 0.5,
) -> MemoryRecord:
    data = ProjectData()
    return await long_term.write(
        repository,
        user_id=user_id,
        memory_type=MemoryType.PROJECT,
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


async def recall_for_project(
    repository: MemoryRepository, *, user_id: UUID, project_id: UUID, limit: int = 50
) -> list[MemoryRecord]:
    """Project Memory scoping: retrieving `project_id=X` context returns only that
    project's memories (docs/roadmap/ENGINEERING_ROADMAP.md Phase 1 acceptance
    criteria)."""
    return await repository.list_by_timeline(user_id=user_id, project_id=project_id, limit=limit)
