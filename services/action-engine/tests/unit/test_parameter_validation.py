"""`domain.parameter_validation.validate_parameters` -- stage 5's deep
`Action.parameters` vs. `Capability.input_schema` check (approved §5.2's
stage-5 half, implemented 2026-08-18 to close the gap the Phase 3D
documentation and project-state synchronization pass found). Covers
valid/invalid parameters, missing required fields, wrong types, nested
structures, and malformed schemas -- the exact coverage the closure
instruction asked for."""

from __future__ import annotations

from nova_action_engine.domain.parameter_validation import validate_parameters

_GENERIC_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "operation": {"type": "string"},
        "parameters": {"type": "object"},
    },
    "required": ["operation"],
}


def test_valid_parameters_pass_the_generic_schema() -> None:
    assert (
        validate_parameters(
            {"operation": "read", "path": "/tmp/note.txt"},
            input_schema=_GENERIC_INPUT_SCHEMA,
        )
        is None
    )


def test_missing_required_field_fails() -> None:
    error = validate_parameters({"path": "/tmp/note.txt"}, input_schema=_GENERIC_INPUT_SCHEMA)
    assert error is not None
    assert "operation" in error


def test_wrong_type_for_a_declared_property_fails() -> None:
    schema = {
        "type": "object",
        "properties": {"operation": {"type": "string"}, "retries": {"type": "integer"}},
        "required": ["operation"],
    }
    error = validate_parameters(
        {"operation": "write", "retries": "three"}, input_schema=schema
    )
    assert error is not None
    assert "retries" in error


def test_root_type_mismatch_fails() -> None:
    """`parameters` itself isn't even an object -- a degenerate case a
    caller's own bug could produce (e.g. a list slipped through)."""
    error = validate_parameters([], input_schema=_GENERIC_INPUT_SCHEMA)  # type: ignore[arg-type]
    assert error is not None
    assert "is not of type" in error


def test_nested_structure_valid_case_passes() -> None:
    schema = {
        "type": "object",
        "properties": {
            "operation": {"type": "string"},
            "target": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "permissions": {
                        "type": "object",
                        "properties": {"mode": {"type": "integer"}},
                        "required": ["mode"],
                    },
                },
                "required": ["path", "permissions"],
            },
        },
        "required": ["operation", "target"],
    }
    parameters = {
        "operation": "write",
        "target": {"path": "/tmp/note.txt", "permissions": {"mode": 0o644}},
    }
    assert validate_parameters(parameters, input_schema=schema) is None


def test_nested_structure_invalid_deep_field_fails_with_a_path() -> None:
    schema = {
        "type": "object",
        "properties": {
            "operation": {"type": "string"},
            "target": {
                "type": "object",
                "properties": {
                    "permissions": {
                        "type": "object",
                        "properties": {"mode": {"type": "integer"}},
                        "required": ["mode"],
                    },
                },
                "required": ["permissions"],
            },
        },
        "required": ["operation", "target"],
    }
    parameters = {
        "operation": "write",
        "target": {"permissions": {"mode": "not-an-integer"}},
    }
    error = validate_parameters(parameters, input_schema=schema)
    assert error is not None
    assert "target" in error
    assert "permissions" in error
    assert "mode" in error


def test_array_item_type_mismatch_in_a_nested_list_fails() -> None:
    schema = {
        "type": "object",
        "properties": {
            "operation": {"type": "string"},
            "paths": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["operation"],
    }
    error = validate_parameters(
        {"operation": "list", "paths": ["/tmp/a", 42, "/tmp/c"]}, input_schema=schema
    )
    assert error is not None
    assert "paths" in error


def test_additional_properties_are_allowed_by_default() -> None:
    """JSON Schema's own default (`additionalProperties` unset means
    `true`) -- an adapter-specific extra key (e.g. `content` on a
    `filesystem` write) must not be rejected just because the generic
    schema doesn't name it."""
    assert (
        validate_parameters(
            {"operation": "write", "path": "/tmp/note.txt", "content": "hello"},
            input_schema=_GENERIC_INPUT_SCHEMA,
        )
        is None
    )


def test_malformed_schema_itself_is_reported_distinctly_from_invalid_parameters() -> None:
    """A capability's own `input_schema` can be malformed (not a valid
    JSON Schema document) -- e.g. `type` given a value outside the JSON
    Schema vocabulary. This is `capability-engine`'s own registration-time
    data-quality problem, not a caller parameter error, so the message is
    distinguishable."""
    malformed_schema = {"type": "not-a-real-json-schema-type"}
    error = validate_parameters({"operation": "read"}, input_schema=malformed_schema)
    assert error is not None
    assert "malformed" in error


def test_malformed_schema_with_wrong_shaped_properties_is_reported() -> None:
    malformed_schema = {"type": "object", "properties": "should-be-a-mapping-not-a-string"}
    error = validate_parameters({"operation": "read"}, input_schema=malformed_schema)
    assert error is not None
    assert "malformed" in error


def test_empty_schema_accepts_any_parameters() -> None:
    """An empty JSON Schema (`{}`) is a legal, maximally-permissive
    schema -- distinct from a malformed one; must not be misreported."""
    assert validate_parameters({"anything": "goes", "here": 1}, input_schema={}) is None
