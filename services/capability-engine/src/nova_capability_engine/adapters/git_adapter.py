"""`git` built-in adapter (TDD 3C §3): same mechanism as `terminal`,
additionally scoped to a declared repository root path -- git operations
are terminal+filesystem operations under this model, not a fourth distinct
sandboxing primitive. Composes `TerminalAdapter` rather than duplicating
its subprocess-execution/timeout logic.
"""

from __future__ import annotations

from nova_capability_engine.adapters.terminal_adapter import TerminalAdapter
from nova_capability_engine.domain.sandbox import SandboxViolation, resolve_within_roots

__all__ = ["GitAdapter"]

_ALLOWED_SUBCOMMANDS = frozenset({"status", "log", "diff", "add", "commit", "branch", "checkout"})


class GitAdapter:
    name = "git"

    def __init__(self, *, terminal: TerminalAdapter | None = None) -> None:
        self._terminal = terminal or TerminalAdapter()

    async def invoke(
        self, operation: str, parameters: dict, *, required_resources: list[str]
    ) -> dict:
        if operation not in _ALLOWED_SUBCOMMANDS:
            raise SandboxViolation(
                f"git subcommand {operation!r} is not on the declared allow-list "
                f"{sorted(_ALLOWED_SUBCOMMANDS)!r}",
                adapter="git",
            )
        repo_root = resolve_within_roots(
            parameters.get("repo_root", required_resources[0]), allowed_roots=required_resources
        )
        args = [operation, *parameters.get("args", [])]
        return await self._terminal.run_subprocess("git", args, cwd=str(repo_root))
