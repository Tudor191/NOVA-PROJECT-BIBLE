"""`/v1/communication/sessions*` (docs/design/phase-2d/01-communication-engine.md
Sec12) -- Create Session, Send Message (text), Pause/Resume Conversation,
Close Session, Retrieve Context. The WebSocket channel (voice + streaming
text) is `api/websocket.py`; this router is the synchronous HTTP surface.

`POST /sessions/{id}/messages` records the inbound turn and returns an
acknowledgment only -- design doc Sec6's "Determine Intent" pass-through
means the actual reply is generated asynchronously by a content-source
engine (Reasoning Engine) and delivered later through the `communication.
intent` gate, over whatever channel connection is currently live (design
doc Sec8.2).

Prefixed `/v1/communication` per the Phase 2D-A Gate Review's API-consistency
finding: every prior engine's public API follows `/v1/<domain>/...`; this
engine's original bare-path routes were a real, unintentional deviation,
corrected immediately per the user's own standing instruction to fix a
Gate-Review-identified inconsistency rather than carry it forward as debt.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from nova_communication_engine.domain import session_lifecycle
from nova_communication_engine.domain.models import ChannelType, ConversationState
from nova_communication_engine.domain.session_lifecycle import InvalidCloseStateError
from nova_communication_engine.domain.state_machine import InvalidTransitionError

router = APIRouter(prefix="/v1/communication/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    user_id: UUID
    channel: ChannelType
    device_id: UUID


class SessionResponse(BaseModel):
    session_id: UUID
    user_id: UUID
    channel: ChannelType
    device_id: UUID
    state: ConversationState
    objective: str | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None


def _to_response(session) -> SessionResponse:  # type: ignore[no-untyped-def]
    return SessionResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        channel=session.channel,
        device_id=session.device_id,
        state=session.state,
        objective=session.objective,
        created_at=session.created_at,
        updated_at=session.updated_at,
        closed_at=session.closed_at,
    )


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(body: CreateSessionRequest, request: Request) -> SessionResponse:
    state = request.app.state
    session = await session_lifecycle.create_session(
        user_id=body.user_id,
        channel=body.channel,
        device_id=body.device_id,
        repository=state.repository,
        world_model_port=state.world_model_port,
        correlation_id=body.device_id,
    )
    return _to_response(session)


async def _get_session_or_404(session_id: UUID, request: Request):  # type: ignore[no-untyped-def]
    session = await request.app.state.repository.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


class SendMessageRequest(BaseModel):
    content: str


class SendMessageResponse(BaseModel):
    turn_id: UUID
    session_id: UUID
    accepted: bool = True


@router.post("/{session_id}/messages", response_model=SendMessageResponse, status_code=202)
async def send_message(
    session_id: UUID, body: SendMessageRequest, request: Request
) -> SendMessageResponse:
    session = await _get_session_or_404(session_id, request)
    try:
        _updated_session, turn = await session_lifecycle.record_inbound_turn(
            session=session,
            content=body.content,
            repository=request.app.state.repository,
            correlation_id=session_id,
        )
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return SendMessageResponse(turn_id=turn.turn_id, session_id=session_id)


@router.post("/{session_id}/pause", response_model=SessionResponse)
async def pause_session(session_id: UUID, request: Request) -> SessionResponse:
    session = await _get_session_or_404(session_id, request)
    try:
        updated = await session_lifecycle.pause_session(
            session=session, repository=request.app.state.repository, correlation_id=session_id
        )
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _to_response(updated)


@router.post("/{session_id}/resume", response_model=SessionResponse)
async def resume_session(session_id: UUID, request: Request) -> SessionResponse:
    session = await _get_session_or_404(session_id, request)
    try:
        updated = await session_lifecycle.resume_session(
            session=session, repository=request.app.state.repository, correlation_id=session_id
        )
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _to_response(updated)


@router.delete("/{session_id}", response_model=SessionResponse)
async def close_session(session_id: UUID, request: Request) -> SessionResponse:
    session = await _get_session_or_404(session_id, request)
    try:
        updated = await session_lifecycle.close_session(
            session=session, repository=request.app.state.repository, correlation_id=session_id
        )
    except InvalidCloseStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    request.app.state.session_registry.unregister(session_id)
    return _to_response(updated)


class ContextResponse(BaseModel):
    session_id: UUID
    state: ConversationState
    objective: str | None
    turn_count: int


@router.get("/{session_id}/context", response_model=ContextResponse)
async def retrieve_context(session_id: UUID, request: Request) -> ContextResponse:
    session = await _get_session_or_404(session_id, request)
    return ContextResponse(
        session_id=session.session_id,
        state=session.state,
        objective=session.objective,
        turn_count=len(session.turns),
    )
