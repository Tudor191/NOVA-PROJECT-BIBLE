"""Workspace normalization and enrichment -- TDD 4F §9, §20.2.

The security-critical property here is negative: **a raw filesystem path must
never reach the payload.** Most of these tests are about proving an absence,
which is why they assert on the *output* rather than on the call.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from nova_perception_engine.domain.workspace import (
    WorkspaceObservation,
    WorkspaceObservationDebouncer,
    label_for_path,
    object_id_for_path,
    resolve_project_id,
)

PATH = "/home/ada/projects/analytical-engine/notes.md"


def _observation(*, object_id: str = "ws-abc", at: datetime | None = None) -> WorkspaceObservation:
    return WorkspaceObservation(
        object_id=object_id,
        label="notes.md",
        sensor_id="companion-filesystem",
        observed_at=at or datetime.now(UTC),
    )


# --- the path never travels ----------------------------------------------


def test_the_object_id_does_not_contain_the_path_or_any_segment_of_it() -> None:
    """The property that matters, stated directly: nothing recognisable from
    the path survives into the handle."""
    object_id = object_id_for_path(PATH)
    assert PATH not in object_id
    for segment in ("home", "ada", "projects", "analytical-engine", "notes"):
        assert segment not in object_id


def test_the_object_id_contains_no_path_separator() -> None:
    object_id = object_id_for_path(PATH)
    assert "/" not in object_id.removeprefix("ws-")
    assert "\\" not in object_id


def test_the_object_id_is_a_prefixed_sha256_hex_digest() -> None:
    object_id = object_id_for_path(PATH)
    assert object_id.startswith("ws-")
    digest = object_id.removeprefix("ws-")
    assert len(digest) == 64
    assert all(character in "0123456789abcdef" for character in digest)


def test_the_same_path_always_produces_the_same_handle() -> None:
    """Stability is what lets the consumer recognise a second observation of
    an object it already knows and move it `Idle -> Active` rather than
    creating a duplicate."""
    assert object_id_for_path(PATH) == object_id_for_path(PATH)


def test_different_paths_produce_different_handles() -> None:
    assert object_id_for_path(PATH) != object_id_for_path(PATH + ".bak")


def test_an_empty_path_raises_rather_than_hashing_nothing() -> None:
    """A digest of `""` would be a non-empty string, so it would satisfy the
    consumer's non-empty check while identifying nothing."""
    for empty in ("", "   "):
        with pytest.raises(ValueError, match="must not be empty"):
            object_id_for_path(empty)


def test_the_label_is_the_final_segment_only() -> None:
    """`label` is display text. A full path here would put the very data the
    hash exists to keep off the bus straight back onto it."""
    label = label_for_path(PATH)
    assert label == "notes.md"
    assert "/" not in label
    assert "ada" not in label


# --- enrichment: an honest unknown ---------------------------------------


def test_a_failed_project_correlation_returns_none() -> None:
    """§9: *"When correlation fails the observation is published without a
    `project_id`"* -- never a guess, never a default project."""
    assert resolve_project_id("ws-unknown", {}) is None


def test_a_successful_project_correlation_returns_the_project() -> None:
    project_id = uuid4()
    assert resolve_project_id("ws-known", {"ws-known": project_id}) == project_id


def test_correlation_is_keyed_by_handle_not_by_path() -> None:
    """The correlation table never sees a path either."""
    project_id = uuid4()
    known = {object_id_for_path(PATH): project_id}
    assert resolve_project_id(object_id_for_path(PATH), known) == project_id
    assert resolve_project_id(PATH, known) is None


# --- debounce -------------------------------------------------------------


def test_the_first_observation_of_an_object_is_always_admitted() -> None:
    """Debouncing must cost AC-7 nothing: the first observation -- the one
    AC-7 measures -- is never delayed."""
    debouncer = WorkspaceObservationDebouncer(window=timedelta(seconds=1))
    assert debouncer.admit(_observation()) is True


def test_a_burst_within_the_window_is_coalesced() -> None:
    start = datetime.now(UTC)
    debouncer = WorkspaceObservationDebouncer(window=timedelta(seconds=1))
    assert debouncer.admit(_observation(at=start)) is True
    for offset in (0.1, 0.3, 0.9):
        assert debouncer.admit(_observation(at=start + timedelta(seconds=offset))) is False


def test_an_observation_after_the_window_is_admitted_again() -> None:
    start = datetime.now(UTC)
    debouncer = WorkspaceObservationDebouncer(window=timedelta(seconds=1))
    assert debouncer.admit(_observation(at=start)) is True
    assert debouncer.admit(_observation(at=start + timedelta(seconds=1.5))) is True


def test_a_fast_stream_still_publishes_rather_than_starving() -> None:
    """The deadline advances from the last *admitted* observation, not the
    last seen one -- otherwise a fast enough stream would push it forward
    forever and nothing would ever publish."""
    start = datetime.now(UTC)
    debouncer = WorkspaceObservationDebouncer(window=timedelta(seconds=1))
    admitted = [
        debouncer.admit(_observation(at=start + timedelta(seconds=0.4 * step)))
        for step in range(10)
    ]
    assert admitted.count(True) >= 3


def test_two_objects_do_not_debounce_each_other() -> None:
    start = datetime.now(UTC)
    debouncer = WorkspaceObservationDebouncer(window=timedelta(seconds=1))
    assert debouncer.admit(_observation(object_id="ws-one", at=start)) is True
    assert debouncer.admit(_observation(object_id="ws-two", at=start)) is True


def test_the_debouncer_reads_no_clock_of_its_own() -> None:
    """§20.1 forbids fake clocks and time simulation. The debouncer takes its
    time from the real OS event, so these tests need no frozen clock -- and a
    future edit that reached for `datetime.now()` inside `admit` would make
    them untestable without one.
    """
    source = (
        __import__("inspect").getsource(WorkspaceObservationDebouncer.admit).replace("admitted", "")
    )
    assert "now(" not in source
    assert "utcnow" not in source
