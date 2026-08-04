from datetime import UTC, datetime, timedelta

from nova_world_model_engine.domain.conflict_resolution import Observation, resolve


def _obs(**overrides: object) -> Observation:
    defaults: dict[str, object] = {
        "object_id": "window:1",
        "value": {"title": "x"},
        "confidence": 0.5,
        "observed_at": datetime.now(UTC),
        "source": "calendar",
    }
    defaults.update(overrides)
    return Observation(**defaults)  # type: ignore[arg-type]


def test_confidence_wins_when_margin_exceeded() -> None:
    now = datetime.now(UTC)
    a = _obs(confidence=0.9, observed_at=now, value={"v": "a"})
    b = _obs(confidence=0.5, observed_at=now, value={"v": "b"})
    result = resolve(a, b)
    assert result.resolution_strategy == "confidence"
    assert result.resolved_value == {"v": "a"}


def test_policy_wins_when_confidence_tied() -> None:
    now = datetime.now(UTC)
    a = _obs(confidence=0.5, source="user", observed_at=now, value={"v": "a"})
    b = _obs(confidence=0.5, source="calendar", observed_at=now, value={"v": "b"})
    result = resolve(a, b)
    assert result.resolution_strategy == "policy"
    assert result.resolved_value == {"v": "a"}  # "user" outranks "calendar"


def test_recency_wins_when_confidence_and_policy_tied() -> None:
    now = datetime.now(UTC)
    a = _obs(confidence=0.5, source="calendar", observed_at=now, value={"v": "old"})
    b = _obs(
        confidence=0.5,
        source="calendar",
        observed_at=now + timedelta(seconds=10),
        value={"v": "new"},
    )
    result = resolve(a, b)
    assert result.resolution_strategy == "recency"
    assert result.resolved_value == {"v": "new"}


def test_unresolved_still_produces_a_value() -> None:
    """§17: "always produces a value... never blocks the write" -- even the
    genuinely-ambiguous branch returns a usable `resolved_value`, just labeled
    `unresolved` rather than claimed as a confident result."""
    now = datetime.now(UTC)
    a = _obs(confidence=0.5, source="calendar", observed_at=now, value={"v": "a"})
    b = _obs(confidence=0.55, source="calendar", observed_at=now, value={"v": "b"})
    result = resolve(a, b)
    assert result.resolution_strategy == "unresolved"
    assert result.resolved_value is not None


def test_never_prefers_recency_without_checking_confidence_first() -> None:
    """Component table's "must never" -- an older, much-more-confident
    observation beats a newer, low-confidence one."""
    now = datetime.now(UTC)
    older_confident = _obs(confidence=0.95, observed_at=now, value={"v": "confident"})
    newer_unsure = _obs(
        confidence=0.2, observed_at=now + timedelta(seconds=10), value={"v": "unsure"}
    )
    result = resolve(older_confident, newer_unsure)
    assert result.resolution_strategy == "confidence"
    assert result.resolved_value == {"v": "confident"}
