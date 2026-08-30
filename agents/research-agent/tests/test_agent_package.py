"""Structural smoke test for the research-agent Agent Package (doc 12 §3/§4)
-- `agent.yaml` declares every required manifest key and validates against
`AgentManifest`; `handler.py`'s own `Handler` class structurally satisfies
`AgentHandler` (the same two checks Registry's own install pipeline
performs at Manifest Validation and Sandbox Test Run, TDD 3E §5)."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from nova_agent_sdk import AgentHandler, AgentManifest

PACKAGE_DIR = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(PACKAGE_DIR / "src"))
from handler import Handler  # noqa: E402


def test_agent_yaml_validates_against_agent_manifest() -> None:
    manifest_text = (PACKAGE_DIR / "agent.yaml").read_text()
    manifest = AgentManifest.model_validate(yaml.safe_load(manifest_text))
    assert manifest.id == "research-agent"
    assert manifest.category == "research"
    assert "inprocess" in manifest.supported_execution_backends


def test_handler_structurally_satisfies_agent_handler() -> None:
    assert issubclass(Handler, AgentHandler)
