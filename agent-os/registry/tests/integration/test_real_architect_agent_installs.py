"""Registry's own 8-step install pipeline against the **real**
`agents/architect-agent` package on disk -- mirrors
`test_real_qa_agent_installs.py` exactly, closing the same loop for the
fourth Agent Package this monorepo ships, and the one `coding-agent`'s own
`peer_reviewer_category: architect` is waiting for."""

from __future__ import annotations

from pathlib import Path

from nova_agent_os_registry.domain.discovery import discover_agent_packages
from nova_agent_os_registry.domain.pipeline import install_agent_package

from tests.fakes.repository import FakeRegistryRepository

_REPO_ROOT = Path(__file__).resolve().parents[4]


def test_architect_agent_is_discoverable_under_the_real_agents_root() -> None:
    discovered = discover_agent_packages(_REPO_ROOT / "agents")
    ids = {package.directory.name for package in discovered}
    assert "architect-agent" in ids


async def test_architect_agent_installs_successfully_through_the_real_pipeline() -> None:
    discovered = discover_agent_packages(_REPO_ROOT / "agents")
    (architect_agent,) = [p for p in discovered if p.directory.name == "architect-agent"]

    repository = FakeRegistryRepository()
    installed = await install_agent_package(
        architect_agent,
        repository=repository,
        communication_port=None,
        primary_user_id=None,
        kernel_version="0.1.0",
    )

    assert installed.category == "architect"
    assert installed.version == "0.1.0"
    assert installed.manifest_json["id"] == "architect-agent"
    assert installed.health_status == "healthy"
