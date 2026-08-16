"""`GET /v1/capabilities`, `POST /v1/capabilities/install`,
`DELETE /v1/capabilities/{id}` (TDD 3C §7) -- thin, delegates entirely to
`domain/pipeline.py` and the repository already wired onto
`request.app.state` in `main.py`. Exposed directly, no `api-gateway` yet
(same stopgap precedent as every other Phase 3 engine).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from nova_contracts import Capability

from nova_capability_engine.domain.models import CapabilityManifest
from nova_capability_engine.domain.pipeline import InstallationError, install_capability

router = APIRouter(prefix="/v1/capabilities", tags=["capabilities"])


@router.get("", response_model=list[Capability])
async def list_capabilities(request: Request) -> list[Capability]:
    return await request.app.state.repository.list_all()


@router.post("/install", response_model=Capability, status_code=201)
async def install(body: CapabilityManifest, request: Request) -> Capability:
    """Idempotent on `(name, version)` (Fork 3C-4, Option B) -- a repeat
    request for an already-installed capability returns the existing row,
    never a duplicate or a 409."""
    state = request.app.state
    try:
        return await install_capability(
            body,
            repository=state.repository,
            adapters=state.adapters,
            communication_port=state.communication_port,
            primary_user_id=state.settings.primary_user_id,
            on_stage=state.on_install_stage,
        )
    except InstallationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{capability_id}", status_code=204)
async def delete_capability(capability_id: UUID, request: Request) -> None:
    deleted = await request.app.state.repository.delete(capability_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="capability not found")
