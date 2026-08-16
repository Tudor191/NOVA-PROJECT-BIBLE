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


def resolve_within_roots(path: str, *, allowed_roots: list[str]) -> Path:
    """TDD 3C §3's `filesystem` row: path-prefix allow-list validated
    against the **canonicalized/resolved** path (not the raw string), so a
    `../`-traversal or a symlink resolving outside every declared root is
    rejected, not merely a naive string-prefix comparison."""
    resolved = Path(path).resolve()
    for root in allowed_roots:
        resolved_root = Path(root).resolve()
        if resolved == resolved_root or resolved_root in resolved.parents:
            return resolved
    raise SandboxViolation(
        f"path {path!r} (resolved: {resolved}) is outside every declared "
        f"root {allowed_roots!r}",
        adapter="filesystem",
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
