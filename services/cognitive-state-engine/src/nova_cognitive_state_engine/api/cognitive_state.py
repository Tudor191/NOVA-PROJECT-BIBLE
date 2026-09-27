"""`/v1/cognitive-state/*` -- TDD 4F.7 §7's three routes, and nothing beyond them.

| Method | Path |
|---|---|
| `GET` | `/v1/cognitive-state/thoughts` |
| `GET` | `/v1/cognitive-state/focus` |
| `GET` | `/v1/cognitive-state/sensors` |

**Read-only, by construction** (RS-1b). Only `@router.get` is declared, no route
has a body, a path parameter or a query parameter, and nothing here can reach
`upsert_thought`, `move_layer` or `promote_thought`. Any other method answers
405, which `api-gateway` forwards unchanged. Creating thoughts, authoring
`ProposedAction`s and promoting are the promotion slice 4F.P's (RS-1c).

**Identity is the server's** (ADR-025, RS-4a). Every thought read resolves
`Settings.primary_user_id`; there is no `user_id` parameter, so a caller cannot
name another identity -- a `?user_id=` is simply ignored.

**Empty is empty.** An empty store answers `{"thoughts": []}`, `{"capacity": …,
"entries": []}` and `{"sensors": []}`. Nothing is synthesized. **An error is
never an empty success**: a store or validation failure propagates as an error
response, because `[]` is a claim that nothing exists.

**No autonomy data** (RS-4b). No route reads `autonomy-engine`, and no response
carries a decision, outcome, `subject_id` or triggered/executed field.
`proposed_action` is returned **as a proposal** (RS-4c) -- the persisted value,
exactly, and nothing about what happened to it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from nova_cognitive_state_engine.domain.focus import select_focus
from nova_cognitive_state_engine.domain.models import (
    ActiveThought,
    FocusedThought,
    ProposedAction,
)
from nova_cognitive_state_engine.domain.sensor_state import (
    SensorLifecycleState,
    SensorStateRecord,
)

__all__ = [
    "FocusEntryResponse",
    "FocusResponse",
    "ProposedActionResponse",
    "SensorStateListResponse",
    "SensorStateResponse",
    "ThoughtListResponse",
    "ThoughtResponse",
    "router",
]

router = APIRouter(prefix="/v1/cognitive-state", tags=["cognitive-state"])


class _Strict(BaseModel):
    """Every 4F.7 response model forbids unknown fields -- 4D's and 4E's
    precedent (`digital-twin-engine/api/digital_twin.py`). A field that is not
    in TDD 4F.7 §7 cannot be added by accident."""

    model_config = ConfigDict(extra="forbid")


class ProposedActionResponse(_Strict):
    """`ProposedAction`, verbatim -- a **proposal**, and nothing about its fate."""

    category: str
    risk: str
    action_type: str
    execution_target: str
    verification_method: str
    title: str
    detail: str

    @classmethod
    def of(cls, action: ProposedAction) -> ProposedActionResponse:
        return cls(
            category=action.category.value,
            risk=action.risk.value,
            action_type=action.action_type,
            execution_target=action.execution_target,
            verification_method=action.verification_method,
            title=action.title,
            detail=action.detail,
        )


class ThoughtResponse(_Strict):
    """Every Part 6 field of an Active Thought (l.123–137), plus its identity,
    Attention Layer and bookkeeping. **No `user_id`**: identity is the
    server's, and echoing it gives a client nothing to act on."""

    thought_id: UUID
    description: str
    priority: int
    confidence: float
    dependencies: list[UUID]
    estimated_completion: datetime | None
    related_memories: list[UUID]
    related_projects: list[UUID]
    current_progress: float
    attention_layer: Literal["immediate", "active", "passive", "dormant", "archived"]
    created_at: datetime
    updated_at: datetime
    proposed_action: ProposedActionResponse | None

    @classmethod
    def of(cls, thought: ActiveThought) -> ThoughtResponse:
        return cls(
            thought_id=thought.thought_id,
            description=thought.description,
            priority=thought.priority,
            confidence=thought.confidence,
            dependencies=list(thought.dependencies),
            estimated_completion=thought.estimated_completion,
            related_memories=list(thought.related_memories),
            related_projects=list(thought.related_projects),
            current_progress=thought.current_progress,
            attention_layer=thought.attention_layer.value,
            created_at=thought.created_at,
            updated_at=thought.updated_at,
            proposed_action=(
                ProposedActionResponse.of(thought.proposed_action)
                if thought.proposed_action is not None
                else None
            ),
        )


class ThoughtListResponse(_Strict):
    thoughts: list[ThoughtResponse]


class FocusEntryResponse(_Strict):
    """One `FocusedThought`. `signals_used` is returned even when empty --
    which, with no focus signal computed anywhere in production, is always."""

    thought: ThoughtResponse
    score: float
    signals_used: list[str]

    @classmethod
    def of(cls, entry: FocusedThought) -> FocusEntryResponse:
        return cls(
            thought=ThoughtResponse.of(entry.thought),
            score=entry.score,
            signals_used=[signal.value for signal in entry.signals_used],
        )


class FocusResponse(_Strict):
    capacity: int
    entries: list[FocusEntryResponse]


class SensorStateResponse(_Strict):
    """One current record from `cognitive_state.sensor_state` (A-4F7-1).

    `state` is `perception-engine`'s `SensorState` vocabulary exactly (A-4F7-2),
    under the same field name `perception-engine`'s own REST uses. `reported_at`
    is dispatch time, not transition time (TDD 4F.7 §7.3)."""

    sensor_id: str
    sensor_type: str
    state: SensorLifecycleState
    reported_at: datetime

    @classmethod
    def of(cls, record: SensorStateRecord) -> SensorStateResponse:
        return cls(
            sensor_id=record.sensor_id,
            sensor_type=record.sensor_type,
            state=record.state,
            reported_at=record.reported_at,
        )


class SensorStateListResponse(_Strict):
    sensors: list[SensorStateResponse]


@router.get("/thoughts", response_model=ThoughtListResponse)
async def list_active_thoughts(request: Request) -> ThoughtListResponse:
    state = request.app.state
    thoughts = await state.repository.list_thoughts(user_id=state.settings.primary_user_id)
    return ThoughtListResponse(thoughts=[ThoughtResponse.of(thought) for thought in thoughts])


@router.get("/focus", response_model=FocusResponse)
async def current_focus(request: Request) -> FocusResponse:
    """`select_focus`, unchanged, with **no** signals supplied: focus-signal
    computation is OPEN, and supplying one here would decide it."""
    state = request.app.state
    capacity = state.settings.focus_capacity
    thoughts = await state.repository.list_thoughts(user_id=state.settings.primary_user_id)
    entries = select_focus(thoughts, capacity=capacity, inputs=None)
    return FocusResponse(
        capacity=capacity, entries=[FocusEntryResponse.of(entry) for entry in entries]
    )


@router.get("/sensors", response_model=SensorStateListResponse)
async def sensor_states(request: Request) -> SensorStateListResponse:
    records = await request.app.state.repository.list_sensor_states()
    return SensorStateListResponse(sensors=[SensorStateResponse.of(record) for record in records])
