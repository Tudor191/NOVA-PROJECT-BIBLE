"""Scheduling-time version selection (TDD 3E §14 acceptance criterion #3,
doc 12 §6's "the Kernel Scheduler selects a version per policy
(latest-stable by default)") -- pure functions over already-fetched
`AgentPackage` rows, kept separate from `events/find_healthy_package_handler.py`
so the policy itself is unit-testable without a repository or an Event Bus.
The full design decision and its scope boundary are recorded in
`docs/design/phase-3/16-3e-hot-load-design-decision.md`.

**This is version pinning and scheduling hot-load, not simultaneous
execution of different bytecode versions** (doc 16 §2). Phase 3's
`inprocess` backend resolves handler code by category alone
(`agents/<manifest id>/src/handler.py` -- one file per package, no
per-version directory exists) and runs an instance's entire lifecycle
synchronously inside `spawn()`, so two code bodies for one category can
never execute concurrently in Phase 3. What this module makes possible is
the part criterion #3 actually turns on: a *new* dispatch resolving to the
newest healthy `agent_package` row, while every already-dispatched
`agent_instance` stays permanently pinned to the exact row UUID it was
dispatched against.

Policy, as approved (doc 16 §3):
- Only `health_status == "healthy"` is selectable. `"degraded"`,
  `"unhealthy"`, and `"unknown"` are all non-selectable, with no invented
  `degraded` fallback semantics -- nothing in this codebase produces
  `"degraded"` today (`domain/pipeline.py` writes only `"unknown"` at
  Registration and `"healthy"` after a successful `on_load`).
- Among healthy rows, the **highest version** wins, compared as a
  dotted-integer tuple -- deliberately **not** `installed_at`, so a
  rollback re-install of an older version cannot out-rank a newer one
  merely by being installed more recently.
- No healthy row -> `None`.

Distinct from `RegistryRepository.find_latest_by_category`, which means
"most recently *installed*" and answers Permission Review's own,
different question (diff a new install's `required_permissions` against
its predecessor, TDD 3E §5). The two are separate concerns and stay
separate.
"""

from __future__ import annotations

from nova_agent_os_registry.domain.models import AgentPackage

__all__ = ["SELECTABLE_HEALTH_STATUSES", "select_dispatch_version", "version_sort_key"]

SELECTABLE_HEALTH_STATUSES: frozenset[str] = frozenset({"healthy"})


def version_sort_key(version: str) -> tuple[int, ...]:
    """Dotted-integer comparison, e.g. `"1.10.0"` -> `(1, 10, 0)` --
    identical semantics to `domain/pipeline.py::_version_tuple`, which
    already establishes this exact comparison for
    `compatibility.min_kernel_version` checks. Deliberately not a full
    semver parser (no pre-release/build-metadata handling): every version
    this project has ever assigned is a plain `MAJOR.MINOR.PATCH` string,
    and doc 12/TDD 3E name no richer version grammar.

    A version string that is not dotted integers sorts lowest rather than
    raising -- a malformed version must never make an entire category
    undispatchable, and Manifest Validation (pipeline stage 3) is the
    place that would reject one at install time.
    """
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError:
        return ()


def select_dispatch_version(packages: list[AgentPackage]) -> AgentPackage | None:
    """The highest-versioned healthy package among `packages`, or `None`
    if none is healthy. Callers pass every row for one category (see
    `RegistryRepository.list_by_category`); this function does not filter
    by category itself."""
    healthy = [p for p in packages if p.health_status in SELECTABLE_HEALTH_STATUSES]
    if not healthy:
        return None
    return max(healthy, key=lambda p: version_sort_key(p.version))
