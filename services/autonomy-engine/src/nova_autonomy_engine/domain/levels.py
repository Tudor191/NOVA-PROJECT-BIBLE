"""Autonomy Level semantics -- TDD 4D §1 row 2, §4.3, §12; decision **D-1**.

Three properties are enforced here and nowhere else, so there is exactly one
place to change them when 4F enables Level 2:

1. **Levels 0-5 are all named** (`AutonomyLevel`) so the vocabulary matches
   Bible Part 14 and nobody invents a seventh.
2. **Levels 0-2 are defined**; 3-5 are named only.
3. **Levels 0-1 are selectable.** Level 2 is defined and *disabled* --
   `require_selectable` rejects it, and TDD §13 binds that rejection to a
   **422 with the reason, never a silent clamp**.

**No function here can return an "execute" verdict.** `permits_execution`
exists and returns `False` unconditionally: 4D's level set contains no level
at which NOVA acts unattended, and a caller that needs to ask the question
gets a straight answer instead of the question being absent and later
answered by assumption.
"""

from __future__ import annotations

from nova_autonomy_engine.domain.models import (
    AUTONOMY_LEVEL_NAMES,
    DEFINED_LEVELS,
    SELECTABLE_LEVELS,
    AutonomyLevel,
)

__all__ = [
    "LevelNotDefinedError",
    "LevelNotSelectableError",
    "level_name",
    "parse_level",
    "permits_execution",
    "permits_proposal",
    "require_selectable",
]


class LevelNotDefinedError(ValueError):
    """The integer is not one of Bible Part 14's six levels at all."""


class LevelNotSelectableError(ValueError):
    """The level exists and is defined, but 4D does not permit selecting it.

    Distinct from `LevelNotDefinedError` on purpose: "Level 2 is real but
    arrives in 4F" and "Level 9 does not exist" are different answers, and
    TDD §13 requires the 422's *reason* to say which.
    """


def parse_level(value: int) -> AutonomyLevel:
    """`AutonomyLevel(value)` with a domain error instead of a bare
    `ValueError`, so the API layer can map it to a 422 without matching on
    exception text."""
    try:
        return AutonomyLevel(value)
    except ValueError as exc:  # pragma: no cover - re-raised with our own type
        raise LevelNotDefinedError(
            f"autonomy level {value} does not exist; Bible Part 14 defines levels "
            f"{min(AutonomyLevel)}-{max(AutonomyLevel)}"
        ) from exc


def require_selectable(level: AutonomyLevel) -> AutonomyLevel:
    """Return `level` unchanged, or raise `LevelNotSelectableError`.

    **Returns the level rather than a bool** so a caller cannot forget to act
    on a `False`. Level 2 is rejected here even though it is *defined*: D-1
    assigns enabling it to 4F, and TDD §16 control 2 requires that making it
    selectable fails the suite.
    """
    if level not in SELECTABLE_LEVELS:
        if level in DEFINED_LEVELS:
            raise LevelNotSelectableError(
                f"autonomy level {int(level)} ({AUTONOMY_LEVEL_NAMES[level]}) is defined "
                f"but not enabled in this release; it is enabled in milestone 4F "
                f"(decision D-1)"
            )
        raise LevelNotSelectableError(
            f"autonomy level {int(level)} ({AUTONOMY_LEVEL_NAMES[level]}) is named in the "
            f"vocabulary but has no defined semantics in this release"
        )
    return level


def permits_proposal(level: AutonomyLevel) -> bool:
    """`False` at Level 0 -- Bible Part 14: *"NOVA never acts. Only monitors
    and reports."* Level 1 (*"NOVA proposes actions"*) and above may
    propose."""
    return level >= AutonomyLevel.SUGGESTIVE


def permits_execution(level: AutonomyLevel) -> bool:
    """**Always `False` in 4D, at every level, by construction.**

    Level 2 (*"Low risk actions execute automatically"*) is the first level
    whose Bible text implies an execute branch, and D-1 defers enabling it to
    4F. Until then there is no level -- selectable or merely defined -- at
    which this returns `True`, and TDD §16 control 1 requires that forcing
    otherwise fails the suite.
    """
    return False


def level_name(level: AutonomyLevel) -> str:
    """Bible Part 14's own wording, for the API and the panel."""
    return AUTONOMY_LEVEL_NAMES[level]
