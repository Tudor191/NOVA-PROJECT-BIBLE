"""Event Bus subscription handlers for the subjects in `events/subscribed.py`
(docs/design/phase-2d/03-perception-engine.md Sec13.3). Both
`communication.session.created`/`.completed` carry `session_id` and `user_id`
(`nova_contracts.events.communication.CommunicationSessionCreatedPayload`/
`CommunicationSessionCompletedPayload`) -- `make_session_dispatch_handler` is
the single handler registered against both subjects, routing by
`envelope.subject` so a future subscription-list change here never needs a
second competing handler wired in `main.py`.
"""

from __future__ import annotations

from uuid import UUID

from nova_contracts import EventEnvelope
from nova_observability import get_logger

from nova_perception_engine.domain.ports import PerceptionRepository
from nova_perception_engine.domain.session_activity import SessionActivityTracker

__all__ = ["make_known_project_handler", "make_session_dispatch_handler"]

logger = get_logger("perception-engine.events.handlers")


def _uuid_from(payload: dict, key: str) -> UUID | None:
    value = payload.get(key)
    if not value:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def make_session_dispatch_handler(  # type: ignore[no-untyped-def]
    tracker: SessionActivityTracker,
):
    """Feeds `SessionActivityTracker` (Sec10's "is a session currently active
    with this speaker" addressee-candidate input) from `communication-engine`'s
    own session lifecycle -- `.created` marks a session active,
    `.completed` marks it ended. Missing/malformed `user_id`/`session_id` is
    logged and skipped rather than raised, matching every other engine's own
    subscription-handler convention (a malformed upstream event degrades this
    engine's addressee-candidate signal quality, never crashes it)."""

    async def handle(envelope: EventEnvelope) -> None:
        user_id = _uuid_from(envelope.payload, "user_id")
        session_id = _uuid_from(envelope.payload, "session_id")
        if user_id is None or session_id is None:
            logger.warning(
                "communication.session.* missing user_id/session_id, skipping",
                extra={"subject": envelope.subject},
            )
            return

        if envelope.subject == "communication.session.created":
            tracker.session_created(user_id=user_id, session_id=session_id)
        elif envelope.subject == "communication.session.completed":
            tracker.session_ended(user_id=user_id, session_id=session_id)
        else:
            logger.warning(
                "unexpected subject routed to session dispatch handler",
                extra={"subject": envelope.subject},
            )

    return handle


def make_known_project_handler(  # type: ignore[no-untyped-def]
    repository: PerceptionRepository, *, primary_user_id: UUID | None
):
    """Phase 4F.8, A-4F8-2 (a): learn which project identities NOVA holds.

    Each `memory.long_term.created` carrying a `project_id` of this deployment's
    user makes that project known (`perception.known_project`), which activates
    any operator-declared folder binding for it. Nothing else is read from the
    memory: not its content, type or privacy level.

    **Skipped, and logged:** a memory with no `project_id`, which is ordinary;
    a memory of any other user; and every memory while `primary_user_id` is
    unset, the same explicit degrade the workspace route applies. A malformed
    event degrades correlation, never crashes this engine."""

    async def handle(envelope: EventEnvelope) -> None:
        project_id = _uuid_from(envelope.payload, "project_id")
        if project_id is None:
            return
        user_id = _uuid_from(envelope.payload, "user_id")
        if primary_user_id is None or user_id != primary_user_id:
            logger.info(
                "memory.long_term.created not of this deployment's user, skipping",
                extra={"subject": envelope.subject},
            )
            return
        if await repository.record_known_project(
            project_id, source_event_id=envelope.event_id, observed_at=envelope.occurred_at
        ):
            logger.info("project_identity_known", extra={"project_id": str(project_id)})

    return handle
