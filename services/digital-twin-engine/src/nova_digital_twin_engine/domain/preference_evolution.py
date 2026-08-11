"""Preference Evolution (docs/design/phase-2d/06-personal-companion.md,
Bible Part 16): "Preferences change. The Digital Twin should detect changes
gradually. Never overwrite existing preferences immediately. Require
consistent evidence. Maintain preference history."

`evolve_field` is the literal, generic implementation of that discipline --
it takes an already-computed `candidate` value as a plain argument, so it
never itself infers or classifies anything from raw content (`models.py`'s
own module docstring explains why no production call site feeds it a real
candidate yet this phase: no evidence source for
`verbosity`/`technical_depth`/`terminology_preference`/`conversation_pacing`/
`habit_timing_hint` has been approved). This module is fully testable and
correct today regardless of that -- exactly the "defined now, wired later"
precedent this codebase already uses elsewhere.
"""

from __future__ import annotations

from datetime import UTC, datetime

from nova_digital_twin_engine.domain.models import CommunicationProfile, PreferenceEvolutionEntry

__all__ = ["MIN_CONSISTENT_OBSERVATIONS", "evolve_field"]

MIN_CONSISTENT_OBSERVATIONS = 3
"""Bible Part 16's "require consistent evidence" -- the number of most-
recent candidate observations for a field that must all agree before the
profile's current value actually changes. An implementation-time constant,
not an architectural fork (mirrors reasoning-engine's own
`MAX_HYPOTHESIS_RETRIES`-style named, visible bound)."""


def evolve_field(
    *,
    profile: CommunicationProfile,
    field: str,
    candidate: str,
    pending_observations: list[str],
    confidence: float,
    source: str,
    min_consistent_observations: int = MIN_CONSISTENT_OBSERVATIONS,
) -> tuple[CommunicationProfile, list[str], PreferenceEvolutionEntry | None]:
    """Appends `candidate` to `pending_observations` (bounded to the most
    recent `min_consistent_observations`); the profile's `field` changes
    only once every entry in that bounded window agrees -- a single data
    point, however confident, never overwrites the current value. Returns
    `(profile, pending_observations)` unchanged (plus `None` in place of an
    evolution entry) when no promotion happens, so a caller can always
    persist the returned triple unconditionally without branching on
    whether anything actually changed.

    `field` must name one of `CommunicationProfile`'s five learned fields;
    this function does not validate that itself (Pydantic's own
    `model_copy` raises on an unknown field name, which is diagnostic
    enough -- no separate check would add real safety)."""
    updated_pending = [*pending_observations, candidate][-min_consistent_observations:]

    already_current = getattr(profile, field) == candidate
    not_enough_evidence = len(updated_pending) < min_consistent_observations
    inconsistent = len(set(updated_pending)) > 1
    if already_current or not_enough_evidence or inconsistent:
        return profile, updated_pending, None

    previous = getattr(profile, field)
    updated_profile = profile.model_copy(
        update={field: candidate, "source": "learned", "updated_at": datetime.now(UTC)}
    )
    entry = PreferenceEvolutionEntry(
        user_id=profile.user_id,
        field=field,
        previous_value=previous,
        new_value=candidate,
        confidence=confidence,
        source=source,
        reason=(
            f"{min_consistent_observations} consecutive consistent observations "
            f"of {field!r}={candidate!r}"
        ),
    )
    return updated_profile, updated_pending, entry
