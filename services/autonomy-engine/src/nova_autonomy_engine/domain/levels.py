"""Autonomy Level semantics -- TDD 4D §1 row 2, §4.3, §12; decision **D-1**.

Three properties are enforced here and nowhere else, so there is exactly one
place to change them when 4F enables Level 2:

1. **Levels 0-5 are all named** (`AutonomyLevel`) so the vocabulary matches
   Bible Part 14 and nobody invents a seventh.
2. **Levels 0-2 are defined**; 3-5 are named only.
3. **Levels 0-2 are selectable** since 4F.5; 3-5 are rejected, and TDD 4D §13
   binds that rejection to a **422 with the reason, never a silent clamp**.
   *(Read "Levels 0-1 are selectable. Level 2 is defined and disabled" until
   4F.5 enabled it.)*

**`permits_execution` answers eligibility, not permission.** It returns `True`
from Level 2 up, and that on its own authorizes nothing: `domain/decision.py`
dispatches only when every precondition in TDD 4F.5 §22.4 holds independently.
A caller that needs to ask the question gets a straight answer instead of the
question being absent and later answered by assumption.

*(In 4D this returned `False` unconditionally. The guarantee that a flag alone
cannot create execution is unchanged -- it now lives in
`decision._require_execution_path`, which asserts the execution path is wired
rather than that the flag is unset.)*
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
    on a `False`. Levels 3-5 are rejected because they are named in the
    vocabulary without defined semantics.

    *(Until 4F.5 this also rejected Level 2, which was defined but disabled by
    D-1. 4F.5 enabled it; selecting it grants eligibility, not permission --
    see `permits_execution`.)*
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
    """**Eligibility, never permission** -- TDD 4F.5 **D-4F5-4**, §22.4.

    `True` from Level 2 (`ASSISTED`, *"Low risk actions execute
    automatically"*) upward. **This answers one question only: is this level
    the kind of level at which unattended execution is conceivable at all?**

    It is emphatically **not** an authorization. A `True` here means nothing on
    its own: `domain/decision.py` dispatches only when every precondition in
    §22.4 holds independently -- an affirmative in-bounds `AUTO_EXECUTE`
    policy, the Permission Matrix, no Trust denial, the execution fields, a
    wired dispatch path, and no deny gate. Any one of them failing produces a
    suggestion and no `action.execute`.

    *(This returned `False` unconditionally in 4D -- "there is no level,
    selectable or merely defined, at which this returns `True`" -- because D-1
    deferred enabling Level 2 to 4F. 4F.5 is that milestone. The protection
    against a flag-only enablement did not go away; it moved into
    `_require_execution_path`, which now asserts the path exists rather than
    that the flag is unset.)*
    """
    return level >= AutonomyLevel.ASSISTED


def level_name(level: AutonomyLevel) -> str:
    """Bible Part 14's own wording, for the API and the panel."""
    return AUTONOMY_LEVEL_NAMES[level]
