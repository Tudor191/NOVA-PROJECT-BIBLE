"""Round-trip serialization for `Capability`/`CapabilityHandle` and the 4
new `capability.resolve.*`/`capability.invoke.*` RPC payloads, plus
subject registration (`nova_contracts.registry`) -- mirrors every other
engine's own `tests/contract/` convention."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from nova_contracts import (
    Capability,
    CapabilityHandle,
    CapabilityInvokeReplyPayload,
    CapabilityInvokeRequestPayload,
    CapabilityResolveReplyPayload,
    CapabilityResolveRequestPayload,
)
from nova_contracts.registry import known_subjects, payload_model_for
from pydantic import ValidationError


def _capability(**overrides: object) -> Capability:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "name": "filesystem",
        "description": "Read, write, and list files within a declared root.",
        "category": "filesystem",
        "version": "1.0.0",
        "required_permissions": ["filesystem:read", "filesystem:write"],
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "execution_adapter": "filesystem",
        "health_status": "healthy",
        "installed_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Capability(**defaults)  # type: ignore[arg-type]


def test_capability_round_trips_through_json() -> None:
    capability = _capability()
    restored = Capability.model_validate_json(capability.model_dump_json())
    assert restored == capability


def test_capability_handle_round_trips_through_json() -> None:
    handle = CapabilityHandle(capability_id=uuid4(), name="git", execution_adapter="git")
    restored = CapabilityHandle.model_validate_json(handle.model_dump_json())
    assert restored == handle


def test_resolve_request_and_reply_round_trip() -> None:
    request = CapabilityResolveRequestPayload(
        capability_id=uuid4(), requesting_engine="action-engine", correlation_id=uuid4()
    )
    assert (
        CapabilityResolveRequestPayload.model_validate_json(request.model_dump_json()) == request
    )

    found_reply = CapabilityResolveReplyPayload(found=True, capability=_capability())
    assert (
        CapabilityResolveReplyPayload.model_validate_json(found_reply.model_dump_json())
        == found_reply
    )

    not_found_reply = CapabilityResolveReplyPayload(found=False)
    assert not_found_reply.capability is None


def test_resolve_request_by_name_round_trips() -> None:
    """Additive extension, approved
    (docs/design/phase-3/13-3d-action-engine-research.md §5.1) --
    `action-engine`'s `CapabilityPort` resolves by stable capability
    `name`, never by a `capability_id` it has no way to know in advance."""
    request = CapabilityResolveRequestPayload(
        name="git", requesting_engine="action-engine", correlation_id=uuid4()
    )
    assert request.capability_id is None
    restored = CapabilityResolveRequestPayload.model_validate_json(request.model_dump_json())
    assert restored == request


def test_resolve_request_requires_exactly_one_of_capability_id_or_name() -> None:
    with pytest.raises(ValidationError):
        CapabilityResolveRequestPayload(requesting_engine="x", correlation_id=uuid4())
    with pytest.raises(ValidationError):
        CapabilityResolveRequestPayload(
            capability_id=uuid4(), name="git", requesting_engine="x", correlation_id=uuid4()
        )


def test_invoke_request_and_reply_round_trip() -> None:
    request = CapabilityInvokeRequestPayload(
        capability_id=uuid4(),
        operation="read",
        parameters={"path": "/workspace/note.txt"},
        requesting_engine="action-engine",
        correlation_id=uuid4(),
    )
    assert (
        CapabilityInvokeRequestPayload.model_validate_json(request.model_dump_json()) == request
    )

    success_reply = CapabilityInvokeReplyPayload(outcome="success", result={"content": "hi"})
    assert (
        CapabilityInvokeReplyPayload.model_validate_json(success_reply.model_dump_json())
        == success_reply
    )

    violation_reply = CapabilityInvokeReplyPayload(
        outcome="sandbox_violation", error="path outside declared root"
    )
    assert violation_reply.result is None


def test_every_capability_subject_is_registered() -> None:
    subjects = known_subjects()
    assert "capability.resolve.request" in subjects
    assert "capability.resolve.reply" in subjects
    assert "capability.invoke.request" in subjects
    assert "capability.invoke.reply" in subjects

    assert payload_model_for("capability.resolve.request") is CapabilityResolveRequestPayload
    assert payload_model_for("capability.resolve.reply") is CapabilityResolveReplyPayload
    assert payload_model_for("capability.invoke.request") is CapabilityInvokeRequestPayload
    assert payload_model_for("capability.invoke.reply") is CapabilityInvokeReplyPayload


def test_every_new_payload_carries_a_schema_version() -> None:
    assert CapabilityResolveRequestPayload(
        capability_id=uuid4(), requesting_engine="x", correlation_id=uuid4()
    ).schema_version == 1
    assert CapabilityResolveReplyPayload(found=False).schema_version == 1
    assert (
        CapabilityInvokeRequestPayload(
            capability_id=uuid4(),
            operation="read",
            requesting_engine="x",
            correlation_id=uuid4(),
        ).schema_version
        == 1
    )
    assert CapabilityInvokeReplyPayload(outcome="failure", error="x").schema_version == 1
