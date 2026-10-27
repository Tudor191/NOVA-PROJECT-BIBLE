"""The real companion → real HTTP → real engine harness (findings F-3/F-4/F-5).

Every earlier test of this path replaced at least one segment with a stand-in:
`test_api_workspace_observations.py` drives the route through `TestClient`'s
ASGI transport with no companion and no socket, and the Rust side's
`intake_client.rs` speaks real HTTP to a stub server that is not this engine.
Each half was real; the **join** was not, and an acceptance claim about a
pipeline cannot be assembled from two halves that never met.

This module supplies that join once, so the two test files that need it share
one code path rather than each growing their own:

- a **real `nova-companion` binary**, built from this tree and run as a real
  process, so `main()` and its `run()` loop execute rather than being modelled;
- a **real uvicorn server** on a real TCP socket -- this engine's own
  production server, from its own dependencies, not a test HTTP stack;
- the **real `create_app`** wiring, so the sensor registry, the lifespan, the
  route, the orchestration and `domain/workspace.py` are all the shipped ones.

What varies between the two callers is only the repository: a fake one when the
claim under test is about transport (S-2), a real `PostgresPerceptionRepository`
when it is about persistence (S-3/S-4).

**Nothing here is skipped when a prerequisite is missing.** A skip would turn
absent acceptance evidence into a green run, which is the exact failure mode
these tests exist to remove, so a missing toolchain fails loudly instead.
`cargo` is present on the `ubuntu-latest` image this suite runs on -- the
`checks` job's own Rust step depends on it with no toolchain setup action, and
that step passes -- so this is not a new CI dependency, it is the same one.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import uvicorn
from fastapi import FastAPI

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPANION_ROOT = REPO_ROOT / "companion"

#: Generous enough for a loaded CI runner, short enough that a genuine failure
#: fails instead of hanging. It bounds a wait; it does not pace one.
DEADLINE_SECONDS = 30.0

#: How long to keep watching *after* the expected row arrives, to show that a
#: burst produced no second one. Comfortably wider than the 1.0s debounce
#: window `Settings.workspace_debounce_seconds` defaults to.
SETTLE_SECONDS = 2.5


def build_companion() -> Path:
    """The real binary, built from this tree.

    `NOVA_COMPANION_BINARY` short-circuits the build for a caller that has one
    already (a container image, a warm target directory); everything else
    compiles it here so the binary under test is unambiguously this commit's.
    """
    override = os.environ.get("NOVA_COMPANION_BINARY")
    if override:
        return Path(override)

    if shutil.which("cargo") is None:
        raise RuntimeError(
            "cargo is required to build the nova-companion binary under test. "
            "These tests are deliberately not skippable: S-2/S-3/S-4 are acceptance "
            "claims about a real process, and a skip would report their absence as "
            "success. Install a Rust toolchain, or set NOVA_COMPANION_BINARY to a "
            "prebuilt binary."
        )

    subprocess.run(
        ["cargo", "build", "--locked", "--package", "nova-companion"],
        cwd=COMPANION_ROOT,
        check=True,
        capture_output=True,
    )
    binary = COMPANION_ROOT / "target" / "debug" / "nova-companion"
    if not binary.exists():  # pragma: no cover -- a cargo success implies this
        raise RuntimeError(f"cargo reported success but {binary} is absent")
    return binary


@dataclass
class RunningEngine:
    """A real uvicorn server, already serving, with its real bound port."""

    server: uvicorn.Server
    port: int

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


async def serve(app: FastAPI) -> Iterator[RunningEngine]:
    """Start `app` under a real uvicorn server on an ephemeral port.

    An async generator rather than a context manager because the caller is an
    async fixture. `port=0` lets the kernel choose and the real bound port is
    then read back off the listening socket -- picking a free port and reopening
    it later would race with anything else on the runner.
    """
    import asyncio

    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())

    deadline = time.monotonic() + DEADLINE_SECONDS
    while not server.started:
        if task.done():  # propagate a startup failure instead of timing out on it
            await task
        if time.monotonic() > deadline:
            raise RuntimeError("uvicorn did not start within the deadline")
        await asyncio.sleep(0.02)

    bound: socket.socket = server.servers[0].sockets[0]
    try:
        yield RunningEngine(server=server, port=bound.getsockname()[1])
    finally:
        server.should_exit = True
        await task


@dataclass
class RunningCompanion:
    """A real companion process, watching a real directory.

    Its stdout is drained by a background thread rather than at teardown, for
    two reasons: a pipe nobody reads eventually blocks the process it belongs
    to, and -- the reason that actually bit -- a failing assertion needs the
    daemon's own log lines *in the failure message*, not after the fixture has
    finished unwinding.
    """

    process: subprocess.Popen[str]
    watch_root: Path
    _stdout: list[str] = field(default_factory=list)

    def logs(self) -> list[dict]:
        """Every structured log line the process has emitted so far.

        The companion's own five-field JSON lines, so a test can assert on what
        the daemon actually reported -- including that it reported nothing
        path-shaped.
        """
        lines = []
        for line in list(self._stdout):
            try:
                lines.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return lines

    def raw_output(self) -> str:
        return "\n".join(self._stdout) or "(the companion produced no output)"


def start_companion(binary: Path, *, watch_root: Path, base_url: str) -> RunningCompanion:
    """Spawn the real binary against a real directory and a real engine URL.

    Configured exactly the way the shipped image is -- environment only, no
    flags, no test hooks -- so this exercises `Config::from_env` as deployed.
    """
    environment = {
        **os.environ,
        "NOVA_COMPANION_WATCH_ROOT": str(watch_root),
        "NOVA_COMPANION_PERCEPTION_BASE_URL": base_url,
        "NOVA_COMPANION_SOURCE": "filesystem",
        "NOVA_COMPANION_REQUEST_TIMEOUT_MS": "5000",
    }
    process = subprocess.Popen(
        [str(binary)],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    running = RunningCompanion(process=process, watch_root=watch_root)

    def drain() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            running._stdout.append(line.rstrip("\n"))

    threading.Thread(target=drain, daemon=True, name="companion-stdout").start()

    # The watcher is only armed once `notify` has registered the inotify watch,
    # and the startup line is emitted immediately after `FilesystemSensor::watch`
    # returns -- so it is the process's own signal that it is ready. Writing
    # before it appears is the one genuine race here, and it loses the event
    # silently rather than failing, which is the worst possible way to lose it.
    deadline = time.monotonic() + DEADLINE_SECONDS
    while time.monotonic() < deadline:
        if any(line.get("message") == "nova-companion starting" for line in running.logs()):
            return running
        if process.poll() is not None:
            raise RuntimeError(f"the companion exited at startup:\n{running.raw_output()}")
        time.sleep(0.02)
    raise RuntimeError(f"the companion never signalled readiness:\n{running.raw_output()}")


def stop_companion(companion: RunningCompanion) -> None:
    """Terminate and wait. The draining thread has the output already."""
    if companion.process.poll() is None:
        companion.process.terminate()
    try:
        companion.process.wait(timeout=10)
    except subprocess.TimeoutExpired:  # pragma: no cover -- belt and braces
        companion.process.kill()
        companion.process.wait(timeout=10)


async def wait_until(predicate, *, deadline_seconds: float = DEADLINE_SECONDS):  # type: ignore[no-untyped-def]
    """Poll `predicate` until it returns a truthy value, or the deadline passes.

    The OS decides when a watcher sees a write, so every wait here is bounded
    rather than slept: a fixed sleep would be either flaky or slow, and on a
    loaded runner usually both.
    """
    import asyncio

    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        await asyncio.sleep(0.05)
    return predicate()
