from uuid import uuid4

from nova_digital_twin_engine.domain import preference_evolution
from nova_digital_twin_engine.domain.models import CommunicationProfile


def _profile(**overrides: object) -> CommunicationProfile:
    return CommunicationProfile(user_id=uuid4(), **overrides)  # type: ignore[arg-type]


def test_single_observation_never_overwrites_the_current_value() -> None:
    profile = _profile()
    updated, pending, entry = preference_evolution.evolve_field(
        profile=profile,
        field="verbosity",
        candidate="concise",
        pending_observations=[],
        confidence=0.9,
        source="test",
    )
    assert updated.verbosity == "moderate"
    assert updated.source == "static_default"
    assert entry is None
    assert pending == ["concise"]


def test_inconsistent_observations_never_promote() -> None:
    profile = _profile()
    pending: list[str] = []
    for candidate in ("concise", "verbose", "concise"):
        profile, pending, entry = preference_evolution.evolve_field(
            profile=profile,
            field="verbosity",
            candidate=candidate,
            pending_observations=pending,
            confidence=0.9,
            source="test",
        )
        assert entry is None
    assert profile.verbosity == "moderate"


def test_consistent_observations_promote_the_field_and_emit_a_history_entry() -> None:
    profile = _profile()
    pending: list[str] = []
    entry = None
    for _ in range(3):
        profile, pending, entry = preference_evolution.evolve_field(
            profile=profile,
            field="verbosity",
            candidate="concise",
            pending_observations=pending,
            confidence=0.9,
            source="test",
        )
    assert profile.verbosity == "concise"
    assert profile.source == "learned"
    assert entry is not None
    assert entry.field == "verbosity"
    assert entry.previous_value == "moderate"
    assert entry.new_value == "concise"
    assert entry.confidence == 0.9
    assert entry.source == "test"


def test_already_current_value_never_re_promotes() -> None:
    """A candidate matching the value already in place is not new evidence
    of a change -- no entry, no pending-window churn needed to reach it."""
    profile = _profile(verbosity="concise")
    updated, pending, entry = preference_evolution.evolve_field(
        profile=profile,
        field="verbosity",
        candidate="concise",
        pending_observations=[],
        confidence=0.9,
        source="test",
    )
    assert updated is profile or updated.verbosity == "concise"
    assert entry is None


def test_pending_window_is_bounded_to_min_consistent_observations() -> None:
    profile = _profile()
    pending: list[str] = []
    for candidate in ("verbose", "verbose", "concise", "concise", "concise"):
        profile, pending, entry = preference_evolution.evolve_field(
            profile=profile,
            field="verbosity",
            candidate=candidate,
            pending_observations=pending,
            confidence=0.9,
            source="test",
        )
    assert pending == ["concise", "concise", "concise"]
    assert profile.verbosity == "concise"


def test_custom_threshold_is_respected() -> None:
    profile = _profile()
    updated, pending, entry = preference_evolution.evolve_field(
        profile=profile,
        field="verbosity",
        candidate="concise",
        pending_observations=["concise"],
        confidence=0.9,
        source="test",
        min_consistent_observations=2,
    )
    assert updated.verbosity == "concise"
    assert entry is not None
