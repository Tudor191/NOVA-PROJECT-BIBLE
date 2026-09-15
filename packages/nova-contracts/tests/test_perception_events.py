"""Perception payload contracts, and Phase 4F.2's new one in particular.

The seven Phase 2D payloads are registrations of an existing wire shape;
`PerceptionWorkspaceObservedPayload` is the first perception contract designed
before its producer, so it gets the closer reading here.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from nova_contracts import PerceptionWorkspaceObservedPayload
from nova_contracts.registry import known_subjects, payload_model_for, validate_payload
from pydantic import ValidationError

SUBJECT = "perception.workspace.observed"


def _payload(**overrides: object) -> dict:
    base: dict = {
        "object_id": "ws-" + "a" * 64,
        "label": "quarterly-report.md",
        "user_id": str(uuid4()),
        "object_type": "project",
        "sensor_id": "companion-filesystem",
        "observed_at": datetime.now(UTC).isoformat(),
    }
    base.update(overrides)
    return base


def test_the_subject_is_registered_and_resolves_to_the_payload() -> None:
    """§20.2 requirement 10 -- registry round trip."""
    assert SUBJECT in known_subjects()
    assert payload_model_for(SUBJECT) is PerceptionWorkspaceObservedPayload


def test_a_well_formed_observation_validates_through_the_registry() -> None:
    validated = validate_payload(SUBJECT, _payload())
    assert isinstance(validated, PerceptionWorkspaceObservedPayload)


def test_all_seven_ratified_fields_are_present() -> None:
    """The ratified contract, field for field. A future edit that drops one
    fails here rather than at a consumer."""
    fields = PerceptionWorkspaceObservedPayload.model_fields
    for name in (
        "object_id",
        "label",
        "user_id",
        "object_type",
        "project_id",
        "sensor_id",
        "observed_at",
    ):
        assert name in fields, f"ratified field {name!r} is missing"


def test_the_schema_version_invariant_holds() -> None:
    """ADR-024. Every registered payload in the repository carries
    `schema_version`; this one was ratified as compliance with that
    invariant rather than as an eighth workspace field."""
    assert PerceptionWorkspaceObservedPayload.model_fields["schema_version"].default == 1
    assert validate_payload(SUBJECT, _payload()).schema_version == 1


def test_the_payload_carries_exactly_the_ratified_fields_and_nothing_more() -> None:
    """A guard on the *size* of the contract. "Do not add fields merely
    because they seem useful" is only enforceable if something counts."""
    assert set(PerceptionWorkspaceObservedPayload.model_fields) == {
        "object_id",
        "label",
        "user_id",
        "object_type",
        "project_id",
        "sensor_id",
        "observed_at",
        "schema_version",
    }


@pytest.mark.parametrize("missing", ["object_id", "label", "user_id", "sensor_id", "observed_at"])
def test_every_required_field_is_actually_required(missing: str) -> None:
    payload = _payload()
    del payload[missing]
    with pytest.raises(ValidationError):
        validate_payload(SUBJECT, payload)


def test_object_type_is_a_closed_literal() -> None:
    """*"The payload must remain closed to `object_type="project"`. Do not
    silently broaden it to arbitrary object types."* Broadening it should
    take a contract change and a failing test, not a passing one."""
    for rejected in ("window", "file", "document", "Project", ""):
        with pytest.raises(ValidationError):
            validate_payload(SUBJECT, _payload(object_type=rejected))


def test_project_id_is_optional_and_defaults_to_none() -> None:
    """§9: a failed correlation publishes **without** a `project_id`. The
    field must therefore be omissible, and its absence must mean "unknown"
    rather than raise."""
    assert validate_payload(SUBJECT, _payload()).project_id is None


def test_project_id_round_trips_when_correlation_succeeds() -> None:
    project_id = uuid4()
    validated = validate_payload(SUBJECT, _payload(project_id=str(project_id)))
    assert validated.project_id == project_id


def test_observed_at_keeps_its_timezone() -> None:
    """AC-7 measures an interval that starts at this timestamp. A naive
    datetime would silently be read as server-local time and make that
    interval wrong by the UTC offset."""
    moment = datetime.now(UTC) - timedelta(minutes=5)
    validated = validate_payload(SUBJECT, _payload(observed_at=moment.isoformat()))
    assert validated.observed_at.tzinfo is not None
    assert validated.observed_at == moment


def test_the_consumer_reads_the_three_fields_this_payload_supplies() -> None:
    """The contract's whole reason for existing (§20.2 requirement 5).

    `world-model-engine`'s object handler reads `object_id`, `label` and
    `user_id`. This asserts the payload serializes all three under exactly
    those names -- the handler looks them up by string key, so a rename
    would leave it skipping every event with only a log line.
    """
    wire = validate_payload(SUBJECT, _payload()).model_dump(mode="json")
    for key in ("object_id", "label", "user_id"):
        assert isinstance(wire[key], str) and wire[key].strip()


def test_no_existing_perception_payload_could_have_carried_this() -> None:
    """§20.2 requirement 5, evidenced rather than asserted in prose.

    Every other perception payload is identity- or sensor-shaped. If any of
    them grew the object fields, this subject would be redundant and that
    should be a decision, not a coincidence.
    """
    from nova_contracts.events import perception as module

    object_fields = {"object_id", "entity_id", "object_label"}
    for name in dir(module):
        model = getattr(module, name)
        fields = getattr(model, "model_fields", None)
        if not isinstance(fields, dict) or name == "PerceptionWorkspaceObservedPayload":
            continue
        assert not (object_fields & set(fields)), f"{name} unexpectedly carries object fields"
