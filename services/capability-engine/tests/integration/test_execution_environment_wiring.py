"""Slice 3's execution-environment fixes (D7/D8/D9), proven through the
real `capability.invoke.request` RPC against a real `create_app()` rather
than against adapters constructed by hand.

`tests/unit/test_sandbox.py` and `tests/unit/test_terminal_adapter.py`
already prove the primitives in isolation. What those cannot prove is the
*wiring*: that `Settings.sandbox_filesystem_root` and
`Settings.sandbox_terminal_path` actually reach the adapters
`build_adapter_registry` constructs during `create_app`'s lifespan, and
that a request shaped the way a real agent shapes it survives the whole
served path. That gap is exactly where these three defects lived --
`resolve_within_roots` and `TerminalAdapter` were each individually
"working", and the composed system still rejected every agent write and
ran every agent command in an arbitrary directory.

`adapters=` is deliberately left unset, following this file's sibling
`test_events_capability_resolve_and_invoke.py`: `create_app` then builds
the engine's own real adapters, so the filesystem write and the subprocess
below are genuine, never mocked.
"""

from __future__ import annotations

import json
import subprocess
from uuid import uuid4

from nova_capability_engine.adapters.terminal_adapter import DEFAULT_TERMINAL_PATH
from nova_capability_engine.config import Settings
from nova_capability_engine.main import create_app
from nova_contracts import CapabilityInvokeReplyPayload, CapabilityInvokeRequestPayload
from nova_eventbus_sdk import BoundEventBus

from tests.fakes.repository import FakeCapabilityRepository

_CALLER = "test-caller-engine"


def _caller_bus(app) -> BoundEventBus:  # type: ignore[no-untyped-def]
    return BoundEventBus(
        app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
        engine_name=_CALLER,
        publishable_subjects=frozenset({"capability.invoke.request"}),
        subscribable_subjects=frozenset(),
    )


async def _invoke(
    app,  # type: ignore[no-untyped-def]
    repository: FakeCapabilityRepository,
    *,
    capability_name: str,
    operation: str,
    parameters: dict,
) -> CapabilityInvokeReplyPayload:
    capability = next(c for c in repository.capabilities.values() if c.name == capability_name)
    reply_envelope = await _caller_bus(app).request(
        "capability.invoke.request",
        CapabilityInvokeRequestPayload(
            capability_id=capability.id,
            operation=operation,
            parameters=parameters,
            requesting_engine=_CALLER,
            correlation_id=uuid4(),
        ),
        source_engine=_CALLER,
    )
    return CapabilityInvokeReplyPayload.model_validate(reply_envelope.payload)


