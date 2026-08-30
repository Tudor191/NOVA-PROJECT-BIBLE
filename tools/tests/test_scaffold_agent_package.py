"""Tests for tools/scaffold-agent-package.py (Fork 3E-4). Loaded via
`importlib` (not a normal import) because the script's filename contains
hyphens and lives outside any package -- see test_scaffold_agent_os_component.py
for the same technique applied to the sibling script.

Unlike the agent-os component scaffold, this script touches no shared
workspace-registration files -- doc 12 §6/§15's Phase 3 Agent Registry
discovery is filesystem-based, so there is nothing to register.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scaffold-agent-package.py"


def _load_module(tmp_path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("scaffold_agent_package", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    module.REPO_ROOT = tmp_path  # type: ignore[attr-defined]
    module.AGENTS_DIR = tmp_path / "agents"  # type: ignore[attr-defined]
    return module


@pytest.mark.parametrize(
    "bad_name",
    ["Research-Agent", "research_agent", "research", "-agent", "agent", ""],
)
def test_validate_name_requires_kebab_case_agent_suffix(tmp_path: Path, bad_name: str) -> None:
    mod = _load_module(tmp_path)
    with pytest.raises(SystemExit):
        mod._validate_name(bad_name)


def test_validate_name_accepts_kebab_case_agent_suffix(tmp_path: Path) -> None:
    mod = _load_module(tmp_path)
    mod._validate_name("research-agent")  # must not raise


def test_validate_name_rejects_existing_directory(tmp_path: Path) -> None:
    mod = _load_module(tmp_path)
    (mod.AGENTS_DIR / "research-agent").mkdir(parents=True)
    with pytest.raises(SystemExit):
        mod._validate_name("research-agent")


def test_render_generates_doc12_section3_layout_exactly(tmp_path: Path) -> None:
    mod = _load_module(tmp_path)
    agent_dir = mod.AGENTS_DIR / "research-agent"
    mod._render(agent_dir, "research-agent", "Research Agent")

    for expected in [
        agent_dir / "agent.yaml",
        agent_dir / "src" / "handler.py",
        agent_dir / "README.md",
        agent_dir / "tests" / "test_agent_package.py",
    ]:
        assert expected.is_file(), f"expected {expected} to exist"

    # No pyproject.toml/package.json -- not a uv/pnpm workspace member
    # (doc 12 §6/§15: filesystem-based Registry discovery).
    assert not (agent_dir / "pyproject.toml").exists()
    assert not (agent_dir / "package.json").exists()


def test_agent_yaml_contains_doc12_section3_required_fields(tmp_path: Path) -> None:
    mod = _load_module(tmp_path)
    agent_dir = mod.AGENTS_DIR / "research-agent"
    mod._render(agent_dir, "research-agent", "Research Agent")

    manifest = (agent_dir / "agent.yaml").read_text()
    assert "id: research-agent" in manifest
    for key in (
        "version:",
        "category:",
        "display_name:",
        "required_capabilities:",
        "required_permissions:",
        "supported_execution_backends:",
        "resource_profile:",
        "health_check:",
        "compatibility:",
    ):
        assert key in manifest


def test_handler_py_references_agent_sdk_and_task_node_snapshot(tmp_path: Path) -> None:
    mod = _load_module(tmp_path)
    agent_dir = mod.AGENTS_DIR / "research-agent"
    mod._render(agent_dir, "research-agent", "Research Agent")

    handler = (agent_dir / "src" / "handler.py").read_text()
    assert "from nova_agent_sdk import" in handler
    assert "AgentHandler" in handler
    assert "TaskNodeSnapshot" in handler
    assert "class Handler(AgentHandler):" in handler


def test_generated_smoke_test_does_not_import_handler(tmp_path: Path) -> None:
    mod = _load_module(tmp_path)
    agent_dir = mod.AGENTS_DIR / "research-agent"
    mod._render(agent_dir, "research-agent", "Research Agent")

    smoke_test = (agent_dir / "tests" / "test_agent_package.py").read_text()
    assert "import handler" not in smoke_test
    assert "from src" not in smoke_test
    assert "nova_agent_sdk" not in smoke_test


def test_main_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_module(tmp_path)
    monkeypatch.setattr(sys, "argv", ["scaffold-agent-package.py", "qa-agent"])

    exit_code = mod.main()

    assert exit_code == 0
    assert (mod.AGENTS_DIR / "qa-agent" / "agent.yaml").is_file()
