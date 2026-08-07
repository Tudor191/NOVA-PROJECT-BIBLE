"""`POST /v1/communication/notifications`
(docs/design/phase-2d/01-communication-engine.md Sec10, Sec12) -- Generate
Notification, minimal this phase: recorded, not yet delivered through any
push channel (Sec12's own honest scope note; the full "Communication
Policies" prioritization intelligence is 2D-C scope). Prefixed
`/v1/communication` per the Phase 2D-A Gate Review's API-consistency
finding -- see `sessions.py`'s docstring.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from nova_communication_engine.domain.models import Notification, NotificationPriority

router = APIRouter(prefix="/v1/communication/notifications", tags=["notifications"])


class CreateNotificationRequest(BaseModel):
    user_id: UUID
    content: str
    priority: NotificationPriority = NotificationPriority.NORMAL


class NotificationResponse(BaseModel):
    notification_id: UUID
    user_id: UUID
    content: str
    priority: NotificationPriority
    delivered_at: datetime | None
    created_at: datetime


@router.post("", response_model=NotificationResponse, status_code=201)
async def create_notification(
    body: CreateNotificationRequest, request: Request
) -> NotificationResponse:
    notification = Notification(user_id=body.user_id, content=body.content, priority=body.priority)
    saved = await request.app.state.repository.create_notification(notification)
    return NotificationResponse(
        notification_id=saved.notification_id,
        user_id=saved.user_id,
        content=saved.content,
        priority=saved.priority,
        delivered_at=saved.delivered_at,
        created_at=saved.created_at,
    )
