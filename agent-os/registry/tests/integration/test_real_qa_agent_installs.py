"""Registry's own 8-step install pipeline against the **real**
`agents/qa-agent` package on disk -- mirrors
`test_real_coding_agent_installs.py` exactly, closing the same loop for the
third Agent Package this monorepo ships. Also proves discovery/install
tolerate a manifest with no `peer_reviewer_category` at all (the field's
own default, `None`) exactly as cleanly as one that declares it."""

from __future__ import annotations

from pathlib import Path

from nova_agent_os_registry.domain.discovery import discover_agent_packages
from nova_agent_os_registry.domain.pipeline import install_agent_package

from tests.fakes.repository import FakeRegistryRepository

_REPO_ROOT = Path(__file__).resolve().parents[4]


def test_qa_agent_is_discoverable_under_the_real_agents_root() -> None:
    discovered = discover_agent_packages(_REPO_ROOT / "agents")
    ids = {package.directory.name for package in discovered}
    assert "qa-agent" in ids


async def test_qa_agent_installs_successfully_through_the_real_pipeline() -> None:
    discovered = discover_agent_packages(_REPO_ROOT / "agents")
    (qa_agent,) = [p for p in discovered if p.directory.name == "qa-agent"]

    repository = FakeRegistryRepository()
    installed = await install_agent_package(
        qa_agent,
        repository=repository,
        communication_port=None,
        primary_user_id=None,
        kernel_version="0.1.0",
    )

    assert installed.category == "qa"
    assert installed.version == "0.1.0"
    assert installed.manifest_json["id"] == "qa-agent"
    assert "peer_reviewer_category" not in installed.manifest_json or (
        installed.manifest_json["peer_reviewer_category"] is None
    )
    assert installed.health_status == "healthy"
