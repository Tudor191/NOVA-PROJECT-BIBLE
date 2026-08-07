"""`/v1/perception/identities` (docs/design/phase-2d/03-perception-engine.md
§3.1, §14) -- Enroll Identity, List Identities, Revoke Identity. Every
response is metadata only (`identity_id`, `modality`, `enrolled_at`) --
`template_ciphertext` is never serialized into an API response (§11, §14).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from nova_perception_engine.domain import enrollment
from nova_perception_engine.domain.consent import ConsentRequiredError, require_active_consent
from nova_perception_engine.domain.models import Modality, Source

router = APIRouter(prefix="/v1/perception/identities", tags=["identities"])

_SOURCE_FOR_MODALITY: dict[Modality, Source] = {"voice": "microphone", "face": "camera"}
"""§3.1's consent gate is keyed by *source* (microphone/camera), enrollment is
keyed by *modality* (voice/face) -- this is the one place the two vocabularies
meet, mirroring `sensors/voice_sensor.py`/`sensors/camera_sensor.py`'s own
modality-to-source pairing."""

_SAMPLE_BYTES_CONFIG = ConfigDict(ser_json_bytes="base64", val_json_bytes="base64")
"""Matches `ai-model-orchestration-engine`'s own `_AUDIO_BYTES_CONFIG`
precedent -- arbitrary binary audio/image content is not valid UTF-8 in
general, so pydantic v2's default JSON `bytes` handling must be overridden
explicitly."""


class EnrollIdentityRequest(BaseModel):
    model_config = _SAMPLE_BYTES_CONFIG

    user_id: UUID
    modality: Modality
    sample_bytes: bytes
    """One bounded audio window (`modality="voice"`) or one already-detected
    face crop (`modality="face"`) -- the same "caller owns windowing/
    detection" boundary `sensors/*.py` keep toward `ai-model-orchestration-
    engine`."""


class IdentityResponse(BaseModel):
    identity_id: UUID
    user_id: UUID
    modality: Modality
    enrolled_at: datetime


@router.post("", response_model=IdentityResponse, status_code=201)
async def enroll_identity(body: EnrollIdentityRequest, request: Request) -> IdentityResponse:
    state = request.app.state
    source = _SOURCE_FOR_MODALITY[body.modality]
    try:
        await require_active_consent(state.repository, user_id=body.user_id, source=source)
    except ConsentRequiredError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if not state.settings.template_encryption_key:
        raise HTTPException(status_code=500, detail="Template encryption key is not configured.")
    encryption_key = state.settings.template_encryption_key.encode("utf-8")

    if body.modality == "voice":
        embed_result = await state.ai_model_port.embed_voice(audio=body.sample_bytes)
    else:
        embed_result = await state.ai_model_port.embed_face(image=body.sample_bytes)
    if embed_result is None:
        raise HTTPException(status_code=503, detail="No embedding model was available.")

    identity = await enrollment.enroll(
        state.repository,
        user_id=body.user_id,
        modality=body.modality,
        embedding=embed_result.embedding,
        encryption_key=encryption_key,
    )
    state.metrics.enrollments_total.add(1)
    return IdentityResponse(
        identity_id=identity.identity_id,
        user_id=identity.user_id,
        modality=identity.modality,
        enrolled_at=identity.enrolled_at,
    )


@router.get("", response_model=list[IdentityResponse])
async def list_identities(user_id: UUID, request: Request) -> list[IdentityResponse]:
    identities = await request.app.state.repository.list_identities(user_id=user_id)
    return [
        IdentityResponse(
            identity_id=identity.identity_id,
            user_id=identity.user_id,
            modality=identity.modality,
            enrolled_at=identity.enrolled_at,
        )
        for identity in identities
    ]


@router.delete("/{identity_id}", status_code=204)
async def revoke_identity(identity_id: UUID, request: Request) -> None:
    revoked = await request.app.state.repository.revoke_identity(identity_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="Identity not found.")
    request.app.state.metrics.revocations_total.add(1)
