"""Verifies `domain.addressee_fusion`'s exact weighted-sum formula and its
three-band outcome (design doc Sec4) -- a pure function, no Event Bus, no
fake perception source needed for these boundary/weighting assertions
(the "does a real subscribed event reach this function correctly" proof is
`tests/integration/test_addressee_signal_handler.py`'s job instead, using
`nova-testkit`'s `FakePerceptionSignalSource`)."""

from uuid import uuid4

import pytest
from nova_communication_engine.domain.addressee_fusion import (
    DEFAULT_WEIGHTS,
    FusionSignals,
    confidence_tier_label,
    corroborate_identity_confidence,
    fuse,
)

_NO_SIGNALS = FusionSignals(
    wake_word_matched=False,
    wake_word_confidence=0.0,
    identity_id=None,
    identity_confidence=0.0,
    gaze_toward_device=False,
    session_active=False,
)


def test_no_signals_scores_zero_and_stays_silent() -> None:
    outcome = fuse(_NO_SIGNALS)

    assert outcome.score == 0.0
    assert outcome.tier == "low"
    assert outcome.action == "silent"


def test_wake_word_gaze_and_active_session_reaches_exactly_the_high_threshold() -> None:
    # 0.35*1.0 (wake word) + 0.20 (gaze) + 0.15 (session_active) = 0.70
    signals = FusionSignals(
        wake_word_matched=True,
        wake_word_confidence=1.0,
        identity_id=None,
        identity_confidence=0.0,
        gaze_toward_device=True,
        session_active=True,
    )
    outcome = fuse(signals)

    assert outcome.score == pytest.approx(DEFAULT_WEIGHTS.high_threshold)
    assert outcome.tier == "high"
    assert outcome.action == "activated"


def test_every_signal_at_full_confidence_scores_the_maximum() -> None:
    signals = FusionSignals(
        wake_word_matched=True,
        wake_word_confidence=1.0,
        identity_id=uuid4(),
        identity_confidence=1.0,
        gaze_toward_device=True,
        session_active=True,
    )
    outcome = fuse(signals)

    assert outcome.score == pytest.approx(1.0)
    assert outcome.tier == "high"
    assert outcome.action == "activated"


def test_a_single_moderate_signal_lands_in_the_uncertain_band() -> None:
    # 0.35 * 0.6 (wake word) + 0.20 (gaze) = 0.41 -- comfortably between
    # low_threshold (0.35) and high_threshold (0.70), not at either boundary.
    signals = FusionSignals(
        wake_word_matched=True,
        wake_word_confidence=0.6,
        identity_id=None,
        identity_confidence=0.0,
        gaze_toward_device=True,
        session_active=False,
    )
    outcome = fuse(signals)

    assert DEFAULT_WEIGHTS.low_threshold <= outcome.score < DEFAULT_WEIGHTS.high_threshold
    assert outcome.tier == "uncertain"
    assert outcome.action == "clarify"


def test_score_exactly_at_the_low_threshold_is_uncertain_not_low() -> None:
    # gaze (0.20) + session_active (0.15) = 0.35, exactly low_threshold.
    signals = FusionSignals(
        wake_word_matched=False,
        wake_word_confidence=0.0,
        identity_id=None,
        identity_confidence=0.0,
        gaze_toward_device=True,
        session_active=True,
    )
    outcome = fuse(signals)

    assert outcome.score == pytest.approx(DEFAULT_WEIGHTS.low_threshold)
    assert outcome.tier == "uncertain"
    assert outcome.action == "clarify"


def test_identity_confidence_only_contributes_when_an_identity_id_is_present() -> None:
    # identity_confidence set but identity_id is None -- must not contribute.
    signals = FusionSignals(
        wake_word_matched=False,
        wake_word_confidence=0.0,
        identity_id=None,
        identity_confidence=1.0,
        gaze_toward_device=False,
        session_active=False,
    )
    outcome = fuse(signals)

    assert outcome.score == 0.0


def test_corroboration_boosts_confidence_when_world_model_confirms_the_same_identity() -> None:
    identity_id = uuid4()

    boosted = corroborate_identity_confidence(
        perception_confidence=0.5,
        identity_id=identity_id,
        world_model_present_identity_ids=frozenset({identity_id}),
    )

    assert boosted == 0.5 + (1.0 - 0.5) * 0.5


def test_corroboration_never_exceeds_certainty() -> None:
    identity_id = uuid4()

    boosted = corroborate_identity_confidence(
        perception_confidence=0.99,
        identity_id=identity_id,
        world_model_present_identity_ids=frozenset({identity_id}),
    )

    assert boosted <= 1.0


def test_corroboration_passes_through_unchanged_when_world_model_disagrees_or_has_no_opinion() -> (
    None
):
    identity_id = uuid4()
    other_identity_id = uuid4()

    disagreeing = corroborate_identity_confidence(
        perception_confidence=0.6,
        identity_id=identity_id,
        world_model_present_identity_ids=frozenset({other_identity_id}),
    )
    no_opinion = corroborate_identity_confidence(
        perception_confidence=0.6,
        identity_id=identity_id,
        world_model_present_identity_ids=frozenset(),
    )
    no_identity = corroborate_identity_confidence(
        perception_confidence=0.6,
        identity_id=None,
        world_model_present_identity_ids=frozenset({identity_id}),
    )

    assert disagreeing == 0.6
    assert no_opinion == 0.6
    assert no_identity == 0.6


def test_confidence_tier_label_maps_every_band() -> None:
    assert confidence_tier_label(0.95) == "high"
    assert confidence_tier_label(0.85) == "high"
    assert confidence_tier_label(0.7) == "medium"
    assert confidence_tier_label(0.6) == "medium"
    assert confidence_tier_label(0.5) == "low"
    assert confidence_tier_label(0.35) == "low"
    assert confidence_tier_label(0.1) == "unknown"
    assert confidence_tier_label(0.0) == "unknown"
