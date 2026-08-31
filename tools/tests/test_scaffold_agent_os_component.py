"""Tests for tools/scaffold-agent-os-component.py (Fork 3E-4). Loaded via
`importlib` (not a normal import) because the script's filename contains
hyphens and lives outside any package -- the same reason no test file for
`tools/scaffold-engine.py` exists yet either; this is the first.

Every test operates against a throwaway `tmp_path` copy of the two files the
script mutates (`pyproject.toml`, `pnpm-workspace.yaml`), monkeypatched onto
the loaded module -- never the real repo root.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
import tomlkit

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scaffold-agent-os-component.py"

_FIXTURE_PYPROJECT = '''[tool.uv.workspace]
members = ["packages/*", "services/*"]

[tool.importlinter]
root_packages = [
    "nova_core",
    "nova_service_kit",
]
include_external_packages = true

[[tool.importlinter.contracts]]
name = "Engines are independent (ADR-004): no engine imports another engine's internals directly"
type = "independence"
modules = [
    "nova_core",
]

[[tool.importlinter.contracts]]
name = "No engine imports a message broker client directly (ADR-006): only nova_eventbus_sdk may"
type = "forbidden"
source_modules = [
    "nova_core",
]
forbidden_modules = [
    "nats",
]

[[tool.importlinter.contracts]]
name = "No engine imports a graph database client directly (ADR-007): only nova_graphstore_sdk may"
type = "forbidden"
source_modules = [
    "nova_core",
]
forbidden_modules = [
    "neo4j",
]

[[tool.importlinter.contracts]]
name = "nova-service-kit has no engine-specific knowledge (ADR-034): it \
may not import any engine's own top-level package"
type = "forbidden"
source_modules = [
    "nova_service_kit",
]
forbidden_modules = [
    "nova_core",
]
'''

_FIXTURE_PNPM_WORKSPACE = """packages:
  - \"apps/*\"
  - \"packages/*\"
  - \"services/*\"
