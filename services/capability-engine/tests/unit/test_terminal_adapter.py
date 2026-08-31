"""`TerminalAdapter` -- real `asyncio.create_subprocess_exec` calls, never
`shell=True`. Real, adversarial sandbox-escape attempts (a disallowed
executable), never mocked."""

from __future__ import annotations

import json

import pytest
from nova_capability_engine.adapters.terminal_adapter import (
    DEFAULT_TERMINAL_PATH,
    TerminalAdapter,
)
from nova_capability_engine.domain.sandbox import SandboxViolation


async def test_execute_an_allowed_executable_returns_its_real_exit_code() -> None:
    adapter = TerminalAdapter()

    result = await adapter.invoke(
        "execute",
        {"executable": "python3", "args": ["-c", "print('hi')"]},
        required_resources=["python3"],
    )

    assert result["exit_code"] == 0
    assert "hi" in result["stdout"]
    assert result["timed_out"] is False


async def test_execute_a_disallowed_executable_is_a_real_blocked_sandbox_violation() -> None:
    adapter = TerminalAdapter()

    with pytest.raises(SandboxViolation) as exc_info:
        await adapter.invoke(
            "execute", {"executable": "rm", "args": ["-rf", "/"]}, required_resources=["git"]
        )
    assert exc_info.value.adapter == "terminal"


async def test_execute_a_nonzero_exit_is_a_structured_result_not_an_exception() -> None:
    """TDD 3C §8: 'A registered capability's adapter fails at invocation
    time (e.g., git command exits non-zero) -> structured failure returned
    to the caller' -- never an exception."""
    adapter = TerminalAdapter()

    result = await adapter.invoke(
        "execute",
        {"executable": "python3", "args": ["-c", "import sys; sys.exit(3)"]},
        required_resources=["python3"],
    )

    assert result["exit_code"] == 3


async def test_execute_times_out_without_raising() -> None:
    adapter = TerminalAdapter(timeout_s=0.05)

    result = await adapter.invoke(
        "execute",
        {"executable": "python3", "args": ["-c", "import time; time.sleep(5)"]},
        required_resources=["python3"],
    )

    assert result["timed_out"] is True
    assert result["exit_code"] is None


async def test_unsupported_operation_raises_value_error() -> None:
    adapter = TerminalAdapter()
    with pytest.raises(ValueError, match="frobnicate"):
        await adapter.invoke("frobnicate", {}, required_resources=[])


# --- D8: the restricted working directory TDD 3C §3's `terminal` row requires.


async def _cwd_of(adapter: TerminalAdapter, **parameters: object) -> str:
    """The subprocess's own real working directory, as it reports it -- not
    what the adapter was asked for. Nothing here is mocked."""
    result = await adapter.invoke(
        "execute",
        {"executable": "python3", "args": ["-c", "import os; print(os.getcwd())"], **parameters},
        required_resources=["python3"],
    )
    assert result["exit_code"] == 0, result["stderr"]
    return result["stdout"].strip()


