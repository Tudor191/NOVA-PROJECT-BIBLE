"""Clarification Engine (docs/design/phase-2d/04-conversation-intelligence.md
Sec6) -- addressee-ambiguity clarification only. General content-level
clarification (Reasoning Engine asking the user for more information about
*what* they want) is explicitly out of this phase's scope (Sec6's own scope
statement) -- this engine has no channel to request that from Reasoning
Engine yet, and inventing one here would be exactly the kind of
undisclosed scope expansion this project's standing discipline forbids.

Templated-only, never generated text -- this engine never generates
content (Sec0.2 of this document; `domain/intent_gate.py`'s own docstring).
Every function here is a pure string formatter over already-structured
data, never a call to any model or another engine.
"""

from __future__ import annotations

__all__ = ["ADDRESSEE_CHECK_IN_CUE", "RESUME_OFFER_FALLBACK", "resume_offer"]

ADDRESSEE_CHECK_IN_CUE = "Yes?"
"""Sec4/Sec6.1 -- the lowest-cost possible acknowledgment for an addressee-
fusion `uncertain`-tier moment (Master Blueprint Sec5 item 4): a brief
check-in, not a full unsolicited response, never a generated question."""

RESUME_OFFER_FALLBACK = "Want me to continue where we left off?"
"""Sec5.1/Sec6.1 -- used when the interrupted session has no `objective`
recorded to reference by name."""


def resume_offer(*, objective: str | None) -> str:
    """Sec5.1/Sec6.1's fixed interruption-resume template. `objective` is
    sourced from the existing `ConversationSession.objective` field
    (`01-communication-engine.md` Sec3.2), never freely generated -- this
    function only ever formats a value this engine already has, it never
    invents one."""
    if objective:
        return f"{objective} -- want me to continue?"
    return RESUME_OFFER_FALLBACK
