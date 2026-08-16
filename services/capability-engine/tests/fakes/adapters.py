"""Fake `domain.ports.AdapterPort` implementations for pipeline unit tests
that need to isolate stage behavior from real subprocess/filesystem I/O.
Real adapters are exercised directly (against `tmp_path`/real subprocesses)
in `tests/unit/test_*_adapter.py` -- these fakes exist only for
`test_pipeline.py`'s stage-isolation tests."""

from __future__ import annotations


class RecordingAdapter:
    """Always succeeds and never raises `SandboxViolation` -- used to prove
    the pipeline's happy path and to record every `invoke()` call it
    receives."""

    name = "recording"

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict, list[str]]] = []

    async def invoke(
        self, operation: str, parameters: dict, *, required_resources: list[str]
    ) -> dict:
        self.calls.append((operation, parameters, required_resources))
        return {"ok": True}


class UnenforcedAdapter:
    """Never raises `SandboxViolation`, even for the pipeline's own
    out-of-scope self-test probe -- simulates a broken/misconfigured
    adapter that fails to enforce its declared scope, proving Sandbox
    Testing halts the pipeline rather than silently registering it
    (TDD 3C's own acceptance criterion 2)."""

    name = "filesystem"

    async def invoke(
        self, operation: str, parameters: dict, *, required_resources: list[str]
    ) -> dict:
        return {"ok": True}
