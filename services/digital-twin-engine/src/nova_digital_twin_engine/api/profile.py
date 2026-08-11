"""`GET`/`PATCH /v1/digital-twin/profile`, `POST /v1/digital-twin/reset`
(docs/design/phase-2d/06-personal-companion.md Sec7.1) -- Bible Part 16's
Digital Twin APIs' "Retrieve Profile"/"Update Profile"/"Reset Domain",
scoped to this phase's Communication Profile domain only.

`PATCH` is a **direct user override**, not routed through
`preference_evolution.evolve_field`'s consistency-requiring discipline --
Bible Part 16's own "User Control" principle ("the user should remain in
complete control") makes the user's own explicit edit the one case that
correctly bypasses "require consistent evidence" (that discipline exists to
guard against *inferred* evidence, never against the user's own direct
say-so). Each field actually changed is recorded as its own
`PreferenceEvolutionEntry` (`source="user_override"`, `confidence=1.0`) --
"nothing important should silently disappear."
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from nova_digital_twin_engine.domain.models import CommunicationProfile, PreferenceEvolutionEntry

router = APIRouter(prefix="/v1/digital-twin", tags=["profile"])

_LEARNED_FIELDS = (
    "verbosity",
    "technical_depth",
    "terminology_preference",
    "conversation_pacing",
    "habit_timing_hint",
)


async def _get_or_default(request: Request, user_id: UUID) -> CommunicationProfile:
    profile = await request.app.state.repository.get_communication_profile(user_id)
    return profile if profile is not None else CommunicationProfile(user_id=user_id)


@router.get("/profile", response_model=CommunicationProfile)
async def get_profile(user_id: UUID, request: Request) -> CommunicationProfile:
    return await _get_or_default(request, user_id)


class ProfilePatchRequest(BaseModel):
    verbosity: str | None = None
    technical_depth: str | None = None
    terminology_preference: dict | None = None
    conversation_pacing: str | None = None
    habit_timing_hint: str | None = None


@router.patch("/profile", response_model=CommunicationProfile)
async def patch_profile(
    user_id: UUID, body: ProfilePatchRequest, request: Request
) -> CommunicationProfile:
    state = request.app.state
    profile = await _get_or_default(request, user_id)

    updates: dict[str, object] = {}
    for field in _LEARNED_FIELDS:
        new_value = getattr(body, field)
        if new_value is None:
            continue
        previous_value = getattr(profile, field)
        if new_value == previous_value:
            continue
        updates[field] = new_value
        await state.repository.create_preference_evolution_entry(
            PreferenceEvolutionEntry(
                user_id=user_id,
                field=field,
                previous_value=str(previous_value) if previous_value is not None else None,
                new_value=str(new_value),
                confidence=1.0,
                source="user_override",
                reason="Direct user edit via PATCH /v1/digital-twin/profile.",
            )
        )

    if not updates:
        return profile

    updates["source"] = "learned"
    updated = profile.model_copy(update=updates)
    return await state.repository.upsert_communication_profile(updated)


@router.post("/reset", response_model=CommunicationProfile)
async def reset_profile(user_id: UUID, request: Request) -> CommunicationProfile:
    """Bible Part 16's "Reset Domain" -- scoped to this phase's
    Communication Profile domain (Sec7.1). Overwrites the stored profile
    with fresh defaults; the evolution history is left in place (an audit
    trail, not deleted -- "nothing important should silently disappear")."""
    default = CommunicationProfile(user_id=user_id)
    return await request.app.state.repository.upsert_communication_profile(default)
