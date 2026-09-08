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


#: Internal request/reply subjects. A browser must never be able to name one,
#: nor may this gateway subscribe to one: an RPC request carries a caller's
#: arguments and an RPC reply is addressed to exactly one caller, so neither is
#: "an already-finalized event plus read-only telemetry" (doc 09 §6).
#:
#: Read from the components' own `events/` declarations rather than typed out,
#: so a subject added there is covered here without anyone remembering to.
_RPC_SUFFIXES = (".request", ".reply")


def _declared_rpc_subjects() -> set[str]:
    """Every `*.request`/`*.reply` subject any component declares."""
    repo_root = Path(__file__).resolve().parents[4]
    paths = list(repo_root.glob("services/*/src/*/events/*.py"))
    paths += list(repo_root.glob("agent-os/*/src/*/events/*.py"))
    assert paths, "found no events/ modules; the glob is wrong"
    subjects: set[str] = set()
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value.endswith(_RPC_SUFFIXES)
            ):
                subjects.add(node.value)
    return subjects


def test_no_internal_rpc_subject_is_publicly_nameable() -> None:
    """A browser may not name an RPC subject, ever.

    `domain/protocol.py`'s own docstring states this as the reason
    `PUBLIC_TOPICS` is an allow-list rather than a pattern language. This
    asserts it against every RPC subject the repository actually declares --
    including `agent_os.registry.list_packages.request`, added in Phase 4C
    milestone 4C.2a, whose whole design depends on staying internal.
    """
    rpc_subjects = _declared_rpc_subjects()
    assert rpc_subjects, "no RPC subjects found; the parser broke, do not delete it"
    leaked = sorted(rpc_subjects & set(PUBLIC_TOPICS))
    assert not leaked, (
        f"internal RPC subjects exposed to browsers: {leaked}. An RPC request "
        "carries a caller's arguments and an RPC reply is addressed to one "
        "caller; neither may cross to a client."
    )


#: RPC subjects a *currently declared* subscribable pattern already matches.
#:
#: **These are a disclosed, pre-existing defect, not an approved exception.**
#: Found 2026-09-08 by the test below, which was written for Phase 4C 4C.2a.
#: 4A's `communication.*` and `personality.*` are broad enough to match these
#: six request subjects, so this gateway's *bus-side* allow-list is wider than
#: doc 09 §6's "already-finalized events plus read-only telemetry".
#:
#: No browser can reach them: `PUBLIC_TOPICS` is an exact-string allow-list and
#: names none of them, and `test_no_internal_rpc_subject_is_publicly_nameable`
#: below asserts that. The exposure is that the gateway *process* may receive
#: internal RPC traffic, not that a client may see it.
#:
#: Narrowing the two patterns is a `ws-gateway` behaviour change, out of scope
#: for 4C.2a (which is forbidden from touching WebSocket behaviour) and needing
#: its own verification of which finalized `communication.*`/`personality.*`
#: subjects the 4A/4B panels actually consume. Pinned here rather than fixed or
#: ignored, per protocol §13.1: the list may shrink, and must never grow.
_KNOWN_OVERBROAD_RPC_MATCHES = frozenset(
    {
        "communication.intent.deliver.request",
        "communication.session.close.request",
        "communication.session.create.request",
        "communication.session.lookup_by_user.request",
        "personality.style.select.request",
        "personality.validate_response.request",
    }
)


def test_no_subscribable_pattern_matches_an_internal_rpc_subject() -> None:
    """The subtler half, and the one a widened pattern would break silently.

    `BoundEventBus` matches with `fnmatchcase`, where `*` spans dots -- so
    `agent_os.*` would match `agent_os.registry.list_packages.request` and
    subscribe this gateway to every RPC in that family. `PUBLIC_TOPICS` would
    still stop a browser naming it, but the gateway process would be
    receiving internal RPC traffic it has no business seeing, and the next
    person to add a topic would find it already arriving.

    This is exactly why Phase 4C's planned realtime exposure is
    `agent_os.task.*` and not `agent_os.*`.

    Six pre-existing matches are pinned above rather than asserted away; this
    test fails on a seventh.
    """
    offenders: dict[str, list[str]] = {}
    for subject in sorted(_declared_rpc_subjects()):
        matching = [p for p in SUBSCRIBABLE_SUBJECTS if fnmatchcase(subject, p)]
        if matching and subject not in _KNOWN_OVERBROAD_RPC_MATCHES:
            offenders[subject] = matching
    assert not offenders, (
        f"internal RPC subjects matched by a subscribable pattern: {offenders}. "
        "Narrow the pattern; do not add it to _KNOWN_OVERBROAD_RPC_MATCHES."
    )


def test_no_agent_os_rpc_subject_is_subscribable() -> None:
    """4C.2a's own guarantee, stated separately so it cannot be weakened by
    editing the pinned list above.

    Every `agent_os.*` RPC subject -- the two Registry ones, the two
    Supervisor ones, and any added later -- must match no subscribable
    pattern at all. There are no grandfathered exceptions here, and there
    must never be.
    """
    agent_os_rpc = sorted(s for s in _declared_rpc_subjects() if s.startswith("agent_os."))
    assert agent_os_rpc, "no agent_os RPC subjects found; the parser broke"
    for subject in agent_os_rpc:
        matching = [p for p in SUBSCRIBABLE_SUBJECTS if fnmatchcase(subject, p)]
        assert not matching, (
            f"{subject!r} is an internal agent-os RPC subject but matches "
            f"subscribable pattern(s) {matching}."
        )


def test_the_pinned_overbroad_list_is_not_stale() -> None:
    """A pinned defect that has been fixed must be unpinned.

    Without this, the list above would quietly outlive the problem and start
    granting exceptions nothing needs.
    """
    still_matching = {
        subject
        for subject in _KNOWN_OVERBROAD_RPC_MATCHES
        if any(fnmatchcase(subject, pattern) for pattern in SUBSCRIBABLE_SUBJECTS)
    }
    resolved = sorted(_KNOWN_OVERBROAD_RPC_MATCHES - still_matching)
    assert not resolved, (
        f"these no longer match any subscribable pattern: {resolved}. "
        "Remove them from _KNOWN_OVERBROAD_RPC_MATCHES."
    )


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
