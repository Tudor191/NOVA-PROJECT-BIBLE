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
    *, terminal_timeout_s: float, http_timeout_s: float
) -> dict[str, AdapterPort]:
    terminal = TerminalAdapter(timeout_s=terminal_timeout_s)
    return {
        "filesystem": FilesystemAdapter(),
        "terminal": terminal,
        "git": GitAdapter(terminal=terminal),
        "http": HttpAdapter(timeout_s=http_timeout_s),
    }
