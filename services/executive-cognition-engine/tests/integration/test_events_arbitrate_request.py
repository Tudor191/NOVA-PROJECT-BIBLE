"""A real Event Bus round-trip through `events/handlers.py`'s served
`executive.arbitrate.request` and `executive.outcome.report` RPCs (docs/
design/phase-2c/00-executive-cognition-engine.md §23) -- every other test
exercises this engine's coordination pipeline only via `api/arbitrate.py`'s
HTTP path; this is the one place the handlers themselves, registered by
`create_app`'s `bus.serve(...)` calls, are actually invoked through a
subscription rather than called as a bare Python function.

`app.state.bus` is this engine's own `BoundEventBus`, whose
`publishable_subjects` (`events/published.py`) deliberately do not include
`executive.arbitrate.request` -- this engine only ever *serves* that
subject, never calls it on itself. A second `BoundEventBus`, wrapping the
exact same underlying in-memory bus instance, stands in for the kind of
external caller (Reasoning Engine, AI Model Orchestration Engine) whose own
`published.py` would legitimately list it.
"""

from __future__ import annotations

from uuid import uuid4

from nova_contracts import (
    ExecutiveArbitrateReplyPayload,
    ExecutiveOutcomeReportPayload,
    ExecutiveOutcomeReportReplyPayload,
    ExecutiveRequestPayload,
)
from nova_eventbus_sdk import BoundEventBus
from nova_executive_cognition_engine.config import Settings
from nova_executive_cognition_engine.main import create_app

from tests.fakes.ports import FakeGoalsPort
from tests.fakes.repository import FakeExecutiveRepository


async def test_arbitrate_request_rpc_round_trips_through_the_real_event_bus(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeExecutiveRepository()
    app = create_app(Settings(), goals_port=FakeGoalsPort(), repository=repository)

    async with app.router.lifespan_context(app):
        caller_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
            engine_name="test-caller-engine",
            publishable_subjects=frozenset(
                {"executive.arbitrate.request", "executive.outcome.report"}
            ),
            subscribable_subjects=frozenset(),
        )
        correlation_id = uuid4()
        reply_envelope = await caller_bus.request(
            "executive.arbitrate.request",
            ExecutiveRequestPayload(
                requesting_engine="test-caller-engine",
                request_kind="reasoning_process",
                user_id=uuid4(),
                correlation_id=correlation_id,
                urgency=0.5,
                importance=0.5,
                complexity=0.5,
                risk=0.5,
                learning_value=0.5,
                resource_cost=0.5,
                user_impact=0.5,
            ),
            source_engine="test-caller-engine",
        )
        reply = ExecutiveArbitrateReplyPayload.model_validate(reply_envelope.payload)
        assert reply.outcome == "proceed"
        assert repository.requests  # the handler actually ran, not a stub reply

        outcome_reply_envelope = await caller_bus.request(
            "executive.outcome.report",
            ExecutiveOutcomeReportPayload(
                correlation_id=correlation_id, outcome="succeeded", actual_duration_ms=123.4
            ),
            source_engine="test-caller-engine",
        )
        outcome_reply = ExecutiveOutcomeReportReplyPayload.model_validate(
            outcome_reply_envelope.payload
        )
        assert outcome_reply.acknowledged
        assert repository.outcome_reports == [(correlation_id, "succeeded", 123.4, None)]
