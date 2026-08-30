"""Registry's own 8-step install pipeline against the **real**
`agents/coding-agent` package on disk -- mirrors
`test_real_research_agent_installs.py` exactly, closing the same loop for
the second Agent Package this monorepo ships. Also proves discovery/install
tolerate the disclosed `peer_reviewer_category` manifest field (an
additive `AgentManifest` field Registry's own Manifest Validation stage
never needs to special-case -- it round-trips through `model_validate`
like every other field)."""

from __future__ import annotations

from pathlib import Path

from nova_agent_os_registry.domain.discovery import discover_agent_packages
from nova_agent_os_registry.domain.pipeline import install_agent_package

from tests.fakes.repository import FakeRegistryRepository

_REPO_ROOT = Path(__file__).resolve().parents[4]


def test_coding_agent_is_discoverable_under_the_real_agents_root() -> None:
    discovered = discover_agent_packages(_REPO_ROOT / "agents")
    ids = {package.directory.name for package in discovered}
    assert "coding-agent" in ids


async def test_coding_agent_installs_successfully_through_the_real_pipeline() -> None:
    discovered = discover_agent_packages(_REPO_ROOT / "agents")
    (coding_agent,) = [p for p in discovered if p.directory.name == "coding-agent"]

    repository = FakeRegistryRepository()
    installed = await install_agent_package(
        coding_agent,
        repository=repository,
        communication_port=None,
        primary_user_id=None,
        kernel_version="0.1.0",
    )

    assert installed.category == "coding"
    assert installed.version == "0.1.0"
    assert installed.manifest_json["id"] == "coding-agent"
    assert installed.manifest_json["peer_reviewer_category"] == "architect"
    assert installed.health_status == "healthy"
