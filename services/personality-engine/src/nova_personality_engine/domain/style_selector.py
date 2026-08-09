"""The Style Selector (docs/design/phase-2d/02-personality-engine.md Sec5) --
a deterministic rule table keyed on caller-supplied context hints, not a
learned or adaptive selector this phase (Master Blueprint Sec4.3 assigns real
adaptive selection to Phase 2D-C, extending this same module later).
`professional` is the default when no hint is supplied.

Phase 2D-C Closure Priority 5 (docs/roadmap/architecture-reviews/
phase-2d-c-closure-priority-5-research.md, Fork A/B, user-approved
A1/B1) makes `channel` load-bearing for `verbosity` only -- see
`select_style`'s own docstring for the exact rule and its disclosed
limitation.
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

_VOICE_CHANNEL = "voice"
_VOICE_VERBOSITY_OVERRIDE = "concise"
"""Doc 23 Sec2's own "Channel (voice vs. text) | Adaptive" row, translated
into the smallest defensible rule (Priority 5 research Sec2.9/Fork B,
user-approved B1): a fixed override to the one verbosity value already
used elsewhere in this codebase's own test fixtures, not a graduated
scale -- no ADR, Bible section, Doc 23, or TDD defines an ordered
verbosity taxonomy to cap against, and inventing one here would be exactly
the "channel-specific behavior merely because the field exists" the
approved research explicitly declined to do."""


def select_style(
    *, situation_hint: str | None, channel: str | None, memory_profile: MemoryProfile
) -> tuple[CommunicationStyle, str, str]:
    """Returns `(style, verbosity, technical_depth)`. `style`/`technical_depth`
    are never affected by `channel` -- only `verbosity`, preserving
    Personality Consistency (Doc 23 Sec2: "Personality remains constant,
    expression adapts"). `channel == "voice"` overrides `verbosity` to a
    fixed, concise value instead of the resolved `memory_profile.verbosity`;
    every other channel value, including `None`, leaves `memory_profile.
    verbosity` completely unchanged -- the pre-existing, unmodified default
    path.

    **Not yet end-to-end observable** (Priority 5 research Sec2.6,
    re-confirmed unchanged at implementation time): `communication-engine`'s
    `resolve_response_shaping()` -- the only caller anywhere in this
    codebase that could ever pass a real, non-`None` channel value -- is
    not called by any production turn-handling path. This function is
    correct and tested in isolation; no live conversation reaches it with a
    real channel value today. Left deliberately unresolved by Priority 5's
    own approved scope (Fork C, decision C1) -- see the research document
    for why."""
    style = _SITUATION_HINT_TO_STYLE.get(
        situation_hint.lower() if situation_hint else "", CommunicationStyle.PROFESSIONAL
    )
    verbosity = _VOICE_VERBOSITY_OVERRIDE if channel == _VOICE_CHANNEL else memory_profile.verbosity
    return style, verbosity, memory_profile.technical_depth
