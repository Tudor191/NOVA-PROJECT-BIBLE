"""`GET /v1/digital-twin/preferences` (docs/design/phase-2d/
06-personal-companion.md Sec7.1) -- HTTP mirror of the `digital_twin.
preferences.get` Event-Bus RPC (`events/handlers.py`), HTTP-accessible for
a future dashboard."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from nova_digital_twin_engine.domain.models import CommunicationProfile

router = APIRouter(prefix="/v1/digital-twin", tags=["preferences"])


class PreferencesResponse(BaseModel):
    user_id: UUID
    conversation_pacing: str | None
    habit_timing_hint: str | None


@router.get("/preferences", response_model=PreferencesResponse)
async def preferences(user_id: UUID, request: Request) -> PreferencesResponse:
    state = request.app.state
    profile = await state.repository.get_communication_profile(user_id)
    if profile is None:
        profile = CommunicationProfile(user_id=user_id)
    return PreferencesResponse(
        user_id=user_id,
        conversation_pacing=profile.conversation_pacing,
        habit_timing_hint=profile.habit_timing_hint,
    )
