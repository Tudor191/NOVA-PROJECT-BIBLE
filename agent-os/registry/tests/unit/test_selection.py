"""Unit tests for `domain/selection.py` -- the hot-load version-selection
policy (TDD 3E §14 acceptance criterion #3; full design record in
`docs/design/phase-3/16-3e-hot-load-design-decision.md`). Pure functions
over already-fetched `AgentPackage` rows, no repository or Event Bus
involved."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from nova_agent_os_registry.domain.models import AgentPackage
from nova_agent_os_registry.domain.selection import (
    SELECTABLE_HEALTH_STATUSES,
    select_dispatch_version,
    version_sort_key,
)

_BASE_INSTALLED_AT = datetime(2026, 8, 28, 12, 0, 0, tzinfo=UTC)


def _package(
    *,
    version: str,
    health_status: str = "healthy",
    category: str = "coding",
    installed_at: datetime | None = None,
) -> AgentPackage:
    return AgentPackage(
        id=uuid4(),
        category=category,
        version=version,
        manifest_json={"id": "coding-agent", "category": category, "version": version},
        installed_at=installed_at or _BASE_INSTALLED_AT,
        health_status=health_status,  # type: ignore[arg-type]
        checksum="deadbeef",
    )


def test_only_healthy_is_selectable() -> None:
    """Approved policy (doc 16 §3): no invented `degraded` fallback."""
    assert frozenset({"healthy"}) == SELECTABLE_HEALTH_STATUSES


def test_version_sort_key_compares_numerically_not_lexically() -> None:
    """`"1.10.0"` must out-rank `"1.9.0"` -- a plain string comparison
    would get this backwards."""
    assert version_sort_key("1.10.0") > version_sort_key("1.9.0")
    assert version_sort_key("1.2.0") > version_sort_key("1.1.0")
    assert version_sort_key("2.0.0") > version_sort_key("1.99.99")


def test_version_sort_key_sorts_a_malformed_version_lowest_without_raising() -> None:
    """A malformed version must never make an entire category
    undispatchable (module docstring's own disclosed behavior)."""
    assert version_sort_key("not-a-version") == ()
    assert version_sort_key("1.0.0") > version_sort_key("not-a-version")


def test_selects_the_highest_healthy_version() -> None:
    older = _package(version="1.1.0")
    newer = _package(version="1.2.0")
    selected = select_dispatch_version([older, newer])
    assert selected is not None
    assert selected.version == "1.2.0"
    assert selected.id == newer.id


def test_selection_is_independent_of_list_order() -> None:
    older = _package(version="1.1.0")
    newer = _package(version="1.2.0")
    assert select_dispatch_version([newer, older]) == select_dispatch_version([older, newer])


def test_falls_back_to_the_highest_healthy_older_version() -> None:
    """The real defect this slice fixes: 1.2.0 installed but its `on_load`
    failed (health still `"unknown"`), 1.1.0 still healthy -- the category
    must stay dispatchable on 1.1.0, never report "no healthy package"."""
    healthy_older = _package(version="1.1.0", health_status="healthy")
    unknown_newer = _package(version="1.2.0", health_status="unknown")
    selected = select_dispatch_version([healthy_older, unknown_newer])
    assert selected is not None
    assert selected.version == "1.1.0"


def test_falls_back_past_multiple_unhealthy_newer_versions() -> None:
    selected = select_dispatch_version(
        [
            _package(version="1.1.0", health_status="healthy"),
            _package(version="1.2.0", health_status="unknown"),
            _package(version="1.3.0", health_status="unhealthy"),
            _package(version="1.4.0", health_status="degraded"),
        ]
    )
    assert selected is not None
    assert selected.version == "1.1.0"


def test_degraded_is_not_selectable() -> None:
    """Approved policy: `degraded` is non-selectable, with no fallback
    semantics of its own invented here."""
    assert select_dispatch_version([_package(version="1.1.0", health_status="degraded")]) is None


def test_unhealthy_is_not_selectable() -> None:
    assert select_dispatch_version([_package(version="1.1.0", health_status="unhealthy")]) is None


def test_unknown_is_not_selectable() -> None:
    assert select_dispatch_version([_package(version="1.1.0", health_status="unknown")]) is None


def test_no_healthy_version_returns_none() -> None:
    selected = select_dispatch_version(
        [
            _package(version="1.1.0", health_status="unknown"),
            _package(version="1.2.0", health_status="unhealthy"),
        ]
    )
    assert selected is None


def test_an_empty_list_returns_none() -> None:
    assert select_dispatch_version([]) is None


def test_version_wins_over_installed_at_ordering() -> None:
    """Approved policy (doc 16 §3): compare by dotted-integer version, NOT
    by `installed_at` -- a rollback re-install of an older version must not
    out-rank a newer one merely by being installed more recently."""
    newer_version_installed_earlier = _package(
        version="1.2.0", installed_at=_BASE_INSTALLED_AT
    )
    older_version_installed_later = _package(
        version="1.1.0", installed_at=_BASE_INSTALLED_AT + timedelta(hours=1)
    )
    selected = select_dispatch_version(
        [newer_version_installed_earlier, older_version_installed_later]
    )
    assert selected is not None
    assert selected.version == "1.2.0"