async def test_an_omitted_cwd_runs_in_the_configured_default_not_the_process_cwd(  # type: ignore[no-untyped-def]
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The half of D8 that is a correctness bug rather than a hole: with no
    `cwd` parameter the adapter used to pass `None` straight through, so the
    subprocess inherited whatever directory `capability-engine`'s own process
    was started in. `qa-agent` sends exactly this shape (`pytest -q`, no
    `cwd`), so its test run landed somewhere arbitrary.

    The process is chdir'd elsewhere so inheritance cannot pass by accident."""
    root = tmp_path / "workspace"
    root.mkdir()
    elsewhere = tmp_path / "somewhere-else"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    observed = await _cwd_of(TerminalAdapter(default_cwd=str(root)))

    assert observed == str(root.resolve())
    assert observed != str(elsewhere.resolve())


async def test_a_caller_supplied_cwd_inside_the_root_is_honoured(tmp_path) -> None:  # type: ignore[no-untyped-def]
    root = tmp_path / "workspace"
    nested = root / "subproject"
    nested.mkdir(parents=True)

    observed = await _cwd_of(TerminalAdapter(default_cwd=str(root)), cwd=str(nested))

    assert observed == str(nested.resolve())


async def test_a_relative_caller_supplied_cwd_resolves_under_the_root(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """D7 and D8 composing: a relative `cwd` means a subdirectory of the
    sandbox root, never a directory relative to this process."""
    root = tmp_path / "workspace"
    (root / "subproject").mkdir(parents=True)

    observed = await _cwd_of(TerminalAdapter(default_cwd=str(root)), cwd="subproject")

    assert observed == str((root / "subproject").resolve())


async def test_a_caller_supplied_cwd_outside_the_root_is_a_blocked_violation(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The other half of D8: the working directory was previously not
    validated at all, so any caller could name any directory on the host."""
    root = tmp_path / "workspace"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    adapter = TerminalAdapter(default_cwd=str(root))

    with pytest.raises(SandboxViolation) as exc_info:
        await adapter.invoke(
            "execute",
            {"executable": "python3", "args": ["-c", ""], "cwd": str(outside)},
            required_resources=["python3"],
        )
    assert exc_info.value.adapter == "terminal"


async def test_a_caller_supplied_cwd_escaping_via_dot_dot_is_blocked(tmp_path) -> None:  # type: ignore[no-untyped-def]
    root = tmp_path / "workspace"
    root.mkdir()
    adapter = TerminalAdapter(default_cwd=str(root))

    with pytest.raises(SandboxViolation):
        await adapter.invoke(
            "execute",
            {"executable": "python3", "args": ["-c", ""], "cwd": "../.."},
            required_resources=["python3"],
        )


async def test_a_caller_supplied_cwd_is_refused_when_no_default_is_configured() -> None:
    """Fail-closed: with no declared root there is nothing to validate
    against, and honouring the request would reinstate exactly the
    unrestricted-directory behaviour D8 removes. Same posture
    `sandbox_http_allowed_hosts` takes by defaulting to empty."""
    adapter = TerminalAdapter()

    with pytest.raises(SandboxViolation) as exc_info:
        await adapter.invoke(
            "execute",
            {"executable": "python3", "args": ["-c", ""], "cwd": "/tmp"},
            required_resources=["python3"],
        )
    assert exc_info.value.adapter == "terminal"


# --- D9: an environment that can actually resolve the declared executables.


async def test_the_subprocess_environment_is_the_configured_path_and_nothing_else(  # type: ignore[no-untyped-def]
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TDD 3C §3's "restricted/minimal environment variables": the adapter
    exports exactly one variable, the configured `PATH`, and inherits
    nothing from this process -- asserted against a real marker variable
    set on the parent.

    `LC_CTYPE` is tolerated because the child *interpreter* sets it on
    itself after exec (PEP 538 locale coercion), not because the adapter
    passes it: `env -i python3 -c 'print(os.environ)'` reports `LC_CTYPE`
    from a completely empty environment. Anything beyond that pair would be
    a real leak, so the assertion is a subset check against exactly those
    two keys rather than a blanket "ignore what we didn't expect"."""
    monkeypatch.setenv("NOVA_LEAK_CANARY", "leaked")
    adapter = TerminalAdapter(default_cwd=str(tmp_path), path_env="/usr/bin:/bin")

    result = await adapter.invoke(
        "execute",
        {
            "executable": "python3",
            "args": ["-c", "import os,json; print(json.dumps(dict(os.environ)))"],
        },
        required_resources=["python3"],
    )

    environment = json.loads(result["stdout"])
    assert environment["PATH"] == "/usr/bin:/bin"
    assert set(environment) <= {"PATH", "LC_CTYPE"}
    assert "NOVA_LEAK_CANARY" not in environment


async def test_an_executable_found_only_on_the_configured_path_really_runs(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The D9 payoff, proven against a real executable rather than asserted:
    `sandbox_terminal_allowed_executables` declares `pytest` and `uv`, which
    live in the active virtualenv's `bin` and are unreachable from the old
    hardcoded `/usr/bin:/bin`. A deployment-configured `PATH` resolves them.

    A stand-in binary is used instead of `pytest` itself so the test asserts
    the resolution mechanism rather than this checkout's own layout."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tool = bin_dir / "novatool"
    tool.write_text("#!/bin/sh\necho novatool-ran\n")
    tool.chmod(0o755)

    adapter = TerminalAdapter(default_cwd=str(tmp_path), path_env=str(bin_dir))
    result = await adapter.invoke(
        "execute", {"executable": "novatool"}, required_resources=["novatool"]
    )

    assert result["exit_code"] == 0
    assert "novatool-ran" in result["stdout"]


async def test_that_same_executable_is_unreachable_on_the_default_path(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Negative control for the test above -- without it, that test would
    pass even if `path_env` were ignored and the binary happened to be
    findable anyway. Here the identical call with the default `PATH` must
    fail to resolve."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tool = bin_dir / "novatool"
    tool.write_text("#!/bin/sh\necho novatool-ran\n")
    tool.chmod(0o755)

    adapter = TerminalAdapter(default_cwd=str(tmp_path))

    with pytest.raises(SandboxViolation) as exc_info:
        await adapter.invoke(
            "execute", {"executable": "novatool"}, required_resources=["novatool"]
        )
    assert exc_info.value.adapter == "terminal"


def test_the_default_path_is_conventional_not_machine_specific() -> None:
    """D9: "Prefer the existing deployment configuration mechanism over
    hardcoding a machine-specific path." The fallback must stay a plain
    POSIX search path -- a virtualenv or checkout path baked in here would
    be exactly the hardcoding that decision rules out."""
    assert DEFAULT_TERMINAL_PATH == "/usr/local/bin:/usr/bin:/bin"