"""


def _load_module(tmp_path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("scaffold_agent_os_component", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    (tmp_path / "pyproject.toml").write_text(_FIXTURE_PYPROJECT)
    (tmp_path / "pnpm-workspace.yaml").write_text(_FIXTURE_PNPM_WORKSPACE)
    module.REPO_ROOT = tmp_path  # type: ignore[attr-defined]
    module.AGENT_OS_DIR = tmp_path / "agent-os"  # type: ignore[attr-defined]
    module.ROOT_PYPROJECT = tmp_path / "pyproject.toml"  # type: ignore[attr-defined]
    module.PNPM_WORKSPACE = tmp_path / "pnpm-workspace.yaml"  # type: ignore[attr-defined]
    return module


@pytest.mark.parametrize("bad_name", ["Kernel", "kernel_registry", "-kernel", "kernel-", ""])
def test_validate_name_rejects_non_kebab_case(tmp_path: Path, bad_name: str) -> None:
    mod = _load_module(tmp_path)
    with pytest.raises(SystemExit):
        mod._validate_name(bad_name)


def test_validate_name_accepts_kebab_case_with_no_engine_suffix_required(tmp_path: Path) -> None:
    mod = _load_module(tmp_path)
    mod._validate_name("kernel")  # must not raise -- no '-engine' suffix required (Fork 3E-4)


def test_validate_name_rejects_existing_directory(tmp_path: Path) -> None:
    mod = _load_module(tmp_path)
    (mod.AGENT_OS_DIR / "kernel").mkdir(parents=True)
    with pytest.raises(SystemExit):
        mod._validate_name("kernel")


def test_module_name_is_nova_agent_os_prefixed(tmp_path: Path) -> None:
    mod = _load_module(tmp_path)
    assert mod._module_name("kernel") == "nova_agent_os_kernel"


def test_render_generates_expected_file_structure(tmp_path: Path) -> None:
    mod = _load_module(tmp_path)
    component_dir = mod.AGENT_OS_DIR / "kernel"
    mod._render(component_dir, "nova_agent_os_kernel", "kernel", "Kernel", "AGENT_OS_KERNEL")

    src = component_dir / "src" / "nova_agent_os_kernel"
    for expected in [
        component_dir / "pyproject.toml",
        component_dir / "package.json",
        component_dir / "README.md",
        src / "__init__.py",
        src / "py.typed",
        src / "config.py",
        src / "main.py",
        src / "domain" / "__init__.py",
        src / "events" / "__init__.py",
        src / "events" / "published.py",
        src / "events" / "subscribed.py",
        src / "repository" / "__init__.py",
        component_dir / "tests" / "__init__.py",
        component_dir / "tests" / "unit" / "__init__.py",
        component_dir / "tests" / "integration" / "__init__.py",
        component_dir / "tests" / "fakes" / "__init__.py",
        component_dir / "tests" / "integration" / "test_health.py",
    ]:
        assert expected.is_file(), f"expected {expected} to exist"

    # No api/ package and no Dockerfile -- deliberate divergence from
    # scaffold-engine.py (TDD 3E §4: no /v1/... REST surface; container-image
    # wiring is a separate, conditional follow-up, not automatic).
    assert not (src / "api").exists()
    assert not (component_dir / "Dockerfile").exists()


def test_render_main_py_uses_make_health_router_not_hand_rolled_health(tmp_path: Path) -> None:
    mod = _load_module(tmp_path)
    component_dir = mod.AGENT_OS_DIR / "kernel"
    mod._render(component_dir, "nova_agent_os_kernel", "kernel", "Kernel", "AGENT_OS_KERNEL")

    main_py = (component_dir / "src" / "nova_agent_os_kernel" / "main.py").read_text()
    assert "from nova_service_kit import make_health_router" in main_py
    assert "make_health_router()" in main_py
    assert "prometheus_asgi_app" in main_py
    assert 'prefix="/v1' not in main_py


def test_update_root_pyproject_registers_workspace_glob_root_packages_and_contracts(
    tmp_path: Path,
) -> None:
    mod = _load_module(tmp_path)
    mod._update_root_pyproject("nova_agent_os_kernel")

    doc = tomlkit.parse(mod.ROOT_PYPROJECT.read_text())
    assert "agent-os/*" in doc["tool"]["uv"]["workspace"]["members"]
    assert "nova_agent_os_kernel" in doc["tool"]["importlinter"]["root_packages"]

    contracts = {c["name"]: c for c in doc["tool"]["importlinter"]["contracts"]}
    assert "nova_agent_os_kernel" in contracts[
        "Engines are independent (ADR-004): no engine imports another engine's internals directly"
    ]["modules"]
    assert "nova_agent_os_kernel" in contracts[
        "No engine imports a message broker client directly (ADR-006): "
        "only nova_eventbus_sdk may"
    ]["source_modules"]
    assert "nova_agent_os_kernel" in contracts[
        "No engine imports a graph database client directly (ADR-007): "
        "only nova_graphstore_sdk may"
    ]["source_modules"]
    assert "nova_agent_os_kernel" in contracts[
        "nova-service-kit has no engine-specific knowledge (ADR-034): it "
        "may not import any engine's own top-level package"
    ]["forbidden_modules"]

    pnpm_text = mod.PNPM_WORKSPACE.read_text()
    assert '  - "agent-os/*"' in pnpm_text.splitlines()


def test_update_root_pyproject_is_idempotent(tmp_path: Path) -> None:
    mod = _load_module(tmp_path)
    mod._update_root_pyproject("nova_agent_os_kernel")
    mod._update_root_pyproject("nova_agent_os_kernel")

    doc = tomlkit.parse(mod.ROOT_PYPROJECT.read_text())
    assert doc["tool"]["uv"]["workspace"]["members"].count("agent-os/*") == 1
    assert doc["tool"]["importlinter"]["root_packages"].count("nova_agent_os_kernel") == 1

    pnpm_lines = mod.PNPM_WORKSPACE.read_text().splitlines()
    assert pnpm_lines.count('  - "agent-os/*"') == 1


def test_main_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_module(tmp_path)
    monkeypatch.setattr(sys, "argv", ["scaffold-agent-os-component.py", "registry"])

    exit_code = mod.main()

    assert exit_code == 0
    assert (mod.AGENT_OS_DIR / "registry" / "src" / "nova_agent_os_registry" / "main.py").is_file()
    doc = tomlkit.parse(mod.ROOT_PYPROJECT.read_text())
    assert "nova_agent_os_registry" in doc["tool"]["importlinter"]["root_packages"]