async def test_an_agent_shaped_relative_write_lands_inside_the_configured_root(
    tmp_path,  # type: ignore[no-untyped-def]
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """D7 end to end. The path is the exact shape `coding-agent` builds
    (`f"coding-agent-output/{task.id}.md"`, project-relative), and
    `action-engine` forwards `parameters` to this RPC verbatim -- so this is
    the real request that used to come back `sandbox_violation` and leave
    criterion #1 with nothing written.

    The process is chdir'd away from the sandbox root so a cwd-anchored
    resolution cannot make this pass by coincidence."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    root = tmp_path / "workspace"
    root.mkdir()
    elsewhere = tmp_path / "somewhere-else"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    repository = FakeCapabilityRepository()
    app = create_app(Settings(sandbox_filesystem_root=str(root)), repository=repository)

    async with app.router.lifespan_context(app):
        task_id = uuid4()
        reply = await _invoke(
            app,
            repository,
            capability_name="filesystem",
            operation="write",
            parameters={
                "operation": "write",
                "path": f"coding-agent-output/{task_id}.md",
                "content": "# scripted change\n",
            },
        )

    assert reply.outcome == "success"
    written = root / "coding-agent-output" / f"{task_id}.md"
    assert written.read_text() == "# scripted change\n"
    assert not (elsewhere / "coding-agent-output").exists()


async def test_a_relative_write_that_climbs_out_of_the_root_is_still_refused(
    tmp_path,  # type: ignore[no-untyped-def]
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """The boundary D7 must not have widened, asserted over the same real
    RPC: anchoring relative paths at the root is not a way to leave it."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    root = tmp_path / "workspace"
    root.mkdir()
    repository = FakeCapabilityRepository()
    app = create_app(Settings(sandbox_filesystem_root=str(root)), repository=repository)

    async with app.router.lifespan_context(app):
        reply = await _invoke(
            app,
            repository,
            capability_name="filesystem",
            operation="write",
            parameters={
                "operation": "write",
                "path": "../escaped.md",
                "content": "should never be written",
            },
        )

    assert reply.outcome == "sandbox_violation"
    assert not (tmp_path / "escaped.md").exists()


async def test_a_terminal_command_runs_in_the_configured_root_by_default(
    tmp_path,  # type: ignore[no-untyped-def]
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """D8 wiring. `qa-agent` sends `{"operation": "execute", "executable":
    "pytest", "args": ["-q"]}` with no `cwd`, so where that lands is decided
    entirely by what `create_app` gave the adapter. Proven with a command
    that reports its own real working directory."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    root = tmp_path / "workspace"
    root.mkdir()
    elsewhere = tmp_path / "somewhere-else"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    repository = FakeCapabilityRepository()
    app = create_app(Settings(sandbox_filesystem_root=str(root)), repository=repository)

    async with app.router.lifespan_context(app):
        reply = await _invoke(
            app,
            repository,
            capability_name="terminal",
            operation="execute",
            parameters={
                "operation": "execute",
                "executable": "python3",
                "args": ["-c", "import os; print(os.getcwd())"],
            },
        )

    assert reply.outcome == "success"
    assert reply.result is not None
    assert reply.result["stdout"].strip() == str(root.resolve())


async def test_a_terminal_cwd_outside_the_configured_root_is_refused_over_the_rpc(
    tmp_path,  # type: ignore[no-untyped-def]
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """D8's other half through the served path: before this slice the RPC
    would have honoured any `cwd` a caller sent."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    root = tmp_path / "workspace"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    repository = FakeCapabilityRepository()
    app = create_app(Settings(sandbox_filesystem_root=str(root)), repository=repository)

    async with app.router.lifespan_context(app):
        reply = await _invoke(
            app,
            repository,
            capability_name="terminal",
            operation="execute",
            parameters={
                "operation": "execute",
                "executable": "python3",
                "args": ["-c", "import os; print(os.getcwd())"],
                "cwd": str(outside),
            },
        )

    assert reply.outcome == "sandbox_violation"


async def test_the_configured_terminal_path_reaches_the_adapter(
    tmp_path,  # type: ignore[no-untyped-def]
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """D9 wiring: `Settings.sandbox_terminal_path` is what the subprocess
    actually gets. This is the setting a deployment (and the Slice 5 E2E
    fixture) will point at the virtualenv `bin` so the allow-list's own
    `pytest`/`uv` become resolvable."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    root = tmp_path / "workspace"
    root.mkdir()
    configured_path = f"/usr/bin:/bin:{tmp_path / 'extra-bin'}"

    repository = FakeCapabilityRepository()
    app = create_app(
        Settings(sandbox_filesystem_root=str(root), sandbox_terminal_path=configured_path),
        repository=repository,
    )

    async with app.router.lifespan_context(app):
        reply = await _invoke(
            app,
            repository,
            capability_name="terminal",
            operation="execute",
            parameters={
                "operation": "execute",
                "executable": "python3",
                "args": ["-c", "import os,json; print(json.dumps(dict(os.environ)))"],
            },
        )

    assert reply.outcome == "success"
    assert reply.result is not None
    assert json.loads(reply.result["stdout"])["PATH"] == configured_path


async def test_a_git_operation_still_scopes_to_its_own_repo_root(
    tmp_path,  # type: ignore[no-untyped-def]
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """Regression guard for the composition Slice 3 touched: `GitAdapter`
    resolves its own repo root and hands `TerminalAdapter.run_subprocess` an
    already-validated `cwd`. Giving `TerminalAdapter` a `default_cwd` must
    not have changed which directory git actually runs in -- if the default
    silently won, git would run at the sandbox root instead of the repo.

    Two real repositories are created, each with a differently-named
    untracked file, and `git status` is asked for one of them by relative
    path. Naming the right file is only possible if git ran in the right
    directory: a fallback to `default_cwd` (the parent of both) or to the
    wrong repo produces different output."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    root = tmp_path / "workspace"
    target = root / "project"
    decoy = root / "other-project"
    for repo, marker in ((target, "target-marker.txt"), (decoy, "decoy-marker.txt")):
        repo.mkdir(parents=True)
        (repo / marker).write_text("x")
        subprocess.run(
            ["git", "init", "-q"], cwd=repo, env={"PATH": DEFAULT_TERMINAL_PATH}, check=True
        )

    repository = FakeCapabilityRepository()
    app = create_app(Settings(sandbox_filesystem_root=str(root)), repository=repository)

    async with app.router.lifespan_context(app):
        reply = await _invoke(
            app,
            repository,
            capability_name="git",
            operation="status",
            parameters={"operation": "status", "repo_root": "project"},
        )

    assert reply.outcome == "success", reply.error
    assert reply.result is not None
    assert reply.result["exit_code"] == 0
    assert "target-marker.txt" in reply.result["stdout"]
    assert "decoy-marker.txt" not in reply.result["stdout"]
