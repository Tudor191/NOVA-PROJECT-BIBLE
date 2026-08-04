from uuid import uuid4

import pytest
from nova_memory_engine.domain.models import (
    EpisodicData,
    MemoryRecord,
    MemoryType,
    PreferenceData,
    PrivacyLevel,
)
from pydantic import ValidationError


def test_memory_record_defaults() -> None:
    record = MemoryRecord(
        memory_type=MemoryType.SEMANTIC, content="Python is a language", user_id=uuid4()
    )

    assert record.importance_score == 0.5
    assert record.privacy_level is PrivacyLevel.INTERNAL
    assert record.lifecycle_state.value == "active"
    assert record.version == 1
    assert record.embedding is None


def test_importance_score_bounds_enforced() -> None:
    with pytest.raises(ValidationError):
        MemoryRecord(
            memory_type=MemoryType.SEMANTIC,
            content="x",
            user_id=uuid4(),
            importance_score=1.5,
        )


def test_episodic_data_defaults() -> None:
    data = EpisodicData()
    assert data.participants == []
    assert data.memory_type is MemoryType.EPISODIC


def test_preference_data_requires_key_and_value() -> None:
    with pytest.raises(ValidationError):
        PreferenceData()  # type: ignore[call-arg]

    data = PreferenceData(key="theme", value="dark")
    assert data.evidence_count == 1
