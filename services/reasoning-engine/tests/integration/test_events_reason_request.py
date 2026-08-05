"""A real Event Bus round-trip through `events/handlers.py`'s served
`reasoning.reason.request` RPC (docs/design/phase-2b/00-reasoning-engine.md
§23) -- every other test exercises this engine's pipeline only via
`api/reason.py`'s HTTP path; this is the one place `make_reason_request_handler`
itself, registered by `create_app`'s `bus.serve(...)` call, is actually invoked
through a subscription rather than called as a bare Python function.

`app.state.bus` is this engine's own `BoundEventBus`, whose `publishable_subjects`
(`events/published.py`) deliberately do not include `reasoning.reason.request`
-- this engine only ever *serves* that subject, never calls it on itself. A
second `BoundEventBus`, wrapping the exact same underlying in-memory bus
instance, stands in for the kind of external caller (a future Planning Engine,
§7.1) whose own `published.py` would legitimately list it.
"""

from __future__ import annotations

from uuid import uuid4

from nova_contracts import ReasoningReplyPayload, ReasoningRequestPayload
from nova_eventbus_sdk import BoundEventBus
from nova_reasoning_engine.config import Settings
from nova_reasoning_engine.domain.models import KnowledgeReference
from nova_reasoning_engine.main import create_app

from tests.fakes.ports import (
    FakeGoalsPort,
    FakeKnowledgePort,
    FakeMemoryPort,
    FakeModelOrchestrationPort,
    FakePersonalContextPort,
    FakeWorldModelPort,
)
from tests.fakes.repository import FakeReasoningRepository


async def test_reason_request_rpc_round_trips_through_the_real_event_bus(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    knowledge_port = FakeKnowledgePort(
        [KnowledgeReference(node_id="n1", name="Paris", layer="verified", confidence=0.9)]
    )
    repository = FakeReasoningRepository()
    app = create_app(
        Settings(),
        memory_port=FakeMemoryPort(),
        knowledge_port=knowledge_port,
        world_model_port=FakeWorldModelPort(),
        personal_context_port=FakePersonalContextPort(),
        goals_port=FakeGoalsPort(),
        model_orchestration_port=FakeModelOrchestrationPort(),
        repository=repository,
    )

    async with app.router.lifespan_context(app):
        caller_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
            engine_name="test-caller-engine",
            publishable_subjects=frozenset({"reasoning.reason.request"}),
            subscribable_subjects=frozenset(),
        )
        reply_envelope = await caller_bus.request(
            "reasoning.reason.request",
            ReasoningRequestPayload(
                objective_text="what is the capital of France?",
                user_id=uuid4(),
                requesting_engine="test-caller-engine",
                reasoning_mode_hint="reactive",
            ),
            source_engine="test-caller-engine",
        )

    reply = ReasoningReplyPayload.model_validate(reply_envelope.payload)
    assert reply.outcome == "decided"
    assert reply.chosen_description == "Paris"
    assert repository.decisions  # the handler actually ran the pipeline, not a stub reply
