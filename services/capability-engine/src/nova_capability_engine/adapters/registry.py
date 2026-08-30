"""Builds the `{execution_adapter_name: AdapterPort}` mapping every pipeline
run and every `capability.invoke.*` RPC handler call needs -- one process,
one instance per adapter, matching this engine's own "capability-engine's
process is the real executor" architecture (Fork 3C-1/3D-1)."""

from __future__ import annotations

from nova_capability_engine.adapters.filesystem_adapter import FilesystemAdapter
from nova_capability_engine.adapters.git_adapter import GitAdapter
from nova_capability_engine.adapters.http_adapter import HttpAdapter
from nova_capability_engine.adapters.terminal_adapter import TerminalAdapter
from nova_capability_engine.domain.ports import AdapterPort

__all__ = ["build_adapter_registry"]


def build_adapter_registry(
    *,
    terminal_timeout_s: float,
    http_timeout_s: float,
    filesystem_root: str,
    terminal_path: str,
) -> dict[str, AdapterPort]:
    """`filesystem_root` reaches `TerminalAdapter` as its `default_cwd`
    (TDD 3C §3's "restricted working directory") -- the same
    `Settings.sandbox_filesystem_root` that `build_builtin_manifests` puts
    in the `filesystem`/`git` capabilities' `required_resources`, so all
    three adapters scope to one declared root rather than three
    independently-configured ones. `GitAdapter` receives the same
    `TerminalAdapter` instance and therefore the same environment."""
    terminal = TerminalAdapter(
        timeout_s=terminal_timeout_s, default_cwd=filesystem_root, path_env=terminal_path
    )
    return {
        "filesystem": FilesystemAdapter(),
        "terminal": terminal,
        "git": GitAdapter(terminal=terminal),
        "http": HttpAdapter(timeout_s=http_timeout_s),
    }
