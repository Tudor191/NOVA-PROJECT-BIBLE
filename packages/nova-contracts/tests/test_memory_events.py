from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from nova_contracts import (
    ConsolidationCompletedPayload,
    EventEnvelope,
    LifecycleState,
    LifecycleTransitionedPayload,
    LongTermMemoryCreatedPayload,
    MemoryRetrieveRequestPayload,
    MemorySearchResultPayload,
    MemoryType,
    PrivacyLevel,
    known_subjects,
    validate_payload,
)
from pydantic import ValidationError


def test_all_memory_subjects_are_registered() -> None:
    subjects = known_subjects()
    for subject in (
        "memory.short_term.created",
        "memory.long_term.created",
        "memory.long_term.updated",
        "memory.consolidation.started",
        "memory.consolidation.completed",
        "memory.lifecycle.transitioned",
        "memory.decision.recorded",
        "memory.embedding.completed",
        "memory.retrieve.request",
    ):
        assert subject in subjects


def test_long_term_memory_created_validates_against_registry() -> None:
    validated = validate_payload(
        "memory.long_term.created",
        {
            "memory_id": str(uuid4()),
            "user_id": str(uuid4()),
            "memory_type": "episodic",
            "importance_score": 0.7,
            "privacy_level": "internal",
        },
    )
    assert isinstance(validated, LongTermMemoryCreatedPayload)
    assert validated.memory_type is MemoryType.EPISODIC
    assert validated.privacy_level is PrivacyLevel.INTERNAL


# --- `created_at`, added by Phase 4E (TDD 4E §0.1.5) ---------------------------
#
# Protocol §8.1: a contract change carries its own contract test. 4E added this
# field with consumer tests in `digital-twin-engine` and `memory-engine`, and
# none here (closure-matrix N-08).


def test_a_created_event_without_created_at_still_validates() -> None:
    """ADR-024's additive rule: a producer written before 4E, or an in-flight
    envelope, omits the field and must still be accepted -- as "no timestamp
    evidence", never as a fabricated one."""
    validated = validate_payload(
        "memory.long_term.created",
        {
            "memory_id": str(uuid4()),
            "user_id": str(uuid4()),
            "memory_type": "episodic",
            "importance_score": 0.5,
            "privacy_level": "internal",
        },
    )
    assert isinstance(validated, LongTermMemoryCreatedPayload)
    assert validated.created_at is None


def test_a_historical_created_at_survives_the_wire_and_is_not_the_envelopes() -> None:
    """The field exists because a memory's creation and its event's publication
    are different moments: the envelope's `occurred_at` is the second."""
    created = datetime(2026, 8, 1, 9, 30, tzinfo=UTC)
    envelope = EventEnvelope(
        subject="memory.long_term.created",
        source_engine="memory-engine",
        correlation_id=uuid4(),
        payload=LongTermMemoryCreatedPayload(
            memory_id=uuid4(),
            user_id=uuid4(),
            memory_type=MemoryType.EPISODIC,
            importance_score=0.5,
            privacy_level=PrivacyLevel.INTERNAL,
            created_at=created,
        ).model_dump(mode="json"),
    )

    received = EventEnvelope.model_validate_json(envelope.model_dump_json())
    payload = validate_payload(received.subject, received.payload)

    assert isinstance(payload, LongTermMemoryCreatedPayload)
    assert payload.created_at == created
    assert received.occurred_at - payload.created_at > timedelta(days=1)


def test_created_at_must_be_a_timestamp() -> None:
    with pytest.raises(ValidationError):
        LongTermMemoryCreatedPayload(
            memory_id=uuid4(),
            user_id=uuid4(),
            memory_type=MemoryType.EPISODIC,
            importance_score=0.5,
            privacy_level=PrivacyLevel.INTERNAL,
            created_at="three weeks ago",  # type: ignore[arg-type]
        )


def test_importance_score_must_be_in_unit_interval() -> None:
    with pytest.raises(ValidationError):
        LongTermMemoryCreatedPayload(
            memory_id=uuid4(),
            user_id=uuid4(),
            memory_type=MemoryType.SEMANTIC,
            importance_score=1.5,
            privacy_level=PrivacyLevel.INTERNAL,
        )


def test_lifecycle_transitioned_payload_round_trips() -> None:
    payload = LifecycleTransitionedPayload(
        memory_id=uuid4(),
        user_id=uuid4(),
        previous_state=LifecycleState.ACTIVE,
        new_state=LifecycleState.WEAK,
        reason="30d since last access AND importance < 0.3",
    )
    assert payload.previous_state is LifecycleState.ACTIVE
    assert payload.new_state is LifecycleState.WEAK


def test_consolidation_completed_counts_are_non_negative() -> None:
    with pytest.raises(ValidationError):
        ConsolidationCompletedPayload(
            run_id=uuid4(),
            records_scanned=-1,
            records_merged=0,
            records_advanced=0,
            records_deleted=0,
            status="completed",
        )


def test_memory_retrieve_request_limit_bounds() -> None:
    with pytest.raises(ValidationError):
        MemoryRetrieveRequestPayload(user_id=uuid4(), limit=1000)

    request = MemoryRetrieveRequestPayload(user_id=uuid4(), query_text="dark mode")
    assert request.limit == 10
    assert request.include_relationships is False


def test_memory_search_result_carries_component_scores() -> None:
    result = MemorySearchResultPayload(
        memory_id=uuid4(),
        memory_type=MemoryType.PREFERENCE,
        content="prefers dark mode",
        score=0.87,
        similarity=0.91,
        importance_score=0.6,
        recency_decay=0.95,
        confidence=0.8,
    )
    assert result.memory_type is MemoryType.PREFERENCE
