"""`GET`/`PATCH /v1/digital-twin/proactive-policy` -- not itself named in
Sec7.1's bullet list, but a necessary completion of Bible Part 16's "User
Control" (view/modify, explicitly required per Sec13) for the boundary
policy Fork D's warm-case delivery (Step 9) depends on:
`proactive_boundary.evaluate_proactive_suggestion` declines any topic with
no configured limit (`domain/proactive_boundary.py`'s own fail-closed
discipline), so without some way to configure one, Fork D's approved
feature could never actually deliver anything. Mirrors `profile.py`'s
`PATCH` shape exactly."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from nova_digital_twin_engine.domain.models import ProactiveBoundaryPolicy

router = APIRouter(prefix="/v1/digital-twin", tags=["proactive-policy"])


async def _get_or_default(request: Request, user_id: UUID) -> ProactiveBoundaryPolicy:
    policy = await request.app.state.repository.get_proactive_boundary_policy(user_id)
    return policy if policy is not None else ProactiveBoundaryPolicy(user_id=user_id)


@router.get("/proactive-policy", response_model=ProactiveBoundaryPolicy)
async def get_proactive_policy(user_id: UUID, request: Request) -> ProactiveBoundaryPolicy:
    return await _get_or_default(request, user_id)


class ProactivePolicyPatchRequest(BaseModel):
    enabled: bool | None = None
    max_per_topic_per_window: dict[str, int] | None = None
    window_hours: int | None = None


@router.patch("/proactive-policy", response_model=ProactiveBoundaryPolicy)
async def patch_proactive_policy(
    user_id: UUID, body: ProactivePolicyPatchRequest, request: Request
) -> ProactiveBoundaryPolicy:
    policy = await _get_or_default(request, user_id)
    updates = body.model_dump(exclude_none=True)
    updated = policy.model_copy(update=updates) if updates else policy
    return await request.app.state.repository.upsert_proactive_boundary_policy(updated)
