"""Registry's own 8-step install pipeline against the **real**
`agents/documentation-agent` package on disk -- mirrors
`test_real_architect_agent_installs.py` exactly, closing the same loop for
the fifth and final Phase 3E Agent Package this monorepo ships."""

from __future__ import annotations

from pathlib import Path

from nova_agent_os_registry.domain.discovery import discover_agent_packages
from nova_agent_os_registry.domain.pipeline import install_agent_package

from tests.fakes.repository import FakeRegistryRepository

_REPO_ROOT = Path(__file__).resolve().parents[4]


def test_documentation_agent_is_discoverable_under_the_real_agents_root() -> None:
    discovered = discover_agent_packages(_REPO_ROOT / "agents")
    ids = {package.directory.name for package in discovered}
    assert "documentation-agent" in ids


async def test_documentation_agent_installs_successfully_through_the_real_pipeline() -> None:
    discovered = discover_agent_packages(_REPO_ROOT / "agents")
    (documentation_agent,) = [p for p in discovered if p.directory.name == "documentation-agent"]

    repository = FakeRegistryRepository()
    installed = await install_agent_package(
        documentation_agent,
        repository=repository,
        communication_port=None,
        primary_user_id=None,
        kernel_version="0.1.0",
    )

    assert installed.category == "documentation"
    assert installed.version == "0.1.0"
    assert installed.manifest_json["id"] == "documentation-agent"
    assert installed.health_status == "healthy"
