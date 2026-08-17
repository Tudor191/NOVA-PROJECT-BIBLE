"""`domain/sandbox.py` -- the shared scope-checking primitives every
adapter composes (TDD 3C §3)."""

from __future__ import annotations

import pytest
from nova_capability_engine.domain.sandbox import (
    SandboxViolation,
    check_executable_allowed,
    check_host_allowed,
    resolve_within_roots,
)


def test_resolve_within_roots_accepts_a_path_inside_the_root(tmp_path) -> None:  # type: ignore[no-untyped-def]
    inside = tmp_path / "a" / "b.txt"
    inside.parent.mkdir(parents=True)
    inside.write_text("x")

    resolved = resolve_within_roots(str(inside), allowed_roots=[str(tmp_path)])

    assert resolved == inside.resolve()


def test_resolve_within_roots_accepts_the_root_itself(tmp_path) -> None:  # type: ignore[no-untyped-def]
    resolved = resolve_within_roots(str(tmp_path), allowed_roots=[str(tmp_path)])
    assert resolved == tmp_path.resolve()


def test_resolve_within_roots_rejects_a_dot_dot_traversal_outside_the_root(tmp_path) -> None:  # type: ignore[no-untyped-def]
    root = tmp_path / "sandboxed"
    root.mkdir()
    escape_target = str(root / ".." / "outside.txt")

    with pytest.raises(SandboxViolation) as exc_info:
        resolve_within_roots(escape_target, allowed_roots=[str(root)])
    assert exc_info.value.adapter == "filesystem"


def test_resolve_within_roots_rejects_a_symlink_that_resolves_outside_the_root(tmp_path) -> None:  # type: ignore[no-untyped-def]
    root = tmp_path / "sandboxed"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("top secret")
    symlink = root / "escape_link"
    symlink.symlink_to(outside / "secret.txt")

    with pytest.raises(SandboxViolation):
        resolve_within_roots(str(symlink), allowed_roots=[str(root)])


def test_check_executable_allowed_accepts_a_declared_executable() -> None:
    check_executable_allowed("git", allowed_executables=["git", "python3"])


def test_check_executable_allowed_rejects_an_undeclared_executable() -> None:
    with pytest.raises(SandboxViolation) as exc_info:
        check_executable_allowed("rm", allowed_executables=["git", "python3"])
    assert exc_info.value.adapter == "terminal"


def test_check_host_allowed_accepts_a_declared_host() -> None:
    check_host_allowed("api.example.com", allowed_hosts=["api.example.com"])


def test_check_host_allowed_rejects_an_undeclared_host() -> None:
    with pytest.raises(SandboxViolation) as exc_info:
        check_host_allowed("evil.example.com", allowed_hosts=["api.example.com"])
    assert exc_info.value.adapter == "http"
