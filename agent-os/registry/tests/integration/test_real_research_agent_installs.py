"""Registry's own 8-step install pipeline against a **real** Agent Package on
disk -- `agents/research-agent`, the first (and, as of this test, only)
Agent Package this monorepo actually ships. Every other Registry test uses a
synthetic `tmp_path` fixture (TDD 3E Milestone 3's own disclosed "no real
Agent Packages yet... a real, exercised no-op until the first one is
scaffolded"); this closes that loop for the specific package the roadmap's
own step 4 requires ("a single trivial agent (research-agent) to prove the
full loop"), pointing `Settings.agents_root` at the repository's real
`agents/` directory instead of a fixture.
"""

from __future__ import annotations

from pathlib import Path

from nova_agent_os_registry.domain.discovery import discover_agent_packages
from nova_agent_os_registry.domain.pipeline import install_agent_package

from tests.fakes.repository import FakeRegistryRepository

_REPO_ROOT = Path(__file__).resolve().parents[4]


def test_research_agent_is_discoverable_under_the_real_agents_root() -> None:
    discovered = discover_agent_packages(_REPO_ROOT / "agents")
    ids = {package.directory.name for package in discovered}
    assert "research-agent" in ids


async def test_research_agent_installs_successfully_through_the_real_pipeline() -> None:
    discovered = discover_agent_packages(_REPO_ROOT / "agents")
    (research_agent,) = [p for p in discovered if p.directory.name == "research-agent"]

    repository = FakeRegistryRepository()
    installed = await install_agent_package(
        research_agent,
        repository=repository,
        communication_port=None,
        primary_user_id=None,
        kernel_version="0.1.0",
    )

    assert installed.category == "research"
    assert installed.version == "0.1.0"
    assert installed.manifest_json["id"] == "research-agent"
    assert installed.health_status == "healthy"
