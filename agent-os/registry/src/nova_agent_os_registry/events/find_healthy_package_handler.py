"""`agent_os.registry.find_healthy_package.request` RPC handler -- serves
the Kernel Scheduler's own "query Registry for healthy candidates in the
required category" step (TDD 3E §4). Disclosed addition: TDD 3E §5 named no
RPC surface for Registry at all (filesystem-discovery- and startup-driven
only); this is the smallest wire shape closing that gap, per
`nova_contracts.events.agent_os`'s own module docstring.

Reuses the existing `find_latest_by_category` repository port method
(Milestone 3, corrected per `docs/design/phase-3/
15-3e-supervisor-reconciliation.md` §A) directly -- no new persistence
logic. "Healthy candidates," scoped to Phase 3's one-supported-version-per-
category reality, resolves to "the most recently installed row with
`health_status == 'healthy'`," not a list requiring a separate scoring step
here (Kernel's own future multi-candidate scoring, doc 12 §7 step 2, has
nothing to score against until a second healthy version of one category
actually coexists -- Phase 3 ships exactly one).
"""

from __future__ import annotations

from fastapi import FastAPI
from nova_contracts import (
    AgentOsFindHealthyPackageReplyPayload,
    AgentOsFindHealthyPackageRequestPayload,
    AgentPackageSnapshot,
    EventEnvelope,
)

__all__ = ["make_find_healthy_package_handler"]


def make_find_healthy_package_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> AgentOsFindHealthyPackageReplyPayload:
        state = app.state
        payload = AgentOsFindHealthyPackageRequestPayload.model_validate(envelope.payload)

        found = await state.repository.find_latest_by_category(payload.category)
        if found is None or found.health_status != "healthy":
            return AgentOsFindHealthyPackageReplyPayload(package=None)

        return AgentOsFindHealthyPackageReplyPayload(
            package=AgentPackageSnapshot(
                id=found.id,
                category=found.category,
                version=found.version,
                manifest_json=found.manifest_json,
                health_status=found.health_status,
            )
        )

    return handle
