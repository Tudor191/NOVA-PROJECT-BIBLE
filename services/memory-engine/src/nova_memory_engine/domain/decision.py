"""Decision Memory -- docs/design/phase-1/01-memory-engine.md §2. Richer than the
other categories by design: both Part 3 (Decision Memory) and Part 8 (Confidence
System / Reasoning Memory) need the full alternatives/reasoning/tradeoffs/risks
shape, so it gets first-class columns (`decision_record`) rather than living only
in `type_data`.
"""

from __future__ import annotations

from uuid import UUID

from nova_contracts import DecisionRecordedPayload

from nova_memory_engine.domain import long_term
from nova_memory_engine.domain.models import (
    DecisionData,
    DecisionRecord,
    MemoryRecord,
    MemoryType,
    PrivacyLevel,
)
from nova_memory_engine.domain.ports import MemoryRepository, OutboxEvent

DEFAULT_IMPORTANCE_SCORE = 0.6
"""Decisions default a little above the generic 0.5 -- they are, definitionally,
things NOVA judged worth deliberating over."""


async def record(
    repository: MemoryRepository,
    *,
    user_id: UUID,
    objective: str,
    alternatives: list[str],
    chosen_alternative: str,
    reasoning: str,
    correlation_id: UUID,
    tradeoffs: list[str] | None = None,
    risks: list[str] | None = None,
    confidence_at_decision: float | None = None,
    project_id: UUID | None = None,
    privacy_level: PrivacyLevel = PrivacyLevel.INTERNAL,
    importance_score: float = DEFAULT_IMPORTANCE_SCORE,
) -> tuple[MemoryRecord, DecisionRecord]:
    memory_record = await long_term.write(
        repository,
        user_id=user_id,
        memory_type=MemoryType.DECISION,
        content=f"{objective}: chose {chosen_alternative}",
        type_data=DecisionData().model_dump(mode="json"),
        project_id=project_id,
        confidence=confidence_at_decision,
        privacy_level=privacy_level,
        importance_score=importance_score,
        correlation_id=correlation_id,
    )
    decision_record = DecisionRecord(
        memory_record_id=memory_record.id,
        objective=objective,
        alternatives=alternatives,
        chosen_alternative=chosen_alternative,
        reasoning=reasoning,
        tradeoffs=tradeoffs or [],
        risks=risks or [],
        confidence_at_decision=confidence_at_decision,
    )
    outbox_event = OutboxEvent(
        subject="memory.decision.recorded",
        payload=DecisionRecordedPayload(
            decision_id=decision_record.id,
            memory_id=memory_record.id,
            user_id=user_id,
            objective=objective,
            chosen_alternative=chosen_alternative,
            confidence_at_decision=confidence_at_decision,
        ).model_dump(mode="json"),
        correlation_id=correlation_id,
    )
    stored_decision = await repository.create_decision(decision_record, outbox_event=outbox_event)
    return memory_record, stored_decision


async def get(repository: MemoryRepository, decision_id: UUID) -> DecisionRecord | None:
    return await repository.get_decision(decision_id)


async def search(
    repository: MemoryRepository, *, user_id: UUID, limit: int = 50
) -> list[DecisionRecord]:
    return await repository.search_decisions(user_id=user_id, limit=limit)
