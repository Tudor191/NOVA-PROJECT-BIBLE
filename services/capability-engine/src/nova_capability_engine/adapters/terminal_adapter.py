"""`terminal` built-in adapter (TDD 3C §3): executable allow-list, restricted
working directory, restricted/minimal environment variables, hard timeout,
`asyncio.create_subprocess_exec` (never `shell=True`, eliminating
shell-injection as a class of escape).

**Working directory (`default_cwd`).** TDD 3C §3's `terminal` row requires a
"restricted working directory". This adapter previously passed
`parameters.get("cwd")` straight to `create_subprocess_exec` -- unvalidated
when supplied (any caller could name any directory on the host) and `None`
when omitted, which silently ran the subprocess in whatever directory
`capability-engine`'s own process was started in. Neither is a restriction.
`default_cwd` closes both halves: it is the directory an omitted `cwd` runs
in, **and** the sole root a caller-supplied `cwd` is validated against.

It is a constructor argument rather than something read out of
`required_resources` because for the `terminal` capability that field holds
the allowed-executable list, not a path (`domain/builtin_capabilities.py`) --
giving it a second, positional meaning would make one field mean two
different things depending on the adapter reading it.

When `default_cwd` is not configured, a caller-supplied `cwd` is refused
rather than honoured: with no declared root there is nothing to validate
against, and admitting it would reinstate exactly the unrestricted-directory
behaviour this exists to remove. Fail-closed, the same posture
`Settings.sandbox_http_allowed_hosts` already takes by defaulting to empty.

**Environment (`path_env`).** The environment stays minimal -- a single
`PATH`, nothing inherited from the parent process -- but the value is now
deployment-configured (`Settings.sandbox_terminal_path`) instead of the
hardcoded `/usr/bin:/bin`. That constant could not resolve most of the
executables the allow-list itself declares: `pytest` and `uv` live in the
active virtualenv's `bin`, so an allow-listed executable failed with
`FileNotFoundError` and surfaced as a sandbox violation. The deployment
knows where its own interpreters live; this module must not guess, and the
default here is deliberately conventional rather than machine-specific.
"""

from __future__ import annotations

import asyncio

from nova_capability_engine.domain.sandbox import (
    SandboxViolation,
    check_executable_allowed,
    resolve_within_roots,
)

__all__ = ["DEFAULT_TERMINAL_PATH", "TerminalAdapter"]

_DEFAULT_TIMEOUT_S = 30.0

DEFAULT_TERMINAL_PATH = "/usr/local/bin:/usr/bin:/bin"
"""Conventional POSIX search path, used when a deployment configures none.
Deliberately not a virtualenv or any other machine-specific location -- a
deployment that needs one sets `CAPABILITY_ENGINE_SANDBOX_TERMINAL_PATH`."""


class TerminalAdapter:
    name = "terminal"

    def __init__(
        self,
        *,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        default_cwd: str | None = None,
        path_env: str = DEFAULT_TERMINAL_PATH,
    ) -> None:
        self._timeout_s = timeout_s
        self._default_cwd = default_cwd
        self._path_env = path_env

    def _resolve_cwd(self, requested: str | None) -> str | None:
        """The working-directory restriction, in one place. An omitted
        `cwd` becomes `default_cwd`; a supplied one must resolve inside it.

        Relative paths resolve against `default_cwd` (`resolve_within_roots`
        anchors them at the root), so `{"cwd": "subproject"}` means the
        subdirectory of the sandbox root a caller would expect, never a
        directory relative to this process."""
        if requested is None:
            return self._default_cwd
        if self._default_cwd is None:
            raise SandboxViolation(
                f"cwd {requested!r} was supplied but this adapter has no configured "
                "default_cwd to validate it against",
                adapter="terminal",
            )
        return str(
            resolve_within_roots(
                requested, allowed_roots=[self._default_cwd], adapter="terminal"
            )
        )

    async def invoke(
        self, operation: str, parameters: dict, *, required_resources: list[str]
    ) -> dict:
        if operation != "execute":
            raise ValueError(f"terminal adapter does not support operation {operation!r}")
        executable = parameters["executable"]
        check_executable_allowed(executable, allowed_executables=required_resources)
        args = parameters.get("args", [])
        cwd = self._resolve_cwd(parameters.get("cwd"))
        return await self.run_subprocess(executable, args, cwd=cwd)

    async def run_subprocess(self, executable: str, args: list[str], *, cwd: str | None) -> dict:
        """Public -- `GitAdapter` composes this directly (its own
        scope-check is repo-root-based, not executable-allow-list-based,
        so it cannot go through `invoke()`'s own `check_executable_allowed`
        without a mismatched interpretation of `required_resources`).

        `cwd` is taken as **already validated** here: `invoke()` has run it
        through `_resolve_cwd`, and `GitAdapter` through its own
        `resolve_within_roots` against the repo root. `None` falls back to
        `default_cwd` so no caller can reach the process's own directory by
        omission."""
        try:
            process = await asyncio.create_subprocess_exec(
                executable,
                *args,
                cwd=cwd if cwd is not None else self._default_cwd,
                env={"PATH": self._path_env},
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
