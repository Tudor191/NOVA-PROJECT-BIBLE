"""`DomainModel`'s invariants -- TDD 4E Sec14.5 controls 5 and 10, as a type.

Part 16 Sec69's *"Never create assumptions without evidence"* is the one rule
Phase 4E cannot break. A test can only observe that a particular derivation
happened not to break it; `DomainModel`'s validators make the broken state
**unconstructible**, so a future derivation bug raises instead of rendering.

This file asserts the validators themselves. Each case constructs the state the
rule forbids and requires a `ValidationError` -- which is also the mutation
evidence: delete a validator and a named test here fails immediately, rather than
the property silently becoming a comment.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from nova_digital_twin_engine.domain.models import (
    DomainModel,
    DomainReason,
    DomainReasonCode,
    DomainState,
    ProjectModel,
    TwinDomain,
)
from pydantic import ValidationError

USER = uuid4()

_REASON = DomainReason(code=DomainReasonCode.NO_EVIDENCE_OBSERVED, detail="nothing yet")


def test_populated_with_zero_evidence_rows_is_unconstructible() -> None:
    """**Control 5.** The single claim Part 16 forbids."""
    with pytest.raises(ValidationError, match="zero evidence rows"):
        DomainModel(
            user_id=USER,
            domain=TwinDomain.GOALS,
            state=DomainState.POPULATED,
            evidence_count=0,
        )


def test_a_non_populated_state_without_a_reason_is_unconstructible() -> None:
    """**Control 10.** Every `partially_populated`, `empty` and `unavailable`
    carries an enumerated code, so the panel can branch and a test can assert."""
    for state in (DomainState.EMPTY, DomainState.UNAVAILABLE, DomainState.PARTIALLY_POPULATED):
        with pytest.raises(ValidationError, match="machine-readable"):
            DomainModel(
                user_id=USER, domain=TwinDomain.GOALS, state=state, evidence_count=1
            )


def test_populated_with_a_reason_is_unconstructible() -> None:
    """A reason explains an absence. A populated domain has none to explain, and
    carrying one would let a domain look both derived and excused."""
    with pytest.raises(ValidationError, match="still carries a reason"):
        DomainModel(
            user_id=USER,
            domain=TwinDomain.GOALS,
            state=DomainState.POPULATED,
            reason=_REASON,
            evidence_count=4,
        )


def test_partially_populated_without_naming_the_missing_fields_is_unconstructible() -> None:
    with pytest.raises(ValidationError, match="which fields are unavailable"):
        DomainModel(
            user_id=USER,
            domain=TwinDomain.KNOWLEDGE_PROFILE,
            state=DomainState.PARTIALLY_POPULATED,
            reason=DomainReason(code=DomainReasonCode.EVIDENCE_PARTIAL, detail="some"),
            evidence_count=2,
        )


def test_partially_populated_with_zero_evidence_is_unconstructible() -> None:
    """That state is `empty`. Calling it partial overstates what is known."""
    with pytest.raises(ValidationError, match="zero evidence"):
        DomainModel(
            user_id=USER,
            domain=TwinDomain.SKILL_PROFILE,
            state=DomainState.PARTIALLY_POPULATED,
            reason=DomainReason(code=DomainReasonCode.EVIDENCE_PARTIAL, detail="some"),
            evidence_count=0,
            unavailable_fields=["named_skills"],
        )


def test_an_empty_domain_carrying_derived_facts_is_unconstructible() -> None:
    """A domain reporting nothing must render nothing -- not a zero, not an
    average, not a default."""
    with pytest.raises(ValidationError, match="still carries derived"):
        DomainModel(
            user_id=USER,
            domain=TwinDomain.GOALS,
            state=DomainState.EMPTY,
            reason=_REASON,
            evidence_count=0,
            facts={"decision_count": 0},
        )


#: Each above-the-floor state, built so it satisfies the *evidence* validator --
#: otherwise that one fires first and the floor rule is never reached, and the
#: test would pass while proving something else entirely.
_ABOVE_THE_FLOOR: list[dict[str, object]] = [
    {"state": DomainState.POPULATED, "evidence_count": 3},
    {
        "state": DomainState.PARTIALLY_POPULATED,
        "evidence_count": 3,
        "reason": DomainReason(code=DomainReasonCode.EVIDENCE_PARTIAL, detail="x"),
        "unavailable_fields": ["cpu"],
    },
]


@pytest.mark.parametrize(
    "domain", [TwinDomain.SOFTWARE_ENVIRONMENT, TwinDomain.HARDWARE_ENVIRONMENT]
)
@pytest.mark.parametrize("above_the_floor", _ABOVE_THE_FLOOR, ids=["populated", "partial"])
def test_the_4f_domains_cannot_be_constructed_above_the_ratified_floor(
    domain: TwinDomain, above_the_floor: dict[str, object]
) -> None:
    """Ratified Sec19.1: `empty` or `unavailable` only, until a real Phase 4F
    source exists. Anything else would be fabricated data, so the type refuses it
    regardless of what a derivation tried to produce."""
    with pytest.raises(ValidationError, match="ratified floor permits only empty"):
        DomainModel(user_id=USER, domain=domain, **above_the_floor)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "domain", [TwinDomain.KNOWLEDGE_PROFILE, TwinDomain.SKILL_PROFILE]
)
def test_the_partial_domains_cannot_be_constructed_as_populated(
    domain: TwinDomain,
) -> None:
    with pytest.raises(ValidationError, match="partially_populated at most"):
        DomainModel(
            user_id=USER, domain=domain, state=DomainState.POPULATED, evidence_count=9
        )


def test_the_floor_still_permits_what_it_was_ratified_to_permit() -> None:
    """Anti-vacuity: the validators above must forbid the forbidden without also
    forbidding the allowed, or every test here would pass on a model that can
    represent nothing at all."""
    assert (
        DomainModel(
            user_id=USER,
            domain=TwinDomain.SOFTWARE_ENVIRONMENT,
            state=DomainState.EMPTY,
            reason=DomainReason(code=DomainReasonCode.NO_SOURCE_ENGINE, detail="4F"),
        ).state
        is DomainState.EMPTY
    )
    assert (
        DomainModel(
            user_id=USER,
            domain=TwinDomain.SKILL_PROFILE,
            state=DomainState.PARTIALLY_POPULATED,
            reason=DomainReason(code=DomainReasonCode.EVIDENCE_PARTIAL, detail="some"),
            evidence_count=2,
            unavailable_fields=["named_skills"],
        ).evidence_count
        == 2
    )
    assert (
        DomainModel(
            user_id=USER,
            domain=TwinDomain.PROJECTS,
            state=DomainState.POPULATED,
            evidence_count=5,
            facts={"project_count": 2},
        ).state
        is DomainState.POPULATED
    )


# --- ProjectModel -----------------------------------------------------------


def test_a_project_with_no_memories_cannot_carry_activity_timestamps() -> None:
    with pytest.raises(ValidationError, match="no memories cannot have activity"):
        ProjectModel(
            user_id=USER,
            project_id=uuid4(),
            memory_count=0,
            last_activity_at=__import__("datetime").datetime.now(
                __import__("datetime").UTC
            ),
        )


def test_a_project_cannot_have_first_activity_after_last() -> None:
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    with pytest.raises(ValidationError, match="after last_activity_at"):
        ProjectModel(
            user_id=USER,
            project_id=uuid4(),
            memory_count=2,
            first_activity_at=now,
            last_activity_at=now - timedelta(days=1),
        )


def test_gap_days_cannot_be_negative() -> None:
    """A gap is elapsed time. A negative one would mean the newest activity is in
    the future, which is a derivation bug rather than a renderable number."""
    with pytest.raises(ValidationError):
        ProjectModel(user_id=USER, project_id=uuid4(), memory_count=1, gap_days=-1.0)
