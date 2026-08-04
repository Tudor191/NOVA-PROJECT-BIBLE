"""Episodic Memory -- docs/design/phase-1/01-memory-engine.md §2. Specific events
and their outcomes. Delegates persistence to `long_term.py`."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from nova_memory_engine.domain import long_term
from nova_memory_engine.domain.models import EpisodicData, MemoryRecord, MemoryType, PrivacyLevel
from nova_memory_engine.domain.ports import MemoryRepository


async def remember(
    repository: MemoryRepository,
    *,
    user_id: UUID,
    content: str,
    correlation_id: UUID,
    participants: list[str] | None = None,
    timeline_start: datetime | None = None,
    timeline_end: datetime | None = None,
    outcome: str | None = None,
    lessons_learned: str | None = None,
    project_id: UUID | None = None,
    confidence: float | None = None,
    privacy_level: PrivacyLevel = PrivacyLevel.INTERNAL,
    source: str | None = None,
    source_ref: UUID | None = None,
    importance_score: float = 0.5,
) -> MemoryRecord:
    data = EpisodicData(
        participants=participants or [],
        timeline_start=timeline_start,
        timeline_end=timeline_end,
        outcome=outcome,
        lessons_learned=lessons_learned,
    )
    return await long_term.write(
        repository,
        user_id=user_id,
        memory_type=MemoryType.EPISODIC,
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
