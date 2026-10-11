"""The one Event Bus handler this engine has -- Phase 4F.7, RS-3a
(docs/design/phase-4/11-tdd-4f7-cognitive-state-panel.md §8.2, §28).

`perception.sensor.health_changed` is an **existing** subject with an existing
contract (`PerceptionSensorHealthChangedPayload`). This engine is a new
*consumer* of it -- not its author, and not its owner. What it does with each
report, in order:

1. **Validate** the payload against the registered contract. Invalid → log at
   warning and drop.
2. **Accept or reject the status** against `perception-engine`'s `SensorState`
   vocabulary (A-4F7-2). Unknown → log at warning and drop. **Never coerced,
   never stored, never returned**, and the previous record stays as it was.
3. **Apply** it to the one current record for that `sensor_id` with the
   repository's conditional upsert (A-4F7-1). A redelivery or an older report
   changes nothing.

**It never replies, never publishes and never raises.** A handler that raised
would surface inside the SDK's NATS callback, where nothing can act on it; a
failure is logged with the envelope's `event_id` and `correlation_id` instead.

**No replay, retry or recovery.** The subscription is core NATS: a report
dispatched while this engine is not subscribed is not delivered to it (TDD 4F.7
§15 K-1). Nothing here pretends otherwise.

*(Phase 4F.P -- TDD 4F.P §30.2, A-4FP-1 and A-4FP-10. "The one Event Bus
handler" in this docstring's first line is preserved as written and is now
**two**: `make_workspace_observation_handler` below consumes the existing,
internal `perception.workspace.observed`. The paragraphs above describe the
sensor handler and still hold for it.)*
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from nova_contracts import EventEnvelope
from nova_contracts.events.perception import (
    PerceptionSensorHealthChangedPayload,
    PerceptionWorkspaceObservedPayload,
)
from nova_observability import get_logger
from pydantic import ValidationError

from nova_cognitive_state_engine.domain.ports import (
    CognitiveStateRepository,
    DecisionTriggerPort,
    SensorStateRepository,
)
from nova_cognitive_state_engine.domain.sensor_state import (
    SensorStateRecord,
    accept_lifecycle_state,
)
from nova_cognitive_state_engine.ingestion_orchestration import ingest_workspace_observation

__all__ = [
    "SENSOR_HEALTH_SUBJECT",
    "WORKSPACE_OBSERVED_SUBJECT",
    "make_sensor_health_handler",
    "make_workspace_observation_handler",
]

SENSOR_HEALTH_SUBJECT = "perception.sensor.health_changed"

WORKSPACE_OBSERVED_SUBJECT = "perception.workspace.observed"
"""**Phase 4F.P, A-4FP-1.** An existing, registered, **internal** subject
(`PerceptionWorkspaceObservedPayload`), published by `perception-engine`. This
engine is a new consumer of it -- not its author, and not its owner."""

logger = get_logger("cognitive-state-engine.events")


def make_sensor_health_handler(
    repository: SensorStateRepository,
) -> Callable[[EventEnvelope], Awaitable[None]]:
    async def handle(envelope: EventEnvelope) -> None:
        context = {
            "event_id": str(envelope.event_id),
            "correlation_id": str(envelope.correlation_id),
        }
        try:
            payload = PerceptionSensorHealthChangedPayload.model_validate(envelope.payload)
        except ValidationError as exc:
            logger.warning(
                "sensor_report_rejected_invalid_payload",
                extra={**context, "detail": str(exc.errors(include_url=False))},
            )
            return

        state = accept_lifecycle_state(payload.status)
        if state is None:
            # A-4F7-2: an unknown value is not a state. Not stored, not coerced;
            # the table keeps the latest *known* state for this sensor.
            logger.warning(
                "sensor_report_rejected_unknown_status",
                extra={**context, "sensor_id": payload.sensor_id, "status": payload.status},
            )
            return

        record = SensorStateRecord(
            sensor_id=payload.sensor_id,
            sensor_type=payload.sensor_type,
            state=state,
            reported_at=envelope.occurred_at,
            last_event_id=envelope.event_id,
        )
        try:
            changed = await repository.apply_sensor_report(record)
        except Exception:
            logger.exception(
                "sensor_report_not_stored", extra={**context, "sensor_id": payload.sensor_id}
            )
            return

        logger.info(
            "sensor_report_applied" if changed else "sensor_report_ignored_duplicate_or_stale",
            extra={**context, "sensor_id": payload.sensor_id, "state": state},
        )

    return handle


def make_workspace_observation_handler(
    repository: CognitiveStateRepository,
    trigger: DecisionTriggerPort,
    *,
    user_id: UUID,
) -> Callable[[EventEnvelope], Awaitable[None]]:
    """**Phase 4F.P, A-4FP-1 and A-4FP-10 (SD-6).** One observation, one
    ingestion step, **awaited inline** -- the insert, the promotion and the
    trigger all finish before this handler returns, so the subscription takes
    the next message only after this one is done. No background task, no
    queue, no retry.

    1. **Validate** against the registered contract. Invalid → log at warning
       and drop; nothing is written.
    2. **Ingest** (`ingestion_orchestration.py`). Every outcome is logged with
       the envelope's `event_id` and `correlation_id`.

    **It never replies, never publishes and never raises.** A failure is logged
    instead: a handler that raised would surface inside the SDK's NATS
    callback, where nothing can act on it. The observation's `label` is not
    logged, and its path never reaches this engine at all."""

    async def handle(envelope: EventEnvelope) -> None:
        context = {
            "event_id": str(envelope.event_id),
            "correlation_id": str(envelope.correlation_id),
        }
        try:
            payload = PerceptionWorkspaceObservedPayload.model_validate(envelope.payload)
        except ValidationError as exc:
            # `include_input=False`: a rejected payload's values -- its label
            # among them -- are not echoed into the log.
            logger.warning(
                "workspace_observation_rejected_invalid_payload",
                extra={
                    **context,
                    "detail": str(exc.errors(include_url=False, include_input=False)),
                },
            )
            return

        try:
            result = await ingest_workspace_observation(
                payload, repository=repository, trigger=trigger, user_id=user_id
            )
        except Exception:
            # The insert failed, so nothing was written for this observation.
            logger.exception(
                "workspace_observation_not_ingested",
                extra={**context, "object_id": payload.object_id},
            )
            return

        detail = {
            **context,
            "object_id": payload.object_id,
            "thought_id": str(result.thought_id) if result.thought_id is not None else None,
        }
        if result.outcome == "foreign_user":
            # SD-1: one trusted user per instance; anyone else's observation is
            # not this engine's to hold.
            logger.warning("workspace_observation_dropped_foreign_user", extra=detail)
        elif result.outcome == "duplicate":
            logger.info("workspace_observation_duplicate_nothing_written", extra=detail)
        elif result.outcome == "initiative_lost":
            # FP-15: the thought exists, its initiative does not, and nothing
            # recovers it.
            logger.error(
                "workspace_observation_initiative_lost", extra={**detail, "error": result.error}
            )
        else:
            promotion = result.promotion
            delivery = promotion.trigger if promotion is not None else None
            logger.info(
                "workspace_observation_ingested",
                extra={
                    **detail,
                    "moved": promotion.moved if promotion is not None else False,
                    "trigger_status": delivery.status if delivery is not None else None,
                    "decision_outcome": delivery.outcome if delivery is not None else None,
                    "subject_id": (
                        str(delivery.subject_id)
                        if delivery is not None and delivery.subject_id is not None
                        else None
                    ),
                },
            )

    return handle
