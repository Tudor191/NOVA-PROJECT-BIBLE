"""Filesystem-based Agent Package discovery (doc 12 §6 flowchart's
"Discover" node; doc 12 §15's own table: "Registry | Filesystem-based
(agents declared in the monorepo)" is Phase 3's only discovery mode --
Git-repo/HTTP-registry/marketplace discovery is Phase 8+, not built here).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = ["DiscoveredPackage", "discover_agent_packages"]


@dataclass(frozen=True)
class DiscoveredPackage:
    """One `agents/<name>-agent/` directory with both required files
    present (doc 12 §3's exact layout)."""

    directory: Path
    manifest_path: Path
    handler_path: Path


def discover_agent_packages(agents_root: Path) -> list[DiscoveredPackage]:
    """Scans `agents_root` (doc 02's `agents/` directory) for every
    immediate subdirectory containing both `agent.yaml` and
    `src/handler.py`. A subdirectory missing either file is silently
    skipped, not an error -- `agents/` may hold in-progress packages not
    yet ready for install (this project's own current state: none of the
    five named agents exist yet, Phase 3E Milestone 3's explicit scope
    boundary)."""
    if not agents_root.is_dir():
        return []
    discovered: list[DiscoveredPackage] = []
    for entry in sorted(agents_root.iterdir()):
        if not entry.is_dir():
            continue
        manifest_path = entry / "agent.yaml"
        handler_path = entry / "src" / "handler.py"
        if manifest_path.is_file() and handler_path.is_file():
            discovered.append(DiscoveredPackage(entry, manifest_path, handler_path))
    return discovered
