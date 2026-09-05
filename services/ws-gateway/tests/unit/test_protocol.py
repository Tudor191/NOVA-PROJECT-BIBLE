"""Unit tests for the public protocol and the topic allow-list."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from fnmatch import fnmatchcase
from pathlib import Path
from uuid import uuid4

import pytest
from nova_contracts import EventEnvelope
from nova_ws_gateway.domain.protocol import (
    PUBLIC_TOPICS,
    MalformedClientMessage,
    parse_client_message,
    partition_topics,
    to_event_frame,
)
from nova_ws_gateway.domain.session import (
    LocalTokenSessionValidator,
    extract_presented_token,
)
from nova_ws_gateway.events.subscribed import SUBSCRIBABLE_SUBJECTS


def _envelope(**overrides: object) -> EventEnvelope:
    base: dict[str, object] = {
        "event_id": uuid4(),
        "subject": "communication.turn.received",
        "occurred_at": datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
        "source_engine": "communication-engine",
        "correlation_id": uuid4(),
        "causation_id": uuid4(),
        "confidence": None,
        "payload": {"text": "hello"},
    }
    base.update(overrides)
    return EventEnvelope(**base)  # type: ignore[arg-type]


# --- authentication -------------------------------------------------------


def test_unconfigured_validator_refuses_every_connection() -> None:
    validator = LocalTokenSessionValidator("")
    assert validator.configured is False
    assert validator.is_valid("anything") is False
    assert validator.is_valid(None) is False


def test_configured_validator_accepts_only_the_token() -> None:
    validator = LocalTokenSessionValidator("tok")
    assert validator.is_valid("tok") is True
    assert validator.is_valid("to") is False
    assert validator.is_valid(None) is False


@pytest.mark.parametrize(
    ("cookie", "header", "expected"),
    [
        ("c", None, "c"),
        (None, "Bearer h", "h"),
        ("c", "Bearer h", "c"),
        (None, "Basic h", None),
        (None, None, None),
    ],
)
def test_token_extraction(
    cookie: str | None, header: str | None, expected: str | None
) -> None:
    assert extract_presented_token(cookie, header) == expected


# --- topic allow-list -----------------------------------------------------


@pytest.mark.parametrize(
    ("pattern", "subject", "expected"),
    [
        ("reasoning.process.*", "reasoning.process.completed", True),
        ("reasoning.process.*", "reasoning.human_override.applied", False),
        ("communication.*", "communication.turn.received", True),
        ("action.approval.*", "action.approval.requested", True),
        ("action.approval.*", "action.execution.started", False),
        ("nova.heartbeat", "nova.heartbeat", True),
        ("nova.heartbeat", "nova.mode.changed", False),
    ],
)
def test_the_guard_below_matches_subjects_the_way_the_sdk_does(
    pattern: str, subject: str, expected: bool
) -> None:
    """The guard must use the SDK's matcher, not an approximation of it.

    `BoundEventBus` authorises a subscription with `fnmatchcase`, where `*`
    spans dots -- so `communication.*` really does cover
    `communication.turn.received`. The earlier version of the guard
    open-coded `topic in SUBSCRIBABLE_SUBJECTS or f"{first}.*" in ...`,
    which happened to agree with `fnmatch` for 4A's single-segment patterns
    and reported a false negative the moment 4B declared a narrower one
    (`reasoning.process.*`). Widening `events/subscribed.py` to
    `reasoning.*` would have silenced that at the cost of subscribing to
    every reasoning subject rather than the finalized ones doc 09 §6 allows.
    """
    assert fnmatchcase(subject, pattern) is expected


def test_every_public_topic_is_reachable_on_the_bus() -> None:
    """The two allow-lists must agree, or a client could name a dead topic."""
    for topic in PUBLIC_TOPICS:
        assert any(
            fnmatchcase(topic, pattern) for pattern in SUBSCRIBABLE_SUBJECTS
        ), f"{topic!r} is public but not declared in events/subscribed.py"


def _declared_publishable_subjects() -> set[str]:
    """Every subject any engine's own `events/published.py` declares.

    Read from source rather than imported: `lint-imports` forbids this
    service from importing another service's package (ADR-004), and the
    files are a flat `frozenset` of string literals, so a literal scan is
    exact -- no engine builds this set dynamically.
    """
    repo_root = Path(__file__).resolve().parents[4]
    subjects: set[str] = set()
    published_files = list(repo_root.glob("services/*/src/*/events/published.py"))
    published_files += list(repo_root.glob("agent-os/*/src/*/events/published.py"))
    assert published_files, "found no events/published.py files; the glob is wrong"
    for path in published_files:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                subjects.add(node.value)
    return subjects


def test_every_public_topic_is_actually_published() -> None:
    """A browser must never be offered a topic nothing emits.

    The prefix check above is necessary but not sufficient, and the gap was
    not hypothetical: it passed against `communication.intent.delivered`,
    `perception.identity.present` and `personality.style.selected` while all
    three matched a subscribable *pattern* and none was published by any
    engine. Subscribing to one of those succeeded and then delivered nothing,
    forever -- the Conversation panel would have rendered the user's own
    turns and never a reply.
    """
    publishable = _declared_publishable_subjects()
    dead = sorted(topic for topic in PUBLIC_TOPICS if topic not in publishable)
    assert not dead, (
        f"public topics that no engine publishes: {dead}. Either some engine "
        "must declare the subject in its events/published.py and emit it, or "
        "the topic must come out of PUBLIC_TOPICS -- a browser subscribing to "
        "it would wait forever."
    )


def test_the_publication_scan_finds_a_known_subject() -> None:
    """Anti-decoration control for the scan above.

    A `_declared_publishable_subjects` that silently returned everything (or
    globbed nothing and was rescued by the `assert`) would make the test
    above vacuous. Pin it to one subject that is definitely published and one
    string that is definitely not a subject.
    """
    publishable = _declared_publishable_subjects()
    assert "communication.turn.received" in publishable
    assert "communication.definitely.not.a.real.subject" not in publishable


@pytest.mark.parametrize(
    "topic",
    [
        ">",  # NATS wildcard for everything
        "*",
        "communication.*",  # patterns are not names
        "communication.>",
        "agent_os.internal.rpc",
        "internal.anything",
        "",
        "nova.heartbeat.extra",
    ],
)
def test_wildcards_and_internal_subjects_are_not_public(topic: str) -> None:
    """A browser must not be able to express 'subscribe to everything'."""
    allowed, rejected = partition_topics([topic])
    assert allowed == []
    assert rejected == [topic]


def test_partition_splits_mixed_requests() -> None:
    allowed, rejected = partition_topics(
        ["nova.heartbeat", "secret.topic", "communication.turn.received"]
    )
    assert allowed == ["nova.heartbeat", "communication.turn.received"]
    assert rejected == ["secret.topic"]


# --- client message parsing ----------------------------------------------


def test_valid_client_message_parses() -> None:
    message = parse_client_message('{"action":"subscribe","topics":["nova.heartbeat"]}')
    assert message.action == "subscribe"
    assert message.topics == ["nova.heartbeat"]


@pytest.mark.parametrize(
    "raw",
    [
        "not json at all",
        "{}",
        '{"action":"subscribe"}',  # no topics
        '{"action":"subscribe","topics":[]}',  # empty
        '{"action":"drop_database","topics":["x"]}',  # unknown action
        '{"action":"subscribe","topics":"nova.heartbeat"}',  # not a list
        "[]",
    ],
)
def test_malformed_messages_are_rejected(raw: str) -> None:
    with pytest.raises(MalformedClientMessage):
        parse_client_message(raw)


# --- envelope projection --------------------------------------------------


def test_frame_preserves_correlation_id_and_timestamp_from_the_source() -> None:
    """Regenerating either would break the trace back through the chain."""
    correlation = uuid4()
    occurred = datetime(2026, 9, 1, 8, 30, tzinfo=UTC)
    frame = to_event_frame(_envelope(correlation_id=correlation, occurred_at=occurred))
    assert frame.meta.correlation_id == str(correlation)
    assert frame.meta.generated_at == occurred


def test_confidence_is_copied_only_when_present() -> None:
    assert to_event_frame(_envelope(confidence=None)).meta.confidence is None
    assert to_event_frame(_envelope(confidence=0.42)).meta.confidence == 0.42


def test_frame_carries_the_payload_and_topic() -> None:
    frame = to_event_frame(_envelope(payload={"a": 1}))
    assert frame.data == {"a": 1}
    assert frame.topic == "communication.turn.received"
    assert frame.error is None


def test_bus_internals_are_absent_from_the_public_frame() -> None:
    """`causation_id` and `source_engine` are internal; they must not ship."""
    serialised = to_event_frame(_envelope()).model_dump()
    assert "causation_id" not in serialised
    assert "source_engine" not in serialised
    assert "event_id" not in serialised
    assert set(serialised["meta"]) == {"correlation_id", "generated_at", "confidence"}


def test_frame_envelope_matches_the_rest_surface_convention() -> None:
    """Doc 11 §4's shape, so the client's data layer sees one convention."""
    serialised = to_event_frame(_envelope()).model_dump()
    assert {"data", "meta", "error"} <= set(serialised)
