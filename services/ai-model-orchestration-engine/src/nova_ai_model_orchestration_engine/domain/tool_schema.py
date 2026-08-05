"""The Function Registry (Bible Part 7 "Function Calling"; design doc §0) --
schema *validation and normalization*, never a registry of what NOVA can do.
`ToolSchema` (already JSON-Schema-based, per `domain/models.py`) is the
provider-agnostic shape every connector formats into its own wire format;
this module is where the one piece of genuinely shared, provider-independent
logic lives -- validating a request's tool schemas are well-formed before any
connector-specific formatting happens, and parsing a tool call's arguments back
out uniformly regardless of whether a given provider handed them back as a JSON
string or an already-parsed object.
"""

from __future__ import annotations

import json
from typing import Any

from nova_ai_model_orchestration_engine.domain.models import ToolSchema

__all__ = ["InvalidToolSchemaError", "parse_tool_arguments", "validate_tool_schemas"]


class InvalidToolSchemaError(ValueError):
    pass


def validate_tool_schemas(tools: list[ToolSchema]) -> None:
    """Raises `InvalidToolSchemaError` for duplicate names or a
    `parameters_json_schema` missing the `"type": "object"` shape every
    provider's tool-calling convention expects at the top level. Called once,
    by `domain/router.py`, before any connector sees the request -- so every
    connector can assume the tool schemas it receives are already well-formed,
    rather than each one re-validating independently (ADR-023: no
    provider-specific behavior, including validation gaps, should leak)."""
    seen: set[str] = set()
    for tool in tools:
        if tool.name in seen:
            raise InvalidToolSchemaError(f"Duplicate tool name: {tool.name!r}")
        seen.add(tool.name)
        if tool.parameters_json_schema.get("type") != "object":
            raise InvalidToolSchemaError(
                f"Tool {tool.name!r}: parameters_json_schema must be a top-level "
                f"JSON Schema object (\"type\": \"object\")."
            )


def parse_tool_arguments(raw: str | dict[str, Any]) -> dict[str, Any]:
    """Normalizes a tool call's arguments, which arrive as a JSON string from
    some providers and an already-parsed object from others, into one shape
    every caller can rely on."""
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InvalidToolSchemaError(f"Malformed tool call arguments: {raw!r}") from exc
    if not isinstance(parsed, dict):
        raise InvalidToolSchemaError(f"Tool call arguments must be a JSON object: {raw!r}")
    return parsed
