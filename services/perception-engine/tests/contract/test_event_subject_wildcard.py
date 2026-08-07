"""Event contract tests (docs/design/phase-2d/03-perception-engine.md §13.2,
§20): the `perception.*.observed` wildcard-match/non-match distinction,
verified with the actual subject-matching mechanism this codebase's Event
Bus uses (`fnmatch.fnmatchcase` -- `nova_eventbus_sdk.boundary._matches_any`
and the in-memory backend's own `publish()` routing both use it), not just
asserted by naming convention.
"""

from __future__ import annotations

from fnmatch import fnmatchcase

from nova_perception_engine.events.published import PUBLISHABLE_SUBJECTS

_WORLD_MODEL_WILDCARD = "perception.*.observed"

_SHOULD_MATCH = {
    "perception.presence.observed",
    "perception.identity.observed",
    "perception.attention.observed",
}

_SHOULD_NOT_MATCH = {
    "perception.wake.detected",
    "perception.addressee_signal.candidate",
    "perception.consent.changed",
    "perception.sensor.health_changed",
}


def test_every_declared_perception_subject_is_classified() -> None:
    """Guards against a new subject being added to `published.py` without
    also being added to one of the two sets above."""
    declared_perception_subjects = {
        s for s in PUBLISHABLE_SUBJECTS if s.startswith("perception.")
    }
    assert declared_perception_subjects == _SHOULD_MATCH | _SHOULD_NOT_MATCH


def test_state_of_reality_subjects_match_world_models_wildcard() -> None:
    for subject in _SHOULD_MATCH:
        assert fnmatchcase(subject, _WORLD_MODEL_WILDCARD), subject


def test_trigger_and_candidate_subjects_do_not_match_world_models_wildcard() -> None:
    for subject in _SHOULD_NOT_MATCH:
        assert not fnmatchcase(subject, _WORLD_MODEL_WILDCARD), subject


def test_ai_model_rpc_subjects_are_declared_publishable() -> None:
    """§0.2's four RPC calls -- declared in `published.py` even though they
    read like something this engine "receives a reply to" (`BoundEventBus.
    request()` checks the publishable allow-list, not subscribable)."""
    assert {
        "ai_model.detect_wake_phrase.request",
        "ai_model.embed_voice.request",
        "ai_model.embed_face.request",
        "ai_model.estimate_gaze.request",
    }.issubset(PUBLISHABLE_SUBJECTS)
