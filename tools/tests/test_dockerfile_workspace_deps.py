"""Guard: every Dockerfile copies the workspace packages its component needs.

Each component's image is built from the repo root with a hand-maintained list
of `COPY packages/<name> packages/<name>` lines, and `uv sync --frozen` inside
the builder resolves the workspace from exactly those directories. Add a
workspace dependency to a `pyproject.toml` without adding the matching COPY and
the manifest is unresolvable, so the build dies with a bare `exit code: 2` that
names neither the package nor the missing line.

**This file exists because that happened.** Phase 4D added `nova-service-kit` to
`services/autonomy-engine/pyproject.toml` after the engine was scaffolded and
did not update its Dockerfile. `build-and-scan (autonomy-engine)` failed, and so
did the whole e2e job — `docker compose up --build` could not build the image, so
no service in the stack started and the Playwright report was never written. One
missing line, two red workflows, and nothing in either log said which package.

It is the same family as the repository's other hand-maintained-list guards
(`test_build_and_scan_matrix.py` for the image matrix,
`test_compose_migrations.py` for the migrator's `ENGINES`,
`test_e2e_stack_completeness.py` for the e2e service list): a list that must
agree with something else, where the disagreement is invisible until CI burns a
cycle on it.

Only **non-dev** dependencies are checked. Dev dependencies (`nova-testkit`) are
deliberately absent from the images, which build with `--no-dev`.

**A workspace package is located by reading every manifest, never by assuming
`packages/<name>`.** The first draft of this file did assume it and flagged
`agent-os`'s three components, whose images build perfectly well: they depend on
`nova-agent-sdk`, which lives at `agent-os/sdk/python`, and they copy it from
there. A guard that fires on correct code is a guard that gets deleted, so the
mapping is derived from the repository rather than guessed.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _package_directories() -> dict[str, Path]:
    """Map every workspace package name to the directory holding its manifest.

    Derived by reading `[project] name` out of each `pyproject.toml`, because
    the name does not determine the path: `nova-agent-sdk` lives at
    `agent-os/sdk/python`.
    """
    located: dict[str, Path] = {}
    for manifest in REPO_ROOT.glob("**/pyproject.toml"):
        if any(part in {".venv", "node_modules", ".git"} for part in manifest.parts):
            continue
        try:
            name = tomllib.loads(manifest.read_text()).get("project", {}).get("name")
        except tomllib.TOMLDecodeError:  # pragma: no cover - malformed manifest
            continue
        if name:
            located.setdefault(name, manifest.parent.relative_to(REPO_ROOT))
    return located


def _components() -> list[Path]:
    """Every directory holding both a `pyproject.toml` and a `Dockerfile`."""
    found = [
        manifest.parent
        for pattern in ("services/*/pyproject.toml", "agent-os/*/pyproject.toml")
        for manifest in REPO_ROOT.glob(pattern)
        if (manifest.parent / "Dockerfile").exists()
    ]
    return sorted(found)


def _workspace_dependencies(component: Path) -> list[str]:
    """The workspace packages this component declares as real dependencies.

    Intersecting `[tool.uv.sources]`'s workspace entries with
    `[project.dependencies]` is what excludes the dev-only ones: `nova-testkit`
    appears in sources for every component but is never in the image.
    """
    data = tomllib.loads((component / "pyproject.toml").read_text())
    sources = data.get("tool", {}).get("uv", {}).get("sources", {})
    declared = {
        re.split(r"[><=\[;\s]", raw)[0].strip()
        for raw in data.get("project", {}).get("dependencies", [])
    }
    return sorted(
        name
        for name, spec in sources.items()
        if isinstance(spec, dict) and spec.get("workspace") and name in declared
    )


def test_the_scan_finds_components_at_all() -> None:
    """Anti-decoration control: an empty component list would make every
    parametrized case below pass vacuously."""
    components = _components()
    assert len(components) >= 15
    assert any(c.name == "autonomy-engine" for c in components)


def test_the_package_map_resolves_the_awkward_cases() -> None:
    """Anti-decoration control for `_package_directories`. If it silently
    returned `{}`, every case below would pass with nothing copied."""
    located = _package_directories()
    assert located["nova-contracts"] == Path("packages/nova-contracts")
    # The case the first draft of this file got wrong.
    assert located["nova-agent-sdk"] == Path("agent-os/sdk/python")


@pytest.mark.parametrize("component", _components(), ids=lambda c: c.name)
def test_every_workspace_dependency_is_copied_into_the_image(component: Path) -> None:
    """A declared workspace dependency with no COPY line cannot be resolved by
    `uv sync --frozen`, and the build fails without naming it."""
    dockerfile = (component / "Dockerfile").read_text()
    located = _package_directories()

    missing = []
    for name in _workspace_dependencies(component):
        directory = located.get(name)
        assert directory is not None, f"{name} has no manifest anywhere in the repository"
        # Both halves of the two-phase COPY: the manifest (for layer caching)
        # and the sources. A manifest without its sources leaves `uv`
        # resolving against a package whose code is absent.
        manifest_copied = f"COPY {directory}/pyproject.toml" in dockerfile
        sources_copied = f"COPY {directory} {directory}" in dockerfile
        if not (manifest_copied and sources_copied):
            missing.append(f"{name} (at {directory})")

    assert not missing, (
        f"{component.name}/Dockerfile declares {missing} as workspace "
        f"dependencies but does not copy them into the build context. "
        f"`uv sync --frozen` will fail with a bare exit code 2 that names "
        f"neither the package nor the missing line."
    )
