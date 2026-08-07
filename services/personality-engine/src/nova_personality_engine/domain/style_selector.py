"""The Style Selector (docs/design/phase-2d/02-personality-engine.md Sec5) --
a deterministic rule table keyed on caller-supplied context hints, not a
learned or adaptive selector this phase (Master Blueprint Sec4.3 assigns real
adaptive selection to Phase 2D-C, extending this same module later).
`professional` is the default when no hint is supplied.
"""

from __future__ import annotations

from nova_personality_engine.domain.models import CommunicationStyle, MemoryProfile

__all__ = ["select_style"]

_SITUATION_HINT_TO_STYLE: dict[str, CommunicationStyle] = {
    "debugging": CommunicationStyle.ANALYTICAL,
    "learning_session": CommunicationStyle.EDUCATIONAL,
    "emergency": CommunicationStyle.EMERGENCY,
    "executive_meeting": CommunicationStyle.EXECUTIVE,
    "brainstorming": CommunicationStyle.CREATIVE,
    "quick_check": CommunicationStyle.MINIMAL,
    "casual": CommunicationStyle.FRIENDLY,
    "technical_review": CommunicationStyle.TECHNICAL,
}


def select_style(
    *, situation_hint: str | None, channel: str | None, memory_profile: MemoryProfile
) -> tuple[CommunicationStyle, str, str]:
    """Returns `(style, verbosity, technical_depth)`. `channel` is accepted
    for forward compatibility (Master Blueprint Sec13.6) but does not yet
    influence selection -- no Phase 2D-A acceptance criterion depends on
    channel-specific style, and inventing that rule now, untested against
    real usage, would be exactly the "quality over feature count" violation
    Master Blueprint Sec13.7 forbids."""
    style = _SITUATION_HINT_TO_STYLE.get(
        situation_hint.lower() if situation_hint else "", CommunicationStyle.PROFESSIONAL
    )
    return style, memory_profile.verbosity, memory_profile.technical_depth
