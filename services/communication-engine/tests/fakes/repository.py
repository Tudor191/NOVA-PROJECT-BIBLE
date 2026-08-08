"""`FakeCommunicationRepository` -- an in-memory `domain.ports.
CommunicationRepository`, mirroring `PostgresCommunicationRepository`'s own
behavior (design doc Sec10) closely enough that swapping one for the other
in a test changes nothing observable. Every write appends to `outbox` when
an `OutboxEvent` is supplied, so tests can assert exactly what an operation
would have enqueued -- mirroring every prior engine's own fake repository.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from nova_communication_engine.domain.models import (
    ConversationDecisionTrace,
    ConversationMemory,
    ConversationSession,
    ConversationState,
    ConversationTurn,
    Notification,
)
from nova_communication_engine.domain.ports import OutboxEvent, OutboxRow


class FakeCommunicationRepository:
    def __init__(self) -> None:
        self.sessions: dict[UUID, ConversationSession] = {}
        self.notifications: dict[UUID, Notification] = {}
        self.outbox: list[OutboxEvent] = []
        self.decision_traces: list[ConversationDecisionTrace] = []
        self._dispatched: set[int] = set()

    async def create_session(self, session: ConversationSession) -> ConversationSession:
        self.sessions[session.session_id] = session
        return session

    async def get_session(self, session_id: UUID) -> ConversationSession | None:
        return self.sessions.get(session_id)

    async def update_session_state(
        self,
        session_id: UUID,
        *,
        state: str,
        closed_at: datetime | None = None,
        outbox_event: OutboxEvent | None = None,
    ) -> ConversationSession:
        session = self.sessions[session_id]
        updates: dict[str, object] = {"state": ConversationState(state)}
        if closed_at is not None:
            updates["closed_at"] = closed_at
        updated = session.model_copy(update=updates)
        self.sessions[session_id] = updated
        if outbox_event is not None:
            self.outbox.append(outbox_event)
        return updated

    async def append_turn(
        self, turn: ConversationTurn, *, outbox_event: OutboxEvent | None = None
    ) -> ConversationTurn:
        session = self.sessions[turn.session_id]
        updated = session.model_copy(update={"turns": [*session.turns, turn]})
        self.sessions[turn.session_id] = updated
        if outbox_event is not None:
            self.outbox.append(outbox_event)
        return turn

    async def list_non_terminal_sessions(self) -> list[ConversationSession]:
        return [s for s in self.sessions.values() if s.state is not ConversationState.COMPLETED]

    async def create_notification(self, notification: Notification) -> Notification:
        self.notifications[notification.notification_id] = notification
        return notification

    async def enqueue_outbox(self, event: OutboxEvent) -> UUID:
        self.outbox.append(event)
        return uuid4()

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]:
        rows = []
        for i, event in enumerate(self.outbox):
            if i in self._dispatched:
                continue
            rows.append(
                OutboxRow(
                    id=UUID(int=i + 1),
                    subject=event.subject,
                    payload=event.payload,
                    correlation_id=event.correlation_id,
                    causation_id=event.causation_id,
                    created_at=datetime.now(UTC),
                )
            )
            if len(rows) >= limit:
                break
        return rows

    async def mark_dispatched(self, outbox_id: UUID) -> None:
        index = outbox_id.int - 1
        self._dispatched.add(index)

    async def update_conversation_memory(
        self, session_id: UUID, *, memory: ConversationMemory
    ) -> ConversationSession:
        session = self.sessions[session_id]
        updated = session.model_copy(update={"conversation_memory": memory})
        self.sessions[session_id] = updated
        return updated

    async def set_interrupted_content(
        self, session_id: UUID, *, content: str | None
    ) -> ConversationSession:
        session = self.sessions[session_id]
        updated = session.model_copy(update={"interrupted_content": content})
        self.sessions[session_id] = updated
        return updated

    async def set_dnd_override(self, session_id: UUID, *, enabled: bool) -> ConversationSession:
        session = self.sessions[session_id]
        updated = session.model_copy(update={"dnd_override": enabled})
        self.sessions[session_id] = updated
        return updated

    async def create_decision_trace(
        self, trace: ConversationDecisionTrace
    ) -> ConversationDecisionTrace:
        self.decision_traces.append(trace)
        return trace

    async def set_pending_questions(
        self, session_id: UUID, *, questions: list[str] | None
    ) -> ConversationSession:
        session = self.sessions[session_id]
        updated = session.model_copy(update={"pending_questions": questions})
        self.sessions[session_id] = updated
        return updated
