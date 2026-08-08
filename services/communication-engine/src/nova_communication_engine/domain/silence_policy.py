"""Silence & interruption policy (docs/design/phase-2d/
04-conversation-intelligence.md Sec5) -- interruption recovery (Sec5.1) and
do-not-disturb/notification gating (Sec5.2, Sec5.3). Pure decision
functions; callers (event handlers) are responsible for persisting the
decision and recording a `ConversationDecisionTrace` (Sec15).

Bible Part 13's full "Communication Policies" (activity-aware rules like
"never interrupt while gaming") need desktop/activity sensing this project
does not have until Phase 4 (`nova-companion`, Master Blueprint Sec3.2).
This module ships the honest subset available without it: an explicit
`dnd_override` toggle and "a session is already active" as the one activity
signal this phase genuinely has (Sec5.2) -- named extension points for
activity-specific triggers are not implemented here, matching Doc 23 Sec6's
standing rule against claiming a capability this phase does not have.
"""

from __future__ import annotations

from nova_communication_engine.domain.models import ConversationSession, ConversationState

__all__ = ["should_suppress_proactive_notification"]

_ACTIVE_STATES = frozenset(
    {
        ConversationState.LISTENING,
        ConversationState.THINKING,
        ConversationState.SPEAKING,
        ConversationState.WAITING,
    }
)
"""Sec5.2 -- a session in any of these states already has the user's
attention; a competing proactive notification should queue, not interrupt
(the existing `Notification` model, `01-communication-engine.md` Sec10,
already queues rather than interrupts -- this function decides whether a
notification is even eligible for immediate delivery, not how queuing
itself works)."""


def should_suppress_proactive_notification(session: ConversationSession | None) -> bool:
    """Sec5.2/Sec5.3 -- `True` when a candidate proactive utterance
    (`communication.intent.deliver.request` with no corresponding recent
    inbound turn) should be queued rather than delivered immediately: the
    session's own `dnd_override` is set, or the session is already
    mid-conversation. `session=None` (no session context, e.g. a
    system-wide notification) is never suppressed by this function -- an
    absent session carries no do-not-disturb signal to suppress with."""
    if session is None:
        return False
    if session.dnd_override:
        return True
    return session.state in _ACTIVE_STATES
