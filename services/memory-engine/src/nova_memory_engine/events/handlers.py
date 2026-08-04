"""Event Bus subscription handlers -- docs/design/phase-1/01-memory-engine.md §13.

Per docs/design/phase-1/04-cross-engine-integration.md, Perception, Reasoning, and
Planning don't exist yet in Phase 1 -- these handlers are contracts this engine is
ready to serve, exercised today by a synthetic/test-published event, not a live
upstream producer. Each extracts the minimal fields it can defensively find in
`envelope.payload` and no-ops (with a warning log) rather than raising, since a
malformed or not-yet-finalized upstream payload must never crash this engine's
event loop. Full payload-aware handling lands once each producing engine's real
contract exists (Phase 2-4) -- see the Phase 1 Architecture Review Report for this
noted as a known limitation, not an oversight.
"""

from __future__ import annotations

from uuid import UUID

from nova_contracts import EventEnvelope
from nova_observability import get_logger

from nova_memory_engine.domain import episodic, long_term, sensory, short_term
from nova_memory_engine.domain.ports import MemoryRepository

logger = get_logger("memory-engine.events.handlers")


def _text_from(payload: dict, *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _uuid_from(payload: dict, key: str) -> UUID | None:
    value = payload.get(key)
    if not value:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def make_perception_observed_handler(repository: MemoryRepository):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> None:
        user_id = _uuid_from(envelope.payload, "user_id")
        content = _text_from(envelope.payload, "content", "description")
        if user_id is None or content is None:
            logger.warning(
                "perception.*.observed missing user_id/content, skipping",
                extra={"subject": envelope.subject},
            )
            return
        candidate = sensory.SensoryCandidate(content=content, source="perception", user_id=user_id)
        if not sensory.worth_retaining(candidate):
            return
        await episodic.remember(
            repository,
            user_id=user_id,
            content=content,
            source="perception",
            correlation_id=envelope.correlation_id,
        )

    return handle


def make_reasoning_result_handler(repository: MemoryRepository):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> None:
        user_id = _uuid_from(envelope.payload, "user_id")
        content = _text_from(envelope.payload, "summary", "content")
        if user_id is None or content is None:
            logger.warning("reasoning.result missing user_id/content, skipping")
            return
        await episodic.remember(
            repository,
            user_id=user_id,
            content=content,
            source="reasoning",
            correlation_id=envelope.correlation_id,
        )

    return handle


def make_action_result_handler(repository: MemoryRepository):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> None:
        user_id = _uuid_from(envelope.payload, "user_id")
        content = _text_from(envelope.payload, "summary", "content")
        if user_id is None or content is None:
            logger.warning("action.result missing user_id/content, skipping")
            return
        await episodic.remember(
            repository,
            user_id=user_id,
            content=content,
            outcome=_text_from(envelope.payload, "outcome"),
            source="action",
            correlation_id=envelope.correlation_id,
        )

    return handle


def make_communication_intent_handler(repository: MemoryRepository):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> None:
        user_id = _uuid_from(envelope.payload, "user_id")
        content = _text_from(envelope.payload, "content", "message")
        if user_id is None or content is None:
            logger.warning("communication.intent.received missing user_id/content, skipping")
            return
        await short_term.remember(
            repository,
            user_id=user_id,
            content=content,
            category="recent_conversation",
            correlation_id=envelope.correlation_id,
        )

    return handle


def make_agent_os_task_completed_handler(repository: MemoryRepository):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> None:
        user_id = _uuid_from(envelope.payload, "user_id")
        content = _text_from(envelope.payload, "summary", "content")
        if user_id is None or content is None:
            logger.warning("agent_os.task.completed missing user_id/content, skipping")
            return
        await episodic.remember(
            repository,
            user_id=user_id,
            content=content,
            source="agent_os",
            correlation_id=envelope.correlation_id,
        )

    return handle


def make_knowledge_contradiction_handler(repository: MemoryRepository):  # type: ignore[no-untyped-def]
    """Flags a memory's confidence downward on a detected contradiction (docs/
    design/phase-1/01-memory-engine.md §13) -- does not resolve the contradiction
    (that's Reasoning Engine's job, Phase 2) or change lifecycle state."""

    CONFIDENCE_PENALTY = 0.3

    async def handle(envelope: EventEnvelope) -> None:
        memory_id = _uuid_from(envelope.payload, "memory_id")
        user_id = _uuid_from(envelope.payload, "user_id")
        if memory_id is None or user_id is None:
            logger.warning("knowledge.contradiction.detected missing memory_id/user_id, skipping")
            return
        record = await long_term.get(repository, memory_id, user_id=user_id)
        if record is None:
            return
        lowered = max(0.0, (record.confidence or 0.5) - CONFIDENCE_PENALTY)
        await long_term.correct(
            repository,
            memory_id,
            user_id=user_id,
            updates={"confidence": lowered},
            correlation_id=envelope.correlation_id,
        )

    return handle
