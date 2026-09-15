"""Structured workspace intake -- TDD 4F §8.1's ratified second intake route.

`handle_observation_window` (the sibling module) takes an
`application/octet-stream` **capture window** -- an audio buffer or a face crop
-- and runs presence-gating, wake-phrase detection and biometric matching over
it. A filesystem event is **structured metadata**, not a byte window: there is
nothing in it to run a detector over, and nothing in that pipeline that could
consume it. §8.1 records the split as a deliberate addition rather than leaving
the Gate Review to discover it.

What is *shared* with that pipeline, deliberately, rather than reimplemented:
the sensor registry lookup, the `state() != "running"` gate, the
`primary_user_id` identity resolution and its degrade, and the transactional
outbox. What differs is only the shape of what arrives.

**The identity boundary.** `user_id` is resolved here from
`Settings.primary_user_id` (ADR-025) exactly as the window pipeline does. The
request model has no `user_id` field at all, so a caller cannot supply one --
the override is not rejected at runtime, it is unrepresentable. When
`primary_user_id` is unset this publishes **nothing** and says so, the same
explicit degrade Priority 2 ratified: never a guessed identity.

Lives outside `domain/` for the same reason `observation_orchestration.py`
does: it needs `app.state`, which `domain/ports.py` forbids `domain/` code from
reaching.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import FastAPI
from nova_observability import get_logger
from pydantic import BaseModel

from nova_perception_engine.domain.workspace import (
    WorkspaceObservation,
    label_for_path,
    object_id_for_path,
    resolve_project_id,
)
from nova_perception_engine.events.publishers import workspace_observed

__all__ = ["WorkspaceObservationOutcome", "WorkspaceObservationRequest", "handle_workspace_event"]

logger = get_logger("perception-engine.workspace_orchestration")


class WorkspaceObservationRequest(BaseModel):
    """What the companion sends.

    **No `user_id` field, deliberately** -- see this module's docstring. Also
    no `object_id`: the companion reports a *path*, and this engine decides
    what handle that becomes, so a caller cannot hand in a pre-computed (or
    forged) object handle either.
    """

    path: str
    observed_at: datetime
    """The **real** OS event time, from the sensor that saw it. §20.1 forbids
    fabricating this, so it is required rather than defaulted to `now()` --
    a default would quietly substitute the server's clock for the event's own
    and still look like a genuine timestamp."""


class WorkspaceObservationOutcome(BaseModel):
    sensor_id: str
    object_id: str | None = None
    published: bool
    reason: str | None = None
    """Why nothing was published, when nothing was. A machine-readable
    explanation rather than a bare `published: false`, the same discipline
    4E's domain states adopted -- "no event" and "no event *because consent
    was revoked*" are different facts."""


async def handle_workspace_event(
    app: FastAPI,
    *,
    source: str,
    request: WorkspaceObservationRequest,
    correlation_id: UUID | None = None,
) -> WorkspaceObservationOutcome | None:
    """Returns `None` when no sensor is registered for `source` -- the caller
    maps that to 404, matching `handle_observation_window`'s own convention."""
    state = app.state
    sensor = state.sensors_by_source.get(source)
    if sensor is None:
        return None
    sensor_id = sensor.sensor_id
    correlation_id = correlation_id or uuid4()

    if sensor.state() != "running":
        # §9: "drop any signal whose sensor is not `running`". This is what
        # makes AC-7's revocation clause true at the pipeline level rather
        # than only at the sensor -- a paused sensor's in-flight observation
        # must not slip through behind it.
        return WorkspaceObservationOutcome(
            sensor_id=sensor_id, published=False, reason="sensor_not_running"
        )

    user_id = state.settings.primary_user_id
    if user_id is None:
        logger.warning("primary_user_id_not_configured", extra={"sensor_id": sensor_id})
        return WorkspaceObservationOutcome(
            sensor_id=sensor_id, published=False, reason="primary_user_id_not_configured"
        )

    object_id = object_id_for_path(request.path)
    observation = WorkspaceObservation(
        object_id=object_id,
        label=label_for_path(request.path),
        sensor_id=sensor_id,
        observed_at=request.observed_at,
        project_id=resolve_project_id(object_id, state.known_projects),
    )

    if not state.workspace_debouncer.admit(observation):
        return WorkspaceObservationOutcome(
            sensor_id=sensor_id, object_id=object_id, published=False, reason="debounced"
        )

    event = workspace_observed(observation, user_id=user_id, correlation_id=correlation_id)
    await state.repository.enqueue_outbox(event)
    return WorkspaceObservationOutcome(sensor_id=sensor_id, object_id=object_id, published=True)
