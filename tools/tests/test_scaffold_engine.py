"""Tests for `tools/scaffold-engine.py`'s service-name validation.

Loaded via `importlib` rather than a normal import because the script's
filename contains hyphens and lives outside any package -- the same technique
`test_scaffold_agent_os_component.py` and `test_scaffold_agent_package.py`
already use.

These tests exist because of Phase 4 decision **D-2**: `_NAME_PATTERN`
previously required a literal `-engine` suffix, which meant `api-gateway` and
`ws-gateway` could not be scaffolded at all. The gap was identified in
`docs/design/phase-3/03-gateway-web-prerequisite.md` §2 and left unactioned.
The pattern now accepts `-gateway` as well.

Only `_validate_name` and the pure name-derivation helpers are exercised here.
Nothing in this module writes to the real repository: the one test that reaches
`_validate_name`'s existence check monkeypatches `SERVICES_DIR` onto a
throwaway `tmp_path`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scaffold-engine.py"


@pytest.fixture(scope="module")
def scaffold() -> ModuleType:
    spec = importlib.util.spec_from_file_location("scaffold_engine", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["scaffold_engine"] = module
    spec.loader.exec_module(module)
    return module


# --- accepted names ------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        # -engine, the pre-D-2 behaviour, which must not regress
        "memory-engine",
        "world-model-engine",
        "ai-model-orchestration-engine",
        "executive-cognition-engine",
        # -gateway, newly accepted by D-2
        "api-gateway",
        "ws-gateway",
    ],
)
def test_valid_names_are_accepted(
    scaffold: ModuleType, name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(scaffold, "SERVICES_DIR", tmp_path)
    scaffold._validate_name(name)  # must not raise


# --- rejected names ------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "memory",  # no recognised suffix
        "memory-service",  # wrong suffix
        "gateway",  # suffix alone is not a name
        "engine",  # suffix alone is not a name
        "Memory-Engine",  # not kebab-case
        "memory_engine",  # underscores, not hyphens
        "-engine",  # empty stem
        "memory--engine",  # empty segment
        "memory-engine-",  # trailing hyphen
        "1memory-engine",  # must start with a letter
        "api-gateway-engine-extra",  # suffix must be terminal
    ],
)
def test_invalid_names_are_rejected(
    scaffold: ModuleType, name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(scaffold, "SERVICES_DIR", tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        scaffold._validate_name(name)
    # The message must name both accepted suffixes, or a caller hitting it has
    # no way to discover that `-gateway` is legal.
    message = str(excinfo.value)
    assert "-engine" in message
    assert "-gateway" in message


def test_existing_service_directory_is_rejected(
    scaffold: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(scaffold, "SERVICES_DIR", tmp_path)
    (tmp_path / "api-gateway").mkdir()
    with pytest.raises(SystemExit, match="already exists"):
        scaffold._validate_name("api-gateway")


# --- name derivation for gateway names -----------------------------------


@pytest.mark.parametrize(
    ("name", "module", "title", "env_prefix"),
    [
        ("memory-engine", "nova_memory_engine", "Memory Engine", "MEMORY_ENGINE"),
        ("api-gateway", "nova_api_gateway", "Api Gateway", "API_GATEWAY"),
        ("ws-gateway", "nova_ws_gateway", "Ws Gateway", "WS_GATEWAY"),
    ],
)
def test_name_derivation(
    scaffold: ModuleType, name: str, module: str, title: str, env_prefix: str
) -> None:
    assert scaffold._module_name(name) == module
    assert scaffold._title(name) == title
    assert scaffold._env_prefix(name) == env_prefix
