"""`domain.clarification` (design doc Sec5.1/Sec6) -- templated-only
output, never generated text."""

from __future__ import annotations

from nova_communication_engine.domain.clarification import (
    ADDRESSEE_CHECK_IN_CUE,
    RESUME_OFFER_FALLBACK,
    resume_offer,
)


def test_addressee_check_in_cue_is_a_fixed_short_string() -> None:
    assert ADDRESSEE_CHECK_IN_CUE == "Yes?"


def test_resume_offer_references_the_recorded_objective() -> None:
    assert resume_offer(objective="the deployment plan") == (
        "the deployment plan -- want me to continue?"
    )


def test_resume_offer_falls_back_when_no_objective_is_recorded() -> None:
    assert resume_offer(objective=None) == RESUME_OFFER_FALLBACK
    assert resume_offer(objective="") == RESUME_OFFER_FALLBACK
