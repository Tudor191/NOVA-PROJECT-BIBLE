"""Workspace observation -- normalization and enrichment (TDD 4F §9, §20.2).

The filesystem sensor in `nova-companion` (4F.3) reports *"this path changed"*.
Between that and `perception.workspace.observed` sit three transformations,
each of which exists because publishing the raw signal would be wrong:

1. **Hashing.** A filesystem path is user data -- it carries directory names,
   project names, sometimes a person's name. `WorldObject`'s own docstring
   sanctions *"a window handle, **a file path hash**, a project UUID"* as the
   object handle, so the hash *is* the contract's identifier, not a redaction
   applied to one. `object_id_for_path` is the only way an `object_id` is
   produced, and the raw path never leaves this module.
2. **Debounce/coalesce.** An editor writing a file emits several OS events in
   a burst. Publishing each one would put the same object on the bus repeatedly
   for a single human action.
3. **Enrichment.** AC-7 speaks of a *"known project"*. When correlation fails
   the observation is published with `project_id=None` -- an honest unknown,
   never a guess (§9).

Pure functions and one small stateful debouncer; no I/O, no `app.state`, so
this stays inside `domain/` per `domain/ports.py`'s own rule.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import PurePath
from uuid import UUID

__all__ = [
    "WorkspaceObservation",
    "WorkspaceObservationDebouncer",
    "label_for_path",
    "object_id_for_path",
    "resolve_project_id",
]

_HASH_PREFIX = "ws"


def object_id_for_path(path: str) -> str:
    """A stable, opaque handle for a workspace path.

    **SHA-256 over the normalized path, hex, prefixed.** The prefix makes the
    value self-describing in a log line without revealing anything; the digest
    makes it stable across observations of the same file, which is what lets
    `world-model-engine` recognise a second observation of an object it has
    already seen and move it `Idle -> Active` rather than creating a duplicate.

    **The raw path is not recoverable from the result**, which is the point:
    a directory tree is user data, and the bus is not where it belongs. This
    is a one-way function by choice -- nothing in 4F needs to reverse it, and
    if something later does, it needs a design decision rather than a
    reversible encoding slipped in here.

    Raises on an empty path rather than hashing `""` into a plausible-looking
    handle: the consumer requires a non-empty `object_id`, and a digest of
    nothing would satisfy that check while meaning nothing.
    """
    normalized = path.strip()
    if not normalized:
        raise ValueError("workspace path must not be empty")
    digest = hashlib.sha256(PurePath(normalized).as_posix().encode("utf-8")).hexdigest()
    return f"{_HASH_PREFIX}-{digest}"


def label_for_path(path: str) -> str:
    """The final path segment -- what a human calls the thing.

    **A name, never the path.** `WorldObject.label` is display text, so a full
    path here would put the very data `object_id_for_path` exists to keep off
    the bus straight back onto it in the next field. One segment is enough to
    be useful in the panel and carries no directory structure.
    """
    normalized = path.strip()
    if not normalized:
        raise ValueError("workspace path must not be empty")
    return PurePath(normalized).name or normalized


def resolve_project_id(object_id: str, known: dict[str, UUID]) -> UUID | None:
    """AC-7's *"known project"* correlation -- or an honest `None`.

    Keyed by `object_id`, never by path: this function never sees a path, and
    the correlation table it is given is built from hashes for the same reason.

    **A miss returns `None`, and that is a result rather than a failure.**
    §9 is explicit that a failed correlation publishes without a `project_id`,
    so there is deliberately no fallback, no nearest-match and no default
    project -- each of which would be a guess wearing a UUID.
    """
    return known.get(object_id)


@dataclass
class WorkspaceObservation:
    """One normalized observation, ready to be shaped into a payload."""

    object_id: str
    label: str
    sensor_id: str
    observed_at: datetime
    project_id: UUID | None = None


@dataclass
class WorkspaceObservationDebouncer:
    """Coalesces a burst of observations of the same object into one.

    A single save in an editor typically produces several filesystem events
    within a few hundred milliseconds. Each is a real OS event -- none is
    fabricated -- but they describe one action, and publishing all of them
    would put the same object on the bus repeatedly and move it through the
    same state transition several times.

    **Keyed by `(object_id, sensor_id)`**, so two sensors observing the same
    object are not collapsed into one: that is genuinely two observations.

    **Time comes from the observation, never from a clock this class reads.**
    `admit` takes `observed_at` from the real OS event, which keeps this
    testable without a fake clock -- §20.1 forbids fake clocks and time
    simulation, and a debouncer that called `datetime.now()` internally could
    only be tested by freezing one.
    """

    window: timedelta
    _last_seen: dict[tuple[str, str], datetime] = field(default_factory=dict)

    def admit(self, observation: WorkspaceObservation) -> bool:
        """`True` if this observation should be published.

        The first observation of an object is always admitted. A later one is
        admitted only once `window` has elapsed since the last **admitted**
        one -- not since the last *seen* one, or a fast enough stream would
        push the deadline forward forever and nothing would ever publish.
        """
        key = (observation.object_id, observation.sensor_id)
        previous = self._last_seen.get(key)
        if previous is not None and observation.observed_at - previous < self.window:
            return False
        self._last_seen[key] = observation.observed_at
        return True
