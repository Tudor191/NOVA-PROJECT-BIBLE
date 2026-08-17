"""`FilesystemAdapter` -- real filesystem I/O against `tmp_path`, including a
real, adversarial sandbox-escape attempt (never mocked -- TDD 3C's own
acceptance criterion 2 requires real OS behavior for scope enforcement)."""

from __future__ import annotations

import pytest
from nova_capability_engine.adapters.filesystem_adapter import FilesystemAdapter
from nova_capability_engine.domain.sandbox import SandboxViolation


async def test_write_then_read_round_trips_inside_the_root(tmp_path) -> None:  # type: ignore[no-untyped-def]
    adapter = FilesystemAdapter()
    root = str(tmp_path)
    target = str(tmp_path / "note.txt")

    write_result = await adapter.invoke(
        "write", {"path": target, "content": "hello"}, required_resources=[root]
    )
    assert write_result["bytes_written"] == 5

    read_result = await adapter.invoke("read", {"path": target}, required_resources=[root])
    assert read_result["content"] == "hello"


async def test_list_returns_entries_inside_the_root(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    adapter = FilesystemAdapter()

    result = await adapter.invoke("list", {}, required_resources=[str(tmp_path)])

    assert sorted(result["entries"]) == ["a.txt", "b.txt"]


async def test_read_outside_the_declared_root_is_a_real_blocked_sandbox_violation(
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    root = tmp_path / "sandboxed"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("do not read me")
    adapter = FilesystemAdapter()

    with pytest.raises(SandboxViolation) as exc_info:
        await adapter.invoke("read", {"path": str(outside)}, required_resources=[str(root)])
    assert exc_info.value.adapter == "filesystem"
    assert outside.read_text() == "do not read me"


async def test_unsupported_operation_raises_value_error(tmp_path) -> None:  # type: ignore[no-untyped-def]
    adapter = FilesystemAdapter()
    with pytest.raises(ValueError, match="delete"):
        await adapter.invoke("delete", {}, required_resources=[str(tmp_path)])
