"""`TerminalAdapter` -- real `asyncio.create_subprocess_exec` calls, never
`shell=True`. Real, adversarial sandbox-escape attempts (a disallowed
executable), never mocked."""

from __future__ import annotations

import pytest
from nova_capability_engine.adapters.terminal_adapter import TerminalAdapter
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
