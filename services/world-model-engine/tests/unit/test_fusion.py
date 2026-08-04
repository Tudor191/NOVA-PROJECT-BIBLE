from datetime import UTC, datetime
from uuid import uuid4

from nova_world_model_engine.domain.fusion import PerceptionSignal, fuse_window


def test_no_signals_produces_no_update() -> None:
    assert fuse_window([]) is None


def test_single_signal_confidence_is_its_own_base() -> None:
    user_id = uuid4()
    signal = PerceptionSignal(
        source="calendar",
        user_id=user_id,
        observed_at=datetime.now(UTC),
        suggested_activity="meeting",
        base_confidence=0.5,
    )
    fused = fuse_window([signal])
    assert fused is not None
    assert fused.activity == "meeting"
    assert fused.confidence == 0.5


def test_agreement_increases_confidence_never_decreases() -> None:
    user_id = uuid4()
    now = datetime.now(UTC)
    one_signal = [
        PerceptionSignal(
            source="calendar", user_id=user_id, observed_at=now, suggested_activity="meeting"
        )
    ]
    two_agreeing = [
        *one_signal,
        PerceptionSignal(
            source="voice", user_id=user_id, observed_at=now, suggested_activity="meeting"
        ),
    ]
    confidence_one = fuse_window(one_signal).confidence  # type: ignore[union-attr]
    confidence_two = fuse_window(two_agreeing).confidence  # type: ignore[union-attr]
    assert confidence_two > confidence_one


def test_majority_activity_wins_disagreement() -> None:
    user_id = uuid4()
    now = datetime.now(UTC)
    signals = [
        PerceptionSignal(
            source="calendar", user_id=user_id, observed_at=now, suggested_activity="meeting"
        ),
        PerceptionSignal(
            source="voice", user_id=user_id, observed_at=now, suggested_activity="meeting"
        ),
        PerceptionSignal(
            source="filesystem", user_id=user_id, observed_at=now, suggested_activity="coding"
        ),
    ]
    fused = fuse_window(signals)
    assert fused is not None
    assert fused.activity == "meeting"


def test_confidence_never_exceeds_max() -> None:
    user_id = uuid4()
    now = datetime.now(UTC)
    signals = [
        PerceptionSignal(
            source=f"source-{i}",
            user_id=user_id,
            observed_at=now,
            suggested_activity="meeting",
            base_confidence=0.9,
        )
        for i in range(10)
    ]
    fused = fuse_window(signals)
    assert fused is not None
    assert fused.confidence <= 0.99
