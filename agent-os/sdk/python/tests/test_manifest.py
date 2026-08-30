"""Tests for `AgentManifest` (doc 12 §3's `agent.yaml` schema)."""

from __future__ import annotations

import pytest
from nova_agent_sdk import AgentManifest
from pydantic import ValidationError


def _manifest_kwargs(**overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "id": "coding-agent",
        "version": "1.3.0",
        "category": "coding",
        "display_name": "Coding Agent",
        "required_capabilities": ["git", "filesystem", "terminal"],
        "required_permissions": ["filesystem:write:project-scope", "terminal:execute"],
        "supported_execution_backends": ["inprocess", "subprocess", "container"],
        "resource_profile": {"cpu": "standard", "memory": "standard", "gpu": "none"},
        "health_check": {"interval_seconds": 30},
        "compatibility": {"min_kernel_version": "1.0.0"},
    }
    defaults.update(overrides)
    return defaults


def test_agent_manifest_round_trips_doc12_section3_worked_example() -> None:
    manifest = AgentManifest.model_validate(_manifest_kwargs())
    round_tripped = AgentManifest.model_validate(manifest.model_dump(mode="json"))
    assert round_tripped == manifest
    assert manifest.resource_profile.cpu == "standard"
    assert manifest.health_check.interval_seconds == 30
    assert manifest.compatibility.min_kernel_version == "1.0.0"


def test_agent_manifest_defaults_empty_capabilities_and_permissions() -> None:
    kwargs = _manifest_kwargs()
    del kwargs["required_capabilities"]
    del kwargs["required_permissions"]
    manifest = AgentManifest.model_validate(kwargs)
    assert manifest.required_capabilities == []
    assert manifest.required_permissions == []


def test_agent_manifest_rejects_an_unsupported_execution_backend_value() -> None:
    with pytest.raises(ValidationError):
        AgentManifest.model_validate(
            _manifest_kwargs(supported_execution_backends=["quantum-backend"])
        )


def test_agent_manifest_requires_every_top_level_field() -> None:
    kwargs = _manifest_kwargs()
    del kwargs["compatibility"]
    with pytest.raises(ValidationError):
        AgentManifest.model_validate(kwargs)
