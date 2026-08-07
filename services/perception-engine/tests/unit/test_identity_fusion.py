"""`domain/identity_fusion.py` -- the evidence-fusion algorithm
(docs/design/phase-2d/03-perception-engine.md Sec8). Critically, a direct,
mechanical test that a single strong signal never produces a `high` tier
verdict (Sec0.4's ceiling), and that continuous reassessment (Sec0.10)
increases, decreases, and stabilizes as the summary claims -- not merely
asserted in prose."""

from __future__ import annotations

from uuid import uuid4

from nova_perception_engine.domain.identity_fusion import (
    SINGLE_SIGNAL_CONFIDENCE_CEILING,
    ModalitySignal,
    fuse_window,
    smooth,
    tier_for,
)


def test_tier_boundaries() -> None:
    assert tier_for(0.85) == "high"
    assert tier_for(0.84999) == "medium"
    assert tier_for(0.6) == "medium"
    assert tier_for(0.35) == "low"
    assert tier_for(0.0) == "unknown"


def test_single_signal_never_reaches_high_confidence_even_at_max_raw_score() -> None:
    identity_id = uuid4()
    result = fuse_window(
        [ModalitySignal(modality="voice", candidate_identity_id=identity_id, confidence=0.99)]
    )
    assert result.fused_confidence <= SINGLE_SIGNAL_CONFIDENCE_CEILING
    assert result.confidence_tier != "high"


def test_agreeing_signals_boost_confidence_above_the_single_signal_ceiling() -> None:
    identity_id = uuid4()
    result = fuse_window(
        [
            ModalitySignal(modality="voice", candidate_identity_id=identity_id, confidence=0.8),
            ModalitySignal(modality="face", candidate_identity_id=identity_id, confidence=0.8),
        ]
    )
    assert result.fused_confidence > SINGLE_SIGNAL_CONFIDENCE_CEILING
    assert result.confidence_tier == "high"
    assert result.disagreement is False


def test_disagreeing_signals_are_suppressed_not_averaged() -> None:
    a, b = uuid4(), uuid4()
    result = fuse_window(
        [
            ModalitySignal(modality="voice", candidate_identity_id=a, confidence=0.9),
            ModalitySignal(modality="face", candidate_identity_id=b, confidence=0.9),
        ]
    )
    assert result.disagreement is True
    assert result.confidence_tier in ("low", "unknown")
    # never averaged to (0.9+0.9)/2 = 0.9, which would be "high"
    assert result.fused_confidence < 0.85


def test_empty_signal_window_produces_unknown_with_no_identity() -> None:
    result = fuse_window([])
    assert result.identity_id is None
    assert result.confidence_tier == "unknown"


def test_per_modality_signals_are_recorded_for_audit() -> None:
    identity_id = uuid4()
    result = fuse_window(
        [ModalitySignal(modality="voice", candidate_identity_id=identity_id, confidence=0.7)]
    )
    assert "voice" in result.per_modality_signals


def test_smoothing_dampens_a_single_anomalous_window() -> None:
    identity_id = uuid4()
    presence_session_id, user_id = uuid4(), uuid4()

    steady = fuse_window(
        [
            ModalitySignal(modality="voice", candidate_identity_id=identity_id, confidence=0.8),
            ModalitySignal(modality="face", candidate_identity_id=identity_id, confidence=0.8),
        ]
    )
    state = None
    for _ in range(5):
        state = smooth(
            state, steady, presence_session_id=presence_session_id, user_id=user_id
        )
    assert state is not None
    assert state.smoothed_tier == "high"

    # One anomalous low-confidence window should not immediately crash the tier.
    anomalous = fuse_window(
        [ModalitySignal(modality="voice", candidate_identity_id=identity_id, confidence=0.1)]
    )
    after_anomaly = smooth(
        state, anomalous, presence_session_id=presence_session_id, user_id=user_id
    )
    assert after_anomaly.smoothed_confidence > anomalous.fused_confidence
    assert after_anomaly.smoothed_confidence < state.smoothed_confidence


def test_sustained_weak_evidence_lowers_smoothed_confidence() -> None:
    identity_id = uuid4()
    presence_session_id, user_id = uuid4(), uuid4()

    strong = fuse_window(
        [
            ModalitySignal(modality="voice", candidate_identity_id=identity_id, confidence=0.9),
            ModalitySignal(modality="face", candidate_identity_id=identity_id, confidence=0.9),
        ]
    )
    state = None
    for _ in range(5):
        state = smooth(state, strong, presence_session_id=presence_session_id, user_id=user_id)
    assert state is not None
    initial_confidence = state.smoothed_confidence

    weak = fuse_window(
        [ModalitySignal(modality="voice", candidate_identity_id=identity_id, confidence=0.1)]
    )
    for _ in range(8):
        state = smooth(state, weak, presence_session_id=presence_session_id, user_id=user_id)

    assert state.smoothed_confidence < initial_confidence
    assert state.smoothed_tier in ("low", "unknown")


def test_observation_count_increments_across_windows() -> None:
    identity_id = uuid4()
    presence_session_id, user_id = uuid4(), uuid4()
    window = fuse_window(
        [ModalitySignal(modality="voice", candidate_identity_id=identity_id, confidence=0.6)]
    )
    state = smooth(None, window, presence_session_id=presence_session_id, user_id=user_id)
    assert state.observation_count == 1
    state = smooth(state, window, presence_session_id=presence_session_id, user_id=user_id)
    assert state.observation_count == 2
