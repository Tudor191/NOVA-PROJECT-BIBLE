"""`agent_os.registry.list_packages.request` RPC handler -- disclosed
addition, Phase 4C milestone 4C.2a (approved 2026-09-08).

Answers "what Agent Packages are registered" with every installed row, so
`agent-os/kernel` can serve `GET /v1/agents` (decision D-4, master scope §9)
without reading `agent_package` -- Registry's own table -- directly. See
`nova_contracts.events.agent_os`'s `AgentOsListPackagesRequestPayload`
docstring for the full disclosure of why this is a second RPC rather than a
widened `find_healthy_package`.

**No policy is applied here.** `find_healthy_package` exists to *choose*,
and runs `domain/selection.py::select_dispatch_version` to do it; this
handler exists to *report*, and deliberately returns unhealthy and
superseded versions too. A listing that silently hid the `1.2.0` whose
`on_load` failed would misrepresent what is installed at exactly the moment
an operator most needs to see it -- which is the same failure mode
`select_dispatch_version` was written to fix on the dispatch side, in the
opposite direction.

**Ordering comes from the repository**, not from this handler: `list_all()`
orders in SQL (`domain/ports.py` states the contract and why it is not a
semantic version order), so every caller sees the same sequence without
re-sorting.
"""

from __future__ import annotations

from fastapi import FastAPI
from nova_contracts import (
    AgentOsListPackagesReplyPayload,
    AgentOsListPackagesRequestPayload,
    AgentPackageSnapshot,
    EventEnvelope,
)

__all__ = ["make_list_packages_handler"]


def make_list_packages_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> AgentOsListPackagesReplyPayload:
        state = app.state
        # Validated even though no field is read: a malformed request must
        # fail as a contract violation rather than being answered anyway,
        # the same discipline `find_healthy_package_handler` applies.
        AgentOsListPackagesRequestPayload.model_validate(envelope.payload)

        installed = await state.repository.list_all()

        # The same five-field projection `find_healthy_package_handler`
        # builds. Deliberately not extracted into a shared helper in this
        # slice: doing so would edit the existing dispatch handler, which
        # 4C.2a is meant to leave untouched and prove unchanged by
        # regression test. If a third caller appears, extract it then.
        return AgentOsListPackagesReplyPayload(
            packages=[
                AgentPackageSnapshot(
                    id=package.id,
                    category=package.category,
                    version=package.version,
                    manifest_json=package.manifest_json,
                    health_status=package.health_status,
                )
                for package in installed
            ]
        )

    return handle
