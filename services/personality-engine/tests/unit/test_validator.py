"""`domain.validator.validate` (docs/design/phase-2d/02-personality-engine.md
Sec4, Sec8) -- one test per check family, plus the hard-stop/soft-correction
split Sec8 specifies."""

from __future__ import annotations

import pytest
from nova_personality_engine.domain.models import ConfidenceTier, ViolationCheckFamily
from nova_personality_engine.domain.validator import validate


def test_clean_content_passes_with_no_violations() -> None:
    result = validate("The build finished successfully.", confidence_tier=ConfidenceTier.HIGH)
    assert result.passed is True
    assert result.adjusted_content is None
    assert result.violations == []


@pytest.mark.parametrize("confidence_tier", [ConfidenceTier.LOW, ConfidenceTier.UNKNOWN])
def test_overclaiming_language_is_hedged_under_low_or_unknown_confidence(
    confidence_tier: ConfidenceTier,
) -> None:
    result = validate("This will definitely work, no question.", confidence_tier=confidence_tier)
    assert result.passed is True
    assert result.adjusted_content is not None
    assert result.adjusted_content.startswith("I'm not fully certain")
    assert result.violations[0].check_family == ViolationCheckFamily.CONFIDENCE_LANGUAGE


@pytest.mark.parametrize("confidence_tier", [ConfidenceTier.MEDIUM, ConfidenceTier.HIGH])
def test_overclaiming_language_is_not_flagged_under_medium_or_high_confidence(
    confidence_tier: ConfidenceTier,
) -> None:
    result = validate("This will definitely work.", confidence_tier=confidence_tier)
    assert result.passed is True
    assert result.adjusted_content is None
    assert result.violations == []


@pytest.mark.parametrize(
    "content",
    [
        "Act now, don't wait.",
        "You should feel bad about this, it's your fault.",
        "I understand exactly how you feel.",
    ],
)
def test_forbidden_patterns_hard_stop(content: str) -> None:
    result = validate(content, confidence_tier=ConfidenceTier.UNKNOWN)
    assert result.passed is False
    assert result.adjusted_content is None
    assert result.violations[0].check_family == ViolationCheckFamily.FORBIDDEN_PATTERN


@pytest.mark.parametrize(
    "content",
    [
        "Obviously, clearly you didn't read the docs.",
        "That's not my fault, I never said that.",
    ],
)
def test_emotional_instability_hard_stops(content: str) -> None:
    result = validate(content, confidence_tier=ConfidenceTier.UNKNOWN)
    assert result.passed is False
    assert result.adjusted_content is None
    assert result.violations[0].check_family == ViolationCheckFamily.EMOTIONAL_STABILITY


def test_hard_stop_violations_short_circuit_soft_corrections() -> None:
    # Shouting *and* a forbidden pattern in the same content: the hard stop
    # wins outright, per Sec8 -- no adjusted_content is ever produced.
    result = validate(
        "ACT NOW, don't wait, before it's too late!!!", confidence_tier=ConfidenceTier.UNKNOWN
    )
    assert result.passed is False
    assert result.adjusted_content is None
    assert all(
        v.check_family == ViolationCheckFamily.FORBIDDEN_PATTERN for v in result.violations
    )


@pytest.mark.parametrize(
    "content",
    ["This is REALLY IMPORTANT.", "Great job!!!"],
)
def test_professionalism_floor_soft_corrects_shouting(content: str) -> None:
    result = validate(content, confidence_tier=ConfidenceTier.HIGH)
    assert result.passed is True
    assert result.adjusted_content is not None
    assert result.adjusted_content != content
    assert result.violations[0].check_family == ViolationCheckFamily.PROFESSIONALISM_FLOOR


def test_professionalism_floor_leaves_short_acronyms_alone() -> None:
    # Sec4's pattern only fires on all-caps *words* of 4+ letters -- short,
    # legitimate acronyms (API, TDD) must not be mistaken for shouting.
    result = validate("The API call succeeded.", confidence_tier=ConfidenceTier.HIGH)
    assert result.passed is True
    assert result.adjusted_content is None
    assert result.violations == []
