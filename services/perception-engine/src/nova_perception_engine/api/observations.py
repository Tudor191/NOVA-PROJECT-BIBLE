"""`POST /v1/perception/observations` (docs/design/phase-2d/
05-conversation-intelligence-closure.md Sec3, Priority 1 -- user-approved
Fork #3 Option 1) -- the entry point through which an already-captured
sensor window (an audio buffer, or an already-detected face crop) enters
this engine and is synchronously run through detection, correlation, and
`perception.addressee_signal.candidate` publication.

The window travels as a raw `application/octet-stream` request body, not a
base64 string inside a JSON field: Pydantic's `bytes` field, validated from
JSON, UTF-8-encodes the string verbatim rather than base64-decoding it
(confirmed directly, not assumed -- an earlier draft of this endpoint used
a JSON `bytes` field and silently corrupted any window byte outside the
ASCII range). `source`/`correlation_id` are query parameters instead, since
the body is spoken for.

No caller of this endpoint exists anywhere in this repository yet -- no
gateway or companion-client service exists (`apps/` is empty). This mirrors
`communication-engine`'s own WebSocket endpoint precedent exactly: a real
REST surface that simply waits for a not-yet-built caller, rather than a
fabricated capture integration (Sec3.1's own honesty boundary).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from nova_perception_engine.observation_orchestration import handle_observation_window

router = APIRouter(tags=["observations"])


class ObservationResponse(BaseModel):
    sensor_id: str
    presence_detected: bool
    published: bool


@router.post("/v1/perception/observations", response_model=ObservationResponse, status_code=202)
async def submit_observation(
    request: Request, source: str, correlation_id: UUID | None = None
) -> ObservationResponse:
    """`source` -- which registered sensor this window belongs to;
    unconstrained `str`, not a `Literal`, deliberately: mirrors
    `api/sensors.py`'s own `sensor_id: str` path-param convention so an
    unrecognized value 404s through this same handler. Sec3.10's
    per-sensor ingestion shape -- no cross-sensor synchronized capture is
    assumed or required."""
    window = await request.body()
    outcome = await handle_observation_window(
        request.app, source=source, window=window, correlation_id=correlation_id
    )
    if outcome is None:
        raise HTTPException(status_code=404, detail=f"No sensor registered for source {source!r}.")
    return ObservationResponse(
        sensor_id=outcome.sensor_id,
        presence_detected=outcome.presence_detected,
        published=outcome.published,
    )
