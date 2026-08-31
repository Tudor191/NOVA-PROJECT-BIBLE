"""Deep parameter-shape validation for stage 5 ("Prepare Resources"),
resolving the gap the Phase 3D documentation and project-state
synchronization pass (2026-08-18) found: approved decision §5.2
(`docs/design/phase-3/13-3d-action-engine-research.md`) requires stage 5
to validate `Action.parameters` against the resolved `Capability.input_schema`
before proceeding to stage 6 ("Execute") -- "performs `jsonschema`-style
validation ... of `Action.parameters` against the resolved
`Capability.input_schema` dict."

`Capability.input_schema` is populated with genuine JSON Schema vocabulary
(`type`/`properties`/`required` -- see
`services/capability-engine/.../domain/builtin_capabilities.py`'s
`_GENERIC_INPUT_SCHEMA`), so this module validates literally against the
JSON Schema specification via the `jsonschema` library -- the standard,
reference implementation `"jsonschema"-style` names, not a bespoke
validator reinventing JSON Schema semantics. Pure, framework-free,
no I/O (same discipline as `domain/risk.py`): takes plain dicts in,
returns a plain `str | None` out.

A capability's own `input_schema` can itself be malformed (not a valid
JSON Schema document) -- distinguished from an invalid `parameters` dict,
since the two have different owners and different remediation paths (a
malformed schema is `capability-engine`'s registration-time data quality;
invalid parameters are the caller's request)."""

from __future__ import annotations

import jsonschema
from jsonschema.exceptions import SchemaError, ValidationError

__all__ = ["validate_parameters"]


def validate_parameters(parameters: dict, *, input_schema: dict) -> str | None:
    """Returns `None` if `parameters` satisfies `input_schema`, else a
    single human-readable error string -- matches every other stage-5
    failure in `domain/pipeline.py` (`ActionResultPayload.error: str | None`,
    never a structured/multi-error shape)."""
    try:
        jsonschema.validate(instance=parameters, schema=input_schema)
    except SchemaError as exc:
        return f"capability's own input_schema is malformed: {exc.message}"
    except ValidationError as exc:
        path = ".".join(str(segment) for segment in exc.absolute_path)
        location = f" at {path!r}" if path else ""
        return f"parameters failed schema validation{location}: {exc.message}"
    return None
