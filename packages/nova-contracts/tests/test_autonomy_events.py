"""`events/autonomy.py` -- Phase 4F.6, TDD 4F.6 §3, §4.6, §5 and §19.

The contract is where two of 4F.6's security properties live, so they are
asserted here rather than only in the engines that use it: the producer
**cannot** name a decision's identity, and it **cannot** name a user.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from nova_contracts import (
    AutonomyDecisionReplyPayload,
    AutonomyDecisionRequestedPayload,
    PermissionCategory,
    RiskLevel,
    known_subjects,
    validate_payload,
)
from nova_contracts.registry import payload_model_for
from pydantic import ValidationError

SUBJECT = "autonomy.decision.requested"


def _fields(**overrides: object) -> dict:
    fields: dict = {
        "thought_id": str(uuid4()),
        "category": "create",
        "risk": "low",
        "action_type": "filesystem",
        "execution_target": "filesystem",
        "verification_method": "none",
        "title": "rotate the scratch directory",
        "requesting_engine": "cognitive-state-engine",
        "correlation_id": str(uuid4()),
    }
    fields.update(overrides)
    return fields


# --- registration ------------------------------------------------------------


def test_the_trigger_subject_is_registered() -> None:
    assert SUBJECT in known_subjects()
    assert payload_model_for(SUBJECT) is AutonomyDecisionRequestedPayload


def test_it_is_the_only_autonomy_subject() -> None:
    """**TDD 4F D-4F-9**: exactly one `autonomy.*` subject exists. §11.4's
    prohibition is amended for this one internal subject and no other."""
    assert sorted(s for s in known_subjects() if s.startswith("autonomy.")) == [SUBJECT]


def test_the_registry_holds_exactly_one_hundred_and_twenty_subjects() -> None:
    """**Ratified: 119 → 120.** Pinned so an accidental second subject -- most
    plausibly a registered reply -- fails here rather than in review."""
    assert len(known_subjects()) == 120


def test_the_reply_is_not_a_registered_subject() -> None:
    """**Deliberate, and disclosed as an open finding.** Every other
    request/reply pair registers its reply; the ratified count of 120 leaves no
    room for one here. The reply travels on NATS's ephemeral inbox, so nothing
    needs it registered -- this test pins that it is not."""
    registered = {payload_model_for(s) for s in known_subjects()}
    assert AutonomyDecisionReplyPayload not in registered


def test_autonomy_approval_subjects_stay_unclaimed() -> None:
    """`events/action.py` reserves `autonomy.approval.requested` and
    `autonomy.decision.made` for autonomy-engine to claim; 4F.6 claims neither."""
    assert "autonomy.approval.requested" not in known_subjects()
    assert "autonomy.decision.made" not in known_subjects()


# --- the two absent fields ----------------------------------------------------


def test_the_payload_has_no_subject_id_field() -> None:
    """**A-4F6-3.** The consumer derives the decision identity from
    `envelope.event_id`. A field here would let a producer name it."""
    assert "subject_id" not in AutonomyDecisionRequestedPayload.model_fields


def test_a_producer_supplied_subject_id_is_rejected() -> None:
    """Not dropped and carried on -- **rejected**. A producer that tries to name
    a decision's identity gets a validation error, so the consumer never reaches
    `decide()` with it."""
    with pytest.raises(ValidationError):
        AutonomyDecisionRequestedPayload.model_validate(_fields(subject_id=str(uuid4())))


def test_the_payload_has_no_user_id_field() -> None:
    """**TDD 4F §12.** Identity is resolved server-side from `primary_user_id`;
    a caller-supplied `user_id` is a privilege-escalation surface."""
    assert "user_id" not in AutonomyDecisionRequestedPayload.model_fields


def test_a_producer_supplied_user_id_is_rejected() -> None:
    """**TDD 4F.6 §9**: *"Producer-supplied `user_id` -- **Rejected**."*"""
    with pytest.raises(ValidationError):
        AutonomyDecisionRequestedPayload.model_validate(_fields(user_id=str(uuid4())))


def test_any_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        validate_payload(SUBJECT, _fields(level=2))


# --- validation at the boundary ----------------------------------------------


def test_a_complete_payload_validates_through_the_registry() -> None:
    payload = validate_payload(SUBJECT, _fields())
    assert isinstance(payload, AutonomyDecisionRequestedPayload)
    assert payload.category is PermissionCategory.CREATE
    assert payload.risk is RiskLevel.LOW


@pytest.mark.parametrize(
    "missing",
    ["category", "risk", "action_type", "execution_target", "verification_method", "title"],
)
def test_every_required_field_is_required(missing: str) -> None:
    """All six are required. None is defaulted, because a default would be a
    guess about what the thought proposed."""
    fields = _fields()
    del fields[missing]
    with pytest.raises(ValidationError):
        AutonomyDecisionRequestedPayload.model_validate(fields)


@pytest.mark.parametrize("field", ["execution_target", "verification_method", "title"])
def test_required_strings_may_not_be_empty(field: str) -> None:
    with pytest.raises(ValidationError):
        AutonomyDecisionRequestedPayload.model_validate(_fields(**{field: ""}))


def test_an_action_type_action_engine_cannot_run_is_rejected_here() -> None:
    """`action.execute` accepts only `terminal`/`filesystem`. Rejecting anything
    else at the contract means it never reaches dispatch."""
    with pytest.raises(ValidationError):
        AutonomyDecisionRequestedPayload.model_validate(_fields(action_type="deploy"))


def test_an_unknown_category_is_rejected_rather_than_coerced() -> None:
    with pytest.raises(ValidationError):
        AutonomyDecisionRequestedPayload.model_validate(_fields(category="administer"))


def test_detail_is_the_only_optional_authored_field() -> None:
    payload = AutonomyDecisionRequestedPayload.model_validate(_fields())
    assert payload.detail == ""


# --- PermissionCategory -------------------------------------------------------


def test_permission_category_is_bible_part_fourteens_ten_in_order() -> None:
    assert [c.value for c in PermissionCategory] == [
        "read",
        "analyze",
        "recommend",
        "create",
        "modify",
        "delete",
        "execute",
        "deploy",
        "purchase",
        "communicate",
    ]


def test_permission_category_serializes_as_its_plain_string() -> None:
    """The wire form is the value, so moving the enum changed nothing on the
    wire, in the `permission_grant.category` TEXT column, or in the API."""
    payload = AutonomyDecisionRequestedPayload.model_validate(_fields(category="delete"))
    assert payload.model_dump(mode="json")["category"] == "delete"


# --- the reply ------------------------------------------------------------------


def test_a_degraded_reply_carries_no_outcome_or_identity() -> None:
    reply = AutonomyDecisionReplyPayload(degraded=True, error="boom")
    assert reply.outcome is None
    assert reply.subject_id is None
    assert reply.rejected is False


def test_rejected_is_off_unless_said() -> None:
    """A decided reply must not read as a rejection by default."""
    assert AutonomyDecisionReplyPayload(degraded=False, outcome="propose").rejected is False
