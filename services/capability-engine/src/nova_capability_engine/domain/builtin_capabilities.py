"""The four Phase 3 built-in capabilities (TDD 3C §0/§2.3): `git`,
`filesystem`, `terminal`, `http` -- installed through the real 8-stage
pipeline at first boot via a seed/bootstrap call against this engine's own
install API, not hardcoded pre-registered rows (§2.3's design decision).

`required_resources` is deliberately generic (mirrors `Capability` itself
having no adapter-specific fields) -- interpreted per-adapter: an allowed
filesystem root for `filesystem`/`git`, an allowed-executable list for
`terminal`, an allowed-host list for `http`. Populated from `Settings` at
bootstrap time (deployment-specific), not hardcoded here.
"""

from __future__ import annotations

from nova_capability_engine.domain.models import CapabilityManifest

__all__ = ["build_builtin_manifests"]

_GENERIC_INPUT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "operation": {"type": "string"},
        "parameters": {"type": "object"},
    },
    "required": ["operation"],
}
_GENERIC_OUTPUT_SCHEMA: dict = {"type": "object"}

_VERSION = "1.0.0"


def build_builtin_manifests(
    *,
    filesystem_root: str,
    terminal_allowed_executables: list[str],
    http_allowed_hosts: list[str],
) -> list[CapabilityManifest]:
    """Deterministic construction, not a module-level constant, since
    `required_resources` is deployment-scoped (`Settings`)."""
    return [
        CapabilityManifest(
            name="filesystem",
            description="Read, write, and list files within a declared root.",
            category="filesystem",
            version=_VERSION,
            required_permissions=["filesystem:read", "filesystem:write"],
            required_resources=[filesystem_root],
            input_schema=_GENERIC_INPUT_SCHEMA,
            output_schema=_GENERIC_OUTPUT_SCHEMA,
            execution_adapter="filesystem",
        ),
        CapabilityManifest(
            name="terminal",
            description="Execute declared, allow-listed binaries in a restricted environment.",
            category="terminal",
            version=_VERSION,
            required_permissions=["terminal:execute"],
            required_resources=list(terminal_allowed_executables),
            input_schema=_GENERIC_INPUT_SCHEMA,
            output_schema=_GENERIC_OUTPUT_SCHEMA,
            execution_adapter="terminal",
        ),
        CapabilityManifest(
            name="git",
            description="Git version control operations scoped to a declared repository root.",
            category="version_control",
            version=_VERSION,
            required_permissions=["filesystem:read", "filesystem:write", "terminal:execute"],
            required_resources=[filesystem_root],
            input_schema=_GENERIC_INPUT_SCHEMA,
            output_schema=_GENERIC_OUTPUT_SCHEMA,
            execution_adapter="git",
        ),
        CapabilityManifest(
            name="http",
            description="Make outbound HTTP requests to declared, allow-listed hosts.",
            category="network",
            version=_VERSION,
            required_permissions=["network:outbound"],
            required_resources=list(http_allowed_hosts),
            input_schema=_GENERIC_INPUT_SCHEMA,
            output_schema=_GENERIC_OUTPUT_SCHEMA,
            execution_adapter="http",
        ),
    ]
