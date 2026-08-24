"""A real Event Bus round-trip through `main.py`'s served
`agent_os.supervisor.restart_plan.request` RPC (disclosed addition, see
`events/restart_plan_handler.py`'s own docstring) -- mirrors
`planning-engine`'s own `test_events_decompose_request.py` convention
exactly (the closest, most recent precedent for a served request/reply RPC
in this codebase).

`app.state.bus`'s own `publishable_subjects` deliberately do not include
this subject -- Supervisors only ever *serves* it, never calls it on
itself. A second `BoundEventBus`, wrapping the exact same underlying
in-memory bus instance, stands in for the real external caller
(`agent-os/kernel`'s own Scheduler).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from nova_agent_os_supervisors.config import Settings
from nova_agent_os_supervisors.main import create_app
from nova_contracts import (
    AgentOsRestartPlanReplyPayload,
    AgentOsRestartPlanRequestPayload,
    SupervisedInstanceSnapshot,
)
from nova_eventbus_sdk import BoundEventBus


def _caller_bus(app):  # type: ignore[no-untyped-def]
    return BoundEventBus(
        app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
        engine_name="test-caller-engine",
        publishable_subjects=frozenset({"agent_os.supervisor.restart_plan.request"}),
        subscribable_subjects=frozenset(),
    )


async def test_restart_plan_one_for_one_restarts_only_the_failed_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings())
    failed_id = uuid4()
    sibling_id = uuid4()

    async with app.router.lifespan_context(app):
        caller_bus = _caller_bus(app)
        request = AgentOsRestartPlanRequestPayload(
            failed_instance_id=failed_id,
            restart_strategy="one_for_one",
            siblings=[
                SupervisedInstanceSnapshot(
                    id=failed_id,
                    category="research",
                    restart_strategy="one_for_one",
                    started_order=0,
                    status="failed",
                ),
                SupervisedInstanceSnapshot(
                    id=sibling_id,
                    category="research",
                    restart_strategy="one_for_one",
                    started_order=1,
                    status="running",
                ),
            ],
            requesting_engine="test-caller-engine",
            correlation_id=uuid4(),
        )
        reply_envelope = await caller_bus.request(
            "agent_os.supervisor.restart_plan.request",
            request,
            source_engine="test-caller-engine",
        )
        result = AgentOsRestartPlanReplyPayload.model_validate(reply_envelope.payload)

    assert result.restart_instance_ids == [failed_id]


async def test_restart_plan_one_for_all_restarts_every_running_sibling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings())
    failed_id = uuid4()
    sibling_id = uuid4()
    completed_id = uuid4()

    async with app.router.lifespan_context(app):
        caller_bus = _caller_bus(app)
        request = AgentOsRestartPlanRequestPayload(
            failed_instance_id=failed_id,
            restart_strategy="one_for_all",
            siblings=[
                SupervisedInstanceSnapshot(
                    id=failed_id,
                    category="coding",
                    restart_strategy="one_for_all",
                    started_order=0,
                    status="failed",
                ),
                SupervisedInstanceSnapshot(
                    id=sibling_id,
                    category="coding",
                    restart_strategy="one_for_all",
                    started_order=1,
                    status="running",
                ),
                SupervisedInstanceSnapshot(
                    id=completed_id,
                    category="coding",
                    restart_strategy="one_for_all",
                    started_order=2,
                    status="completed",
                ),
            ],
            requesting_engine="test-caller-engine",
            correlation_id=uuid4(),
        )
        reply_envelope = await caller_bus.request(
            "agent_os.supervisor.restart_plan.request",
            request,
            source_engine="test-caller-engine",
        )
        result = AgentOsRestartPlanReplyPayload.model_validate(reply_envelope.payload)

    assert result.restart_instance_ids == [failed_id, sibling_id]
