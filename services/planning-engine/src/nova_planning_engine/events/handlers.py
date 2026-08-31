"""`reasoning.process.completed` subscribed handler (docs/design/phase-3/
05-tdd-3b-planning-engine.md §6.1) -- this engine's one real decomposition
path today: consumes a completed, sufficiently-confident reasoning result
and produces a validated `TaskGraph` via `domain/decomposition.py`.

Fire-and-forget subscription (`bus.subscribe`, not `bus.serve`) -- there is
no reply channel; a caller publishing `reasoning.process.completed` never
waits on this engine. Below-threshold and failed decompositions are
handled gracefully (logged, metriced, event considered processed) rather
than raised -- an unhandled exception here would trigger NATS JetStream
redelivery of the same event, which would not make a permanently-invalid
model response any more valid (mirrors `reasoning-engine`'s own
`HypothesisGenerationError` handling: caught deep inside the domain layer,
routed to a defined failure outcome, never left to crash the caller).

**Persists and enqueues `planning.task_graph.created` for publication**
(`phase-3b-planning-persistence` precursor, TDD 3B §4/§6.2) --
`reasoning.process.completed` always produces a brand-new `TaskGraph`
(never merges into an existing one; see
`docs/design/phase-3/14-3e-agent-os-research.md`'s own note on why no
`reasoning_process_id`-to-`task_graph_id` linkage exists). The outbox row
is written in the same transaction as the `task_graph`/`task_node` rows
(`PlanningRepository.insert`); the separate outbox worker
(`workers/outbox_worker.py`) is what actually publishes it onto the Event
Bus, decoupling this handler's own success from Event Bus availability.

Never logs `objective_text`/`chosen_description`/`TaskNode.objective`
content -- `PrivacyLevel` propagation for this data remains deferred
(Part 21); only IDs, counts, and outcome labels are logged.
"""

from __future__ import annotations

import time

from fastapi import FastAPI
from nova_contracts import EventEnvelope, ReasoningProcessCompletedPayload
from nova_observability import get_logger

from nova_planning_engine.domain.decomposition import DecompositionError, decompose
from nova_planning_engine.domain.ports import OutboxEvent
from nova_planning_engine.events.snapshot import task_graph_created_payload

__all__ = ["make_reasoning_process_completed_handler"]

logger = get_logger("planning-engine.events.handlers")

_SOURCE_ENGINE = "planning-engine"


def make_reasoning_process_completed_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> None:
        state = app.state
        payload = ReasoningProcessCompletedPayload.model_validate(envelope.payload)
        state.metrics.reasoning_completions_received_total.add(1)

        if payload.confidence_score < state.settings.decomposition_confidence_threshold:
            state.metrics.decomposition_attempts_total.add(1, {"outcome": "below_threshold"})
            logger.info(
                "reasoning.process.completed below decomposition confidence threshold, skipping",
                extra={
                    "reasoning_process_id": str(payload.reasoning_process_id),
                    "confidence_score": payload.confidence_score,
                },
            )
            return

        started = time.monotonic()
        try:
            graph = await decompose(
                root_objective=payload.objective_text,
                chosen_description=payload.chosen_description,
                model_port=state.model_orchestration_port,
                requesting_engine=_SOURCE_ENGINE,
                correlation_id=payload.correlation_id,
            )
        except DecompositionError as exc:
            duration = time.monotonic() - started
            state.metrics.decomposition_duration_seconds.record(duration, {"outcome": "failed"})
            state.metrics.decomposition_attempts_total.add(
                1, {"outcome": "failed", "reason": exc.reason}
            )
            logger.warning(
                "decomposition failed",
                extra={
                    "reasoning_process_id": str(payload.reasoning_process_id),
                    "correlation_id": str(payload.correlation_id),
                    "reason": exc.reason,
                },
            )
            return

        def _build_outbox_event(persisted_graph):  # type: ignore[no-untyped-def]
            created_payload = task_graph_created_payload(
                persisted_graph, correlation_id=payload.correlation_id
            )
            return OutboxEvent(
                subject="planning.task_graph.created",
                payload=created_payload.model_dump(mode="json"),
                correlation_id=payload.correlation_id,
            )

        # Builder-style, and the returned graph is the post-hand-off one:
        # the enqueued snapshot names the admitted nodes as `"ready"` for
        # `agent-os/kernel`'s Scheduler, while the persisted rows already say
        # `"running"` (`domain/ports.py::HAND_OFF_ORDERING`).
        handed_off_graph = await state.repository.insert(
            graph, outbox_event_builder=_build_outbox_event
        )
        state.metrics.planning_task_graph_created_total.add(1)
        admitted = sum(1 for node in handed_off_graph.nodes if node.status == "running")
        state.metrics.planning_task_node_admitted_total.add(admitted)

        duration = time.monotonic() - started
        state.metrics.decomposition_duration_seconds.record(duration, {"outcome": "succeeded"})
        state.metrics.decomposition_attempts_total.add(1, {"outcome": "succeeded"})
        state.metrics.decomposition_task_count.record(len(graph.nodes))
        logger.info(
            "decomposition succeeded and persisted",
            extra={
                "reasoning_process_id": str(payload.reasoning_process_id),
                "correlation_id": str(payload.correlation_id),
                "task_graph_id": str(graph.id),
                "task_count": len(graph.nodes),
                "critical_path_length": len(graph.critical_path),
                "admitted_node_count": admitted,
            },
        )

    return handle
