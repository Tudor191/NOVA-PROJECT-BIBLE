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
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from nova_contracts import EventEnvelope
from nova_contracts.events.perception import PerceptionSensorHealthChangedPayload
from nova_observability import get_logger
from pydantic import ValidationError

from nova_cognitive_state_engine.domain.ports import SensorStateRepository
from nova_cognitive_state_engine.domain.sensor_state import (
    SensorStateRecord,
    accept_lifecycle_state,
)

__all__ = ["SENSOR_HEALTH_SUBJECT", "make_sensor_health_handler"]

SENSOR_HEALTH_SUBJECT = "perception.sensor.health_changed"

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
