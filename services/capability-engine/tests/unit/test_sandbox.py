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


async def test_a_relative_path_anchors_at_the_root_not_the_process_cwd(  # type: ignore[no-untyped-def]
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D7. Every real caller sends a project-relative path -- `coding-agent`
    builds `f"coding-agent-output/{task.id}.md"` and `action-engine` passes
    `parameters` through verbatim. Anchored at `Path.cwd()` those all landed
    outside the declared root and were rejected, making the `filesystem`
    capability unusable for the one thing it exists to do.

    The process is deliberately chdir'd somewhere else entirely, so a
    cwd-anchored implementation cannot pass this by coincidence."""
    root = tmp_path / "workspace"
    root.mkdir()
    elsewhere = tmp_path / "somewhere-else"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    resolved = resolve_within_roots("coding-agent-output/x.md", allowed_roots=[str(root)])

    assert resolved == (root / "coding-agent-output" / "x.md").resolve()
    assert elsewhere.resolve() not in resolved.parents


def test_a_relative_path_that_climbs_out_of_the_root_is_still_rejected(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The containment check is what enforces the boundary, and D7 does not
    touch it. Anchoring at the root must not become a way to leave it."""
    root = tmp_path / "workspace"
    root.mkdir()

    with pytest.raises(SandboxViolation):
        resolve_within_roots("../../etc/passwd", allowed_roots=[str(root)])


def test_a_relative_path_anchors_at_the_first_root_and_does_not_search(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Pins the multi-root semantics rather than leaving them incidental.

    A relative path anchored at the first root is *necessarily* inside that
    root, so the first root always wins and the later ones are never
    consulted -- even when an entry of that name exists under a later root
    and not under the first. That is deliberate: picking the root that
    happens to contain an existing entry would make a pure scope check
    depend on filesystem state, so the same request could be admitted or
    refused depending on timing. Existence is the calling adapter's check.

    No built-in declares more than one root today, so this pins intended
    behaviour rather than describing a path any caller currently takes."""
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    (second / "nested").mkdir(parents=True)

    resolved = resolve_within_roots("nested", allowed_roots=[str(first), str(second)])

    assert resolved == (first / "nested").resolve()
    assert not resolved.exists()


def test_an_absolute_path_is_unaffected_by_the_relative_path_change(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Regression guard: D7 widened usability, not scope. An absolute path
    resolves exactly as it did before, inside the root and outside it."""
    root = tmp_path / "workspace"
    root.mkdir()
    inside = root / "file.txt"
    inside.write_text("x")

    assert resolve_within_roots(str(inside), allowed_roots=[str(root)]) == inside.resolve()
    with pytest.raises(SandboxViolation):
        resolve_within_roots("/etc/passwd", allowed_roots=[str(root)])


def test_the_violation_is_labelled_with_the_adapter_that_asked(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """`capability_sandbox_violation_blocked_total{adapter=...}` (TDD 3C
    §8/§9) is keyed on this label, so a blocked `terminal` working directory
    must not be counted as a `filesystem` violation."""
    root = tmp_path / "workspace"
    root.mkdir()

    with pytest.raises(SandboxViolation) as exc_info:
        resolve_within_roots("/etc", allowed_roots=[str(root)], adapter="terminal")
    assert exc_info.value.adapter == "terminal"

    with pytest.raises(SandboxViolation) as default_info:
        resolve_within_roots("/etc", allowed_roots=[str(root)])
    assert default_info.value.adapter == "filesystem"


def test_no_declared_roots_rejects_every_path() -> None:
    """An empty allow-list admits nothing -- the loop body never runs, and
    the failure path must still produce a well-formed violation."""
    with pytest.raises(SandboxViolation) as exc_info:
        resolve_within_roots("anything", allowed_roots=[])
    assert "anything" in str(exc_info.value)


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
