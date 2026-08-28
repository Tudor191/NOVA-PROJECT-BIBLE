"""`agent_os.registry.find_healthy_package.request` RPC handler -- serves
the Kernel Scheduler's own "query Registry for healthy candidates in the
required category" step (TDD 3E §4). Disclosed addition: TDD 3E §5 named no
RPC surface for Registry at all (filesystem-discovery- and startup-driven
only); this is the smallest wire shape closing that gap, per
`nova_contracts.events.agent_os`'s own module docstring.

**Hot-load version selection (TDD 3E §14 acceptance criterion #3, approved
2026-08-28 -- full record in `docs/design/phase-3/
16-3e-hot-load-design-decision.md`).** Reads every installed row for the
category (`list_by_category`) and applies `domain/selection.py::
select_dispatch_version`: the **highest healthy version** by dotted-integer
comparison, falling back to the highest healthy *older* version when the
newest one is not healthy. This replaces this handler's own original
`find_latest_by_category` + health-check implementation, which had a real
defect under multi-version coexistence: with `1.2.0` freshly installed but
still `"unknown"` (its `on_load` failed) and `1.1.0` still `"healthy"`,
that shape returned `None` -- reporting "no healthy package" for a category
that demonstrably had one, making the whole category undispatchable on a
bad upgrade instead of falling back.

`find_latest_by_category` remains in use, unchanged, by the install
pipeline's own Permission Review stage -- "most recently installed" is the
right question there (diff a new install's `required_permissions` against
its predecessor, TDD 3E §5) and a deliberately different one from "which
version should a new dispatch use" (doc 16 §3).
"""

from __future__ import annotations

from fastapi import FastAPI
from nova_contracts import (
    AgentOsFindHealthyPackageReplyPayload,
    AgentOsFindHealthyPackageRequestPayload,
    AgentPackageSnapshot,
    EventEnvelope,
)

from nova_agent_os_registry.domain.selection import select_dispatch_version

__all__ = ["make_find_healthy_package_handler"]


def make_find_healthy_package_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> AgentOsFindHealthyPackageReplyPayload:
        state = app.state
        payload = AgentOsFindHealthyPackageRequestPayload.model_validate(envelope.payload)

        installed = await state.repository.list_by_category(payload.category)
        selected = select_dispatch_version(installed)
        if selected is None:
            return AgentOsFindHealthyPackageReplyPayload(package=None)

        return AgentOsFindHealthyPackageReplyPayload(
            package=AgentPackageSnapshot(
                id=selected.id,
                category=selected.category,
                version=selected.version,
                manifest_json=selected.manifest_json,
                health_status=selected.health_status,
            )
        )

    return handle
