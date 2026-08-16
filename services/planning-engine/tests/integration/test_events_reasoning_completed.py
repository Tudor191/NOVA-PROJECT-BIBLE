"""`reasoning.process.completed` subscribed handler
(`events/handlers.py::make_reasoning_process_completed_handler`) --
integration-level: a real `create_app()` against a real (in-memory)
`EventBus`, with only the model-orchestration boundary faked. Mirrors
`digital-twin-engine`'s own `tests/integration/test_events_session_completed.py`
pattern.

**Verification tier (Part 17): local integration verified, not
real-infrastructure verified.** The in-memory `EventBus` implements the
same `EventBus` Protocol NATS does, so this proves the subscribe/handler/
allow-list wiring is correct -- it is not proof against real NATS
JetStream redelivery/consumer-group behavior. See this unit's Gate Review
for why a real-NATS test was not added (no engine in this codebase uses
the `nats_event_bus` testkit fixture for a subject-subscription proof
yet -- establishing that pattern for the first time is out of this PR's
scope)."""

from __future__ import annotations

from uuid import uuid4

from nova_contracts import (
    EventEnvelope,
    GenerateReplyPayload,
    ReasoningMode,
    ReasoningOutcome,
    ReasoningProcessCompletedPayload,
    ToolCallPayload,
)
from nova_planning_engine.config import Settings
from nova_planning_engine.events.handlers import make_reasoning_process_completed_handler
from nova_planning_engine.main import create_app

from tests.fakes.ports import FakeModelOrchestrationPort

_TOOL_NAME = "propose_task_graph"


def _payload(*, confidence_score: float) -> ReasoningProcessCompletedPayload:
    return ReasoningProcessCompletedPayload(
        reasoning_process_id=uuid4(),
        correlation_id=uuid4(),
        requesting_engine="reasoning-engine",
        user_id=uuid4(),
        reasoning_mode=ReasoningMode.ANALYTICAL,
        reasoning_level=1,
        confidence_score=confidence_score,
        execution_duration_ms=42.0,
        outcome=ReasoningOutcome.DECIDED,
        objective_text="Ship the release",
        chosen_description="Ship it incrementally",
    )


def _envelope(payload: ReasoningProcessCompletedPayload) -> EventEnvelope:
    return EventEnvelope(
        subject="reasoning.process.completed",
        source_engine="reasoning-engine",
        correlation_id=payload.correlation_id,
        payload=payload.model_dump(mode="json"),
    )


def _structured_reply() -> GenerateReplyPayload:
    return GenerateReplyPayload(
        text="",
        tool_calls=[
            ToolCallPayload(
                id="call_0",
                tool_name=_TOOL_NAME,
                arguments={
                    "tasks": [
                        {
                            "local_id": "a",
                            "objective": "Do the thing",
                            "depends_on": [],
                            "effort_hours": 2.0,
                            "confidence": 0.7,
                            "risk": "low",
                        }
                    ]
                },
            )
        ],
        input_tokens=10,
        output_tokens=10,
        finish_reason="tool_calls",
        structural_confidence=0.9,
        model_id=uuid4(),
        provider="fake",
    )


async def test_below_threshold_reasoning_completion_skips_decomposition(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    port = FakeModelOrchestrationPort()
    settings = Settings(decomposition_confidence_threshold=0.6)
    app = create_app(settings, model_orchestration_port=port)

    async with app.router.lifespan_context(app):
        handler = make_reasoning_process_completed_handler(app)
        await handler(_envelope(_payload(confidence_score=0.2)))

    assert port.requests == []


async def test_above_threshold_reasoning_completion_triggers_decomposition(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    port = FakeModelOrchestrationPort(reply=_structured_reply())
    settings = Settings(decomposition_confidence_threshold=0.6)
    app = create_app(settings, model_orchestration_port=port)

    async with app.router.lifespan_context(app):
        handler = make_reasoning_process_completed_handler(app)
        payload = _payload(confidence_score=0.9)
        await handler(_envelope(payload))

    assert len(port.requests) == 1
    sent = port.requests[0]
    assert sent.requesting_engine == "planning-engine"
    assert sent.correlation_id == payload.correlation_id
    texts = [c.text for c in sent.context]
    assert "Ship the release" in texts


async def test_model_error_during_decomposition_does_not_raise(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    port = FakeModelOrchestrationPort(
        reply=GenerateReplyPayload(
            text="",
            input_tokens=0,
            output_tokens=0,
            finish_reason="error",
            structural_confidence=0.0,
            model_id=uuid4(),
            provider="fake",
            error="provider unavailable",
        )
    )
    settings = Settings(decomposition_confidence_threshold=0.6)
    app = create_app(settings, model_orchestration_port=port)

    async with app.router.lifespan_context(app):
        handler = make_reasoning_process_completed_handler(app)
        # Must not raise -- an expected, defined decomposition failure is
        # handled gracefully, never left to crash the event handler / trigger
        # NATS redelivery (Part 14).
        await handler(_envelope(_payload(confidence_score=0.9)))

    assert len(port.requests) == 1


async def test_subscribing_via_the_real_event_bus_invokes_the_handler(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """Proves `main.py`'s own `bus.subscribe("reasoning.process.completed", ...)`
    wiring -- not calling the handler function directly, but publishing onto
    the same in-memory `EventBus` the app connected to, and letting real
    subject-matching dispatch to the registered handler.

    Publishes via the underlying raw `EventBus`, not `app.state.bus`
    (a `BoundEventBus`) -- `reasoning.process.completed` is correctly absent
    from planning-engine's own `publishable_subjects` (it consumes this
    event, never publishes it); in the real system the publisher is
    `reasoning-engine`'s own, differently-scoped `BoundEventBus`. The
    in-memory backend's `publish()` awaits every matching subscriber's
    handler directly (`backends/in_memory.py`), so no polling wait is
    needed -- by the time `publish()` returns, the handler has already run.
    """
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    port = FakeModelOrchestrationPort(reply=_structured_reply())
    settings = Settings(decomposition_confidence_threshold=0.6)
    app = create_app(settings, model_orchestration_port=port)

    async with app.router.lifespan_context(app):
        payload = _payload(confidence_score=0.9)
        raw_bus = app.state.bus._bus
        await raw_bus.publish(_envelope(payload))

    assert len(port.requests) == 1
    assert port.requests[0].correlation_id == payload.correlation_id
