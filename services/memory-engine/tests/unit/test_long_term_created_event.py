"""`memory.long_term.created` carries the memory's own `created_at`.

Phase 4E (TDD 4E §0.1.5) made this field the one legal way another engine can
learn *when* a memory was created: ADR-004 forbids `digital-twin-engine` reading
`memory-engine` over HTTP, and the envelope's `occurred_at` records when the
event was *published*, which for a historically-dated memory is a different
moment entirely. Bible Part 16's Project Model measures AC-6's multi-week gap in
exactly this value, so an event that dropped it would silently reduce every
reconstruction to "everything happened when the bus delivered it".

Default tier (no Docker): the fake repository records the outbox row the real one
would have written, which is where the payload is decided.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from nova_contracts import LongTermMemoryCreatedPayload
from nova_memory_engine.domain import long_term
from nova_memory_engine.domain.models import MemoryType, PrivacyLevel

from tests.fakes.memory_repository import FakeMemoryRepository


async def _write(repository: FakeMemoryRepository, **overrides: object):  # type: ignore[no-untyped-def]
    return await long_term.write(
        repository,
        user_id=overrides.pop("user_id", uuid4()),  # type: ignore[arg-type]
        memory_type=MemoryType.EPISODIC,
        content="Closed out the ingest retry work.",
        correlation_id=uuid4(),
        **overrides,  # type: ignore[arg-type]
    )


async def test_the_created_event_carries_the_records_own_created_at() -> None:
    repository = FakeMemoryRepository()

    record = await _write(repository)

    payload = LongTermMemoryCreatedPayload.model_validate(repository.outbox_events[-1].payload)
    assert payload.created_at == record.created_at, (
        "the event's created_at is not the record's own -- a consumer deriving a "
        "timeline from this subject would be reading the wrong instant"
    )
    assert payload.memory_id == record.id


async def test_the_created_event_preserves_a_historical_timestamp() -> None:
    """The AC-6 shape at the event layer.

    `long_term.write()` does not accept a `created_at` (deliberately -- TDD 4E
    §20.1 forbids widening it), so this drives the path the Phase 4E test driver
    uses: build the record, then persist it. What is asserted here is that the
    payload is derived from the *record*, not from `datetime.now()` -- which is
    what makes a historically-dated write reach a consumer intact.
    """
    from nova_memory_engine.domain.models import MemoryRecord
    from nova_memory_engine.domain.ports import OutboxEvent

    repository = FakeMemoryRepository()
    written_at = datetime.now(UTC) - timedelta(days=45)
    record = MemoryRecord(
        memory_type=MemoryType.PROJECT,
        content="Chose the outbox over dual writes.",
        user_id=uuid4(),
        project_id=uuid4(),
        created_at=written_at,
        updated_at=written_at,
    )

    await repository.create_long_term(
        record,
        outbox_event=OutboxEvent(
            subject="memory.long_term.created",
            payload=LongTermMemoryCreatedPayload(
                memory_id=record.id,
                user_id=record.user_id,
                project_id=record.project_id,
                memory_type=record.memory_type,
                importance_score=record.importance_score,
                confidence=record.confidence,
                privacy_level=record.privacy_level,
                knowledge_node_id=record.knowledge_node_id,
                created_at=record.created_at,
            ).model_dump(mode="json"),
            correlation_id=uuid4(),
        ),
    )

    payload = LongTermMemoryCreatedPayload.model_validate(repository.outbox_events[-1].payload)
    assert payload.created_at == written_at
    assert payload.created_at is not None
    assert (datetime.now(UTC) - payload.created_at) > timedelta(days=40), (
        "the payload's timestamp is not actually historical"
    )


async def test_created_at_is_optional_so_an_older_publisher_still_validates() -> None:
    """ADR-024's additive rule, asserted rather than assumed.

    An envelope published before this field existed -- or by any consumer's
    replay of one -- must still validate, and must surface the absence honestly
    as `None` rather than as a fabricated timestamp.
    """
    payload = LongTermMemoryCreatedPayload.model_validate(
        {
            "memory_id": str(uuid4()),
            "user_id": str(uuid4()),
            "memory_type": MemoryType.SEMANTIC.value,
            "importance_score": 0.5,
            "privacy_level": PrivacyLevel.INTERNAL.value,
        }
    )
    assert payload.created_at is None
