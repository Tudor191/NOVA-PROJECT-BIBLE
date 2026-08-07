"""`/v1/perception/consent` (docs/design/phase-2d/03-perception-engine.md
§3.3, §11, §14) -- Grant Consent, Consent Status, Revoke Consent. Revocation
calls the matching sensor's `stop()` synchronously within the same request
(§3.3, §5, §11: "no capture continues even momentarily past a revocation"),
never eventually-consistent.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from nova_perception_engine.domain import consent
from nova_perception_engine.domain.models import Source
from nova_perception_engine.events import publishers

router = APIRouter(prefix="/v1/perception/consent", tags=["consent"])


class GrantConsentRequest(BaseModel):
    user_id: UUID
    source: Source
    scope: str


class ConsentResponse(BaseModel):
    consent_id: UUID
    user_id: UUID
    source: Source
    scope: str
    granted_at: datetime
    revoked_at: datetime | None


def _to_response(grant) -> ConsentResponse:  # type: ignore[no-untyped-def]
    return ConsentResponse(
        consent_id=grant.consent_id,
        user_id=grant.user_id,
        source=grant.source,
        scope=grant.scope,
        granted_at=grant.granted_at,
        revoked_at=grant.revoked_at,
    )


@router.get("", response_model=list[ConsentResponse])
async def consent_status(user_id: UUID, request: Request) -> list[ConsentResponse]:
    grants = await request.app.state.repository.consent_status(user_id=user_id)
    return [_to_response(grant) for grant in grants]


@router.post("", response_model=ConsentResponse, status_code=201)
async def grant_consent(body: GrantConsentRequest, request: Request) -> ConsentResponse:
    state = request.app.state
    grant = await consent.grant(
        state.repository, user_id=body.user_id, source=body.source, scope=body.scope
    )
    state.metrics.consent_grants_total.add(1)
    await state.repository.enqueue_outbox(
        publishers.consent_changed(
            user_id=body.user_id, source=body.source, granted=True, correlation_id=grant.consent_id
        )
    )
    return _to_response(grant)


@router.delete("/{source}", response_model=ConsentResponse)
async def revoke_consent(source: Source, user_id: UUID, request: Request) -> ConsentResponse:
    state = request.app.state
    revoked = await consent.revoke(state.repository, user_id=user_id, source=source)
    if revoked is None:
        raise HTTPException(status_code=404, detail="No active consent grant for that source.")
    state.metrics.consent_revocations_total.add(1)

    sensor = state.sensors_by_source.get(source)
    if sensor is not None and sensor.state() in ("running", "paused"):
        await sensor.stop()

    await state.repository.enqueue_outbox(
        publishers.consent_changed(
            user_id=user_id, source=source, granted=False, correlation_id=revoked.consent_id
        )
    )
    return _to_response(revoked)
