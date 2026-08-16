"""`terminal` built-in adapter (TDD 3C §3): executable allow-list, restricted
working directory, restricted/minimal environment variables, hard timeout,
`asyncio.create_subprocess_exec` (never `shell=True`, eliminating
shell-injection as a class of escape).
"""

from __future__ import annotations

import asyncio

from nova_capability_engine.domain.sandbox import SandboxViolation, check_executable_allowed

__all__ = ["TerminalAdapter"]

_DEFAULT_TIMEOUT_S = 30.0
_MINIMAL_ENV = {"PATH": "/usr/bin:/bin"}


class TerminalAdapter:
    name = "terminal"

    def __init__(self, *, timeout_s: float = _DEFAULT_TIMEOUT_S) -> None:
        self._timeout_s = timeout_s

    async def invoke(
        self, operation: str, parameters: dict, *, required_resources: list[str]
    ) -> dict:
        if operation != "execute":
            raise ValueError(f"terminal adapter does not support operation {operation!r}")
        executable = parameters["executable"]
        check_executable_allowed(executable, allowed_executables=required_resources)
        args = parameters.get("args", [])
        cwd = parameters.get("cwd")
        return await self.run_subprocess(executable, args, cwd=cwd)

    async def run_subprocess(self, executable: str, args: list[str], *, cwd: str | None) -> dict:
        """Public -- `GitAdapter` composes this directly (its own
        scope-check is repo-root-based, not executable-allow-list-based,
        so it cannot go through `invoke()`'s own `check_executable_allowed`
        without a mismatched interpretation of `required_resources`)."""
        try:
            process = await asyncio.create_subprocess_exec(
                executable,
                *args,
                cwd=cwd,
                env=dict(_MINIMAL_ENV),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise SandboxViolation(
                f"executable {executable!r} could not be started: {exc}", adapter="terminal"
            ) from exc
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self._timeout_s)
        except TimeoutError:
            process.kill()
            await process.wait()
            return {"exit_code": None, "stdout": "", "stderr": "", "timed_out": True}
        return {
            "exit_code": process.returncode,
            "stdout": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
            "timed_out": False,
        }
