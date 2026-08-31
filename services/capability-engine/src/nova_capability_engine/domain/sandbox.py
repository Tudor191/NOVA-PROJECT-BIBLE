"""OS-level sandboxing primitives (TDD 3C §3, Fork E3's approved lighter
scoping, made concrete) -- shared building blocks the four adapters compose,
not a fourth, independent mechanism. Framework-free (docs/architecture/
03-backend-architecture.md §1): no subprocess/filesystem/network I/O lives
here, only the scope-checking logic every adapter calls before it acts.

Deliberately not gVisor/Firecracker/container/subprocess/remote-execution
isolation (Fork E3's already-approved resolution, not reopened here) --
lighter OS-level permission/resource scoping only.

Known, disclosed limitation (TDD 3C §3): none of these primitives prevent a
`terminal`/`git` capability's own spawned subprocess from making its own
outbound network calls, bypassing the `http` adapter's host allow-list
entirely. Closing that fully would require process-level network isolation
(network namespaces/firewall rules) -- a heavier mechanism than Fork E3's
approved lighter scoping, so it is not implemented here; a real but
narrower security boundary than the Bible's eventual vision, disclosed, not
silently implied to be full isolation.
"""

from __future__ import annotations

from pathlib import Path

__all__ = [
    "SandboxViolation",
    "check_executable_allowed",
    "check_host_allowed",
    "resolve_within_roots",
]


class SandboxViolation(Exception):
    """Raised by any adapter when an operation would escape its declared
    scope. Never silently caught and downgraded to a generic failure --
    capability-engine's own invoke handler converts this into
    `CapabilityInvokeOutcome == "sandbox_violation"`, logs it, and
    increments `capability_sandbox_violation_blocked_total{adapter=...}`
    (TDD 3C §8/§9): a blocked attempt is not evidence of an unhealthy
    capability, `health_status` is unaffected."""

    def __init__(self, message: str, *, adapter: str) -> None:
        super().__init__(message)
        self.adapter = adapter


def resolve_within_roots(
    path: str, *, allowed_roots: list[str], adapter: str = "filesystem"
) -> Path:
    """TDD 3C §3's `filesystem` row: path-prefix allow-list validated
    against the **canonicalized/resolved** path (not the raw string), so a
    `../`-traversal or a symlink resolving outside every declared root is
    rejected, not merely a naive string-prefix comparison.

    **A relative path is resolved against the declared root, never against
    the process's current working directory.** `Path(path).resolve()` alone
    anchors a relative path at `Path.cwd()` -- whatever directory
    `capability-engine`'s own process happens to have been started in --
    which has nothing to do with the sandbox and is not a location any
    caller can reason about. Every real caller sends a project-relative
    path (`coding-agent`'s own `f"coding-agent-output/{task.id}.md"` is the
    concrete case), so under cwd-anchoring every such write resolved
    outside the declared root and was rejected as a sandbox violation --
    the capability was unusable for its actual purpose.

    Anchoring at the root is strictly a *widening of usability, not of
    scope*: the containment check below is unchanged, and it is what
    enforces the boundary. A relative path that climbs back out
    (`"../../etc/passwd"`) still resolves outside the root and is still
    rejected, exactly as an absolute path outside the root is. Absolute
    paths behave identically to before -- they are resolved as given.

    With several `allowed_roots`, each is tried in order and the first that
    contains the resolved path wins. For an **absolute** path that means the
    root it actually lives under. For a **relative** path it always means the
    *first* root, since anchoring it there necessarily puts it inside there
    -- relative paths do not search the remaining roots, and this function
    deliberately does not consult the filesystem to pick a root that happens
    to contain an existing entry: whether a path exists is the calling
    adapter's business (`FilesystemAdapter` checks `is_file()`/`is_dir()`
    itself), and making a scope check depend on filesystem state would make
    the same request admissible or not depending on timing.

    In practice the question does not arise: every built-in declares exactly
    one root (`domain/builtin_capabilities.py` builds `[filesystem_root]`).

    `adapter` labels the `SandboxViolation` this raises, which is what
    `capability_sandbox_violation_blocked_total{adapter=...}` is keyed on
    (TDD 3C §8/§9). It defaults to `"filesystem"` -- the path-scoping
    adapter this primitive was written for -- and is passed explicitly by
    other adapters that scope a path, so a blocked `terminal` working
    directory is not miscounted as a filesystem violation."""
    candidate = Path(path)
    for root in allowed_roots:
        resolved_root = Path(root).resolve()
        resolved = (
            candidate.resolve()
            if candidate.is_absolute()
            else (resolved_root / candidate).resolve()
        )
        if resolved == resolved_root or resolved_root in resolved.parents:
            return resolved
    raise SandboxViolation(
        f"path {path!r} is outside every declared root {allowed_roots!r}",
        adapter=adapter,
    )


def check_executable_allowed(executable: str, *, allowed_executables: list[str]) -> None:
    """TDD 3C §3's `terminal` row: only explicitly declared binaries."""
    if executable not in allowed_executables:
        raise SandboxViolation(
            f"executable {executable!r} is not on the declared allow-list "
            f"{allowed_executables!r}",
            adapter="terminal",
        )


def check_host_allowed(host: str, *, allowed_hosts: list[str]) -> None:
    """TDD 3C §3's `http` row: outbound-host allow-list, declared domains
    only."""
    if host not in allowed_hosts:
        raise SandboxViolation(
            f"host {host!r} is not on the declared allow-list {allowed_hosts!r}",
            adapter="http",
        )
