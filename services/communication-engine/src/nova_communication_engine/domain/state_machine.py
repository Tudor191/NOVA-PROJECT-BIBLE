"""The `ConversationSession` state machine -- Bible Part 13's ten states,
implemented as an explicit transition table, not implicit flags (design doc
Sec3.1): the Live Communication Dashboard, and any future UI, must be able
to render the *real* current state, never an approximation.

Two implementation clarifications the diagram in design doc Sec3.1 leaves
implicit, made explicit here rather than silently assumed:

1. **`WAITING -> LISTENING` on a new trigger.** The diagram draws `Idle
   --trigger--> Listening` for session start, but a multi-turn conversation
   needs the identical mechanism to start every later turn too. `Waiting`
   (NOVA has delivered a response and is waiting for the user) is the state
   that recurs for every turn after the first, so it accepts the same
   `TRIGGER` event `Idle` does.
2. **`Paused -> Listening` on resume, always.** Design doc Sec3.2's required-
   fields table has no `state_before_pause` column, so "resume to the state
   prior to pause" is implemented as "resume to `Listening`, ready for the
   user's next input" -- the same natural resumption point restart recovery
   (Sec3.5) already uses, rather than inventing a field the approved schema
   doesn't have.

Restart recovery (Sec3.5) is deliberately **not** modeled as a table
transition -- it is an operational safety net applied directly by
`repository`/`main.py` at startup, not a domain event a live session ever
raises during normal operation.
"""

from __future__ import annotations

from enum import StrEnum

from nova_communication_engine.domain.models import ConversationState

__all__ = ["ConversationEvent", "InvalidTransitionError", "transition", "valid_events_from"]


class ConversationEvent(StrEnum):
    """The Sec3.1-diagram edges this engine's own pipeline actually raises
    this phase. `CLARIFICATION` (Waiting from Thinking) is not listed --
    design doc Sec0.4/Sec6: the Clarification Engine is 2D-C scope, not yet
    reachable."""

    TRIGGER = "trigger"
    CAPTURED = "captured"
    CONTENT_READY = "content_ready"
    DELIVERED = "delivered"
    BARGE_IN = "barge_in"
    CLOSE = "close"
    PAUSE = "pause"
    RESUME = "resume"


class InvalidTransitionError(ValueError):
    def __init__(self, current: ConversationState, event: ConversationEvent) -> None:
        super().__init__(f"Cannot apply {event.value!r} from state {current.value!r}.")
        self.current = current
        self.event = event


_TRANSITIONS: dict[tuple[ConversationState, ConversationEvent], ConversationState] = {
    (ConversationState.IDLE, ConversationEvent.TRIGGER): ConversationState.LISTENING,
    (ConversationState.WAITING, ConversationEvent.TRIGGER): ConversationState.LISTENING,
    (ConversationState.LISTENING, ConversationEvent.CAPTURED): ConversationState.THINKING,
    (ConversationState.THINKING, ConversationEvent.CONTENT_READY): ConversationState.SPEAKING,
    (ConversationState.SPEAKING, ConversationEvent.DELIVERED): ConversationState.WAITING,
    (ConversationState.SPEAKING, ConversationEvent.BARGE_IN): ConversationState.LISTENING,
    (ConversationState.WAITING, ConversationEvent.CLOSE): ConversationState.COMPLETED,
    (ConversationState.LISTENING, ConversationEvent.PAUSE): ConversationState.PAUSED,
    (ConversationState.THINKING, ConversationEvent.PAUSE): ConversationState.PAUSED,
    (ConversationState.SPEAKING, ConversationEvent.PAUSE): ConversationState.PAUSED,
    (ConversationState.WAITING, ConversationEvent.PAUSE): ConversationState.PAUSED,
    (ConversationState.PAUSED, ConversationEvent.RESUME): ConversationState.LISTENING,
}


def transition(current: ConversationState, event: ConversationEvent) -> ConversationState:
    """Raises `InvalidTransitionError` for any (state, event) pair not in
    Sec3.1's diagram -- an invalid transition is a caller bug, never
    silently ignored or coerced to the nearest valid state."""
    key = (current, event)
    if key not in _TRANSITIONS:
        raise InvalidTransitionError(current, event)
    return _TRANSITIONS[key]


def valid_events_from(current: ConversationState) -> frozenset[ConversationEvent]:
    return frozenset(event for (state, event) in _TRANSITIONS if state == current)
