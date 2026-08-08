"""Response shaping (docs/design/phase-2d/04-conversation-intelligence.md
Sec7/Sec8) -- resolves the `ResponseShapingDirective` this engine publishes
alongside `communication.turn.received` (Sec10). This engine never applies
the directive to generated content itself (Sec0.1: it never generates
content) -- it only computes and publishes the resolved policy for a
content-source engine to honor (Sec0.7's own disclosed finding: no such
consumer exists in this codebase yet, so this directive currently has no
observable effect on delivered text).

`digital_twin.preferences.get` is deliberately never called this phase
(Sec0.10) -- `personality-engine`'s existing static-default Personality
Memory is the sole preference source until Phase 2D-D's `digital-twin-engine`
exists; calling an RPC nothing serves would add a guaranteed-timeout hop to
every turn, violating Master Blueprint Sec13.2's low-latency tie-break rule
for zero benefit.

`personality-engine`'s own `channel` parameter to `personality.style.select`
is documented but currently inert (confirmed by direct code inspection this
session) -- passed through here unchanged (the existing, already-approved
client contract), but style selection will not actually vary by channel
until that engine's own fix lands (TDD Sec7/Sec21 item 4, explicitly out of
this pass's prerequisite scope, tracked as a separate, disclosed follow-up).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from nova_communication_engine.domain.ports import PersonalityPort

__all__ = ["ResponseShapingResult", "derive_situation_hint", "resolve_response_shaping"]

_DEGRADED_STYLE = "professional"
_DEGRADED_VERBOSITY = "moderate"
_DEGRADED_TECHNICAL_DEPTH = "moderate"
"""Sec13's documented fallback -- the same hardcoded minimal-safe default
`domain/intent_gate.py`'s own Sec9 fallback uses, applied here for the
identical reason: an unreachable `personality-engine` degrades response
shaping, it never blocks delivery (Doc 22 Principle 3)."""


def derive_situation_hint(
    *, recent_correction_count: int = 0, recent_clarification_count: int = 0
) -> str | None:
    """Sec0.9 -- a narrow, rule-based heuristic, not ML sentiment
    classification (Doc 23 Sec6's honest-scope discipline; full
    ML-based emotion detection is named there as an explicit, deferred
    future capability, mirroring `personality-engine`'s own design doc
    Sec5/Sec17). Derived only from structural counts this engine already
    tracks (repeated corrections/clarifications within a session) -- never
    from parsing turn content, which stays Reasoning Engine's job (Sec0.1:
    this engine never generates or classifies content)."""
    if recent_correction_count >= 2 or recent_clarification_count >= 2:
        return "frustration"
    return None


@dataclass(frozen=True)
class ResponseShapingResult:
    style: str
    verbosity: str
    technical_depth: str
    situation_hint: str | None
    degraded: bool
    """`True` when `personality.style.select` was unreachable and Sec13's
    documented minimal-safe default was used instead."""


async def resolve_response_shaping(
    *,
    personality_port: PersonalityPort,
    channel: str,
    situation_hint: str | None,
    correlation_id: UUID | None = None,
) -> ResponseShapingResult:
    try:
        selection = await personality_port.select_style(
            situation_hint=situation_hint, channel=channel, correlation_id=correlation_id
        )
    except TimeoutError:
        return ResponseShapingResult(
            style=_DEGRADED_STYLE,
            verbosity=_DEGRADED_VERBOSITY,
            technical_depth=_DEGRADED_TECHNICAL_DEPTH,
            situation_hint=situation_hint,
            degraded=True,
        )
    return ResponseShapingResult(
        style=selection.style,
        verbosity=selection.verbosity,
        technical_depth=selection.technical_depth,
        situation_hint=situation_hint,
        degraded=False,
    )
