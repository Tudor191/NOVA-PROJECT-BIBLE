"""SAD 15 §9.1 item 9 for CF-9's write surface: every change to the
identity-confidence policy is logged with the map **before and after**, and a
change that lowers any tier's threshold -- a weaker authorization gate -- is
logged at `WARNING`.

Not an audit trail (D-4F4-3 stands; L-15 stays open): these assert a log line,
nothing persisted. `configure_logging` replaces the root handlers the first
time it runs, so the records are read from a handler on the module's own
logger, as `autonomy-engine`'s observability tests do.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from nova_action_engine.config import Settings
from nova_action_engine.main import create_app

from tests.fakes.capability_port import FakeCapabilityPort
from tests.fakes.communication_port import FakeCommunicationPort
from tests.fakes.identity_port import FakeIdentityPort
from tests.fakes.repository import FakeActionRepository

ROUTE = "/v1/action/identity-confidence-policy"
MESSAGE = "identity-confidence policy changed"


class _Records(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, _Records]]:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(
        Settings(primary_user_id=uuid4()),
        repository=FakeActionRepository(),
        capability_port=FakeCapabilityPort(),
        communication_port=FakeCommunicationPort(),
        identity_port=FakeIdentityPort(),
    )
    records = _Records()
    target = logging.getLogger("action-engine.identity-confidence-policy")
    target.addHandler(records)
    try:
        with TestClient(app) as client:
            yield client, records
    finally:
        target.removeHandler(records)


def _changes(records: _Records) -> list[logging.LogRecord]:
    return [r for r in records.records if r.getMessage() == MESSAGE]


def test_creating_a_policy_is_a_warning_because_every_written_tier_was_fail_closed(
    harness: tuple[TestClient, _Records],
) -> None:
    client, records = harness
    assert client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.6}}).status_code == 200

    [change] = _changes(records)
    assert change.levelno == logging.WARNING
    assert change.operation == "create"  # type: ignore[attr-defined]
    assert change.before is None  # type: ignore[attr-defined]
    assert change.after == {"low": 0.6}  # type: ignore[attr-defined]
    assert change.loosened_tiers == ["low"]  # type: ignore[attr-defined]


def test_lowering_a_threshold_is_a_warning_and_names_the_tier(
    harness: tuple[TestClient, _Records],
) -> None:
    client, records = harness
    client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.7, "moderate": 0.7}})
    client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.4, "moderate": 0.7}})

    change = _changes(records)[-1]
    assert change.levelno == logging.WARNING
    assert change.operation == "replace"  # type: ignore[attr-defined]
    assert change.before == {"low": 0.7, "moderate": 0.7}  # type: ignore[attr-defined]
    assert change.after == {"low": 0.4, "moderate": 0.7}  # type: ignore[attr-defined]
    assert change.loosened_tiers == ["low"]  # type: ignore[attr-defined]


def test_tightening_or_removing_a_tier_is_info(harness: tuple[TestClient, _Records]) -> None:
    """Removing a tier returns it to the fail-closed 1.0 -- stricter, not weaker."""
    client, records = harness
    client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.4, "moderate": 0.5}})
    client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.6}})

    change = _changes(records)[-1]
    assert change.levelno == logging.INFO
    assert change.loosened_tiers == []  # type: ignore[attr-defined]


def test_deleting_the_policy_is_logged_with_what_it_removed(
    harness: tuple[TestClient, _Records],
) -> None:
    client, records = harness
    client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.6}})
    assert client.delete(ROUTE).status_code == 204

    change = _changes(records)[-1]
    assert change.levelno == logging.INFO
    assert change.operation == "delete"  # type: ignore[attr-defined]
    assert change.before == {"low": 0.6}  # type: ignore[attr-defined]
    assert change.after is None  # type: ignore[attr-defined]


def test_a_refused_write_or_a_delete_of_nothing_logs_no_change(
    harness: tuple[TestClient, _Records],
) -> None:
    client, records = harness
    assert client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.9}}).status_code == 422
    assert client.delete(ROUTE).status_code == 404
    assert _changes(records) == []


def _refusals(records: _Records) -> list[logging.LogRecord]:
    return [
        r for r in records.records if r.getMessage() == "identity-confidence policy change refused"
    ]


def test_a_change_names_its_request_its_target_and_that_no_actor_is_known(
    harness: tuple[TestClient, _Records],
) -> None:
    client, records = harness
    response = client.put(
        ROUTE,
        json={"minimum_confidence_by_risk": {"low": 0.6}},
        headers={"x-correlation-id": "corr-policy-1"},
    )
    assert response.status_code == 200

    [change] = _changes(records)
    assert change.outcome == "applied"  # type: ignore[attr-defined]
    assert change.correlation_id == "corr-policy-1"  # type: ignore[attr-defined]
    assert change.user_id == response.json()["user_id"]  # type: ignore[attr-defined]
    assert change.actor is None  # type: ignore[attr-defined]


def test_a_threshold_above_the_ceiling_is_logged_as_refused_without_its_value(
    harness: tuple[TestClient, _Records],
) -> None:
    """The 0.75 ceiling is request validation: the 422 is answered before the
    handler runs, so this is the path the handler alone could never log."""
    client, records = harness
    response = client.put(
        ROUTE,
        json={"minimum_confidence_by_risk": {"low": 0.9}},
        headers={"x-correlation-id": "corr-policy-2"},
    )
    assert response.status_code == 422

    [refusal] = _refusals(records)
    assert refusal.levelno == logging.WARNING
    assert (refusal.operation, refusal.outcome, refusal.status_code) == ("put", "refused", 422)  # type: ignore[attr-defined]
    assert refusal.correlation_id == "corr-policy-2"  # type: ignore[attr-defined]
    assert refusal.actor is None  # type: ignore[attr-defined]
    assert ["body", "minimum_confidence_by_risk"] in [e["loc"] for e in refusal.reason]  # type: ignore[attr-defined]
    assert "0.9" not in repr(refusal.reason)  # type: ignore[attr-defined]


def test_a_delete_of_nothing_is_logged_as_refused(harness: tuple[TestClient, _Records]) -> None:
    client, records = harness
    assert client.delete(ROUTE).status_code == 404

    [refusal] = _refusals(records)
    assert (refusal.operation, refusal.status_code) == ("delete", 404)  # type: ignore[attr-defined]


def test_reading_an_absent_policy_is_not_logged_as_a_refused_change(
    harness: tuple[TestClient, _Records],
) -> None:
    client, records = harness
    assert client.get(ROUTE).status_code == 404
    assert _refusals(records) == []


def test_a_refusal_never_logs_a_tier_name_the_caller_chose(
    harness: tuple[TestClient, _Records],
) -> None:
    client, records = harness
    body = {"minimum_confidence_by_risk": {"sk-live-CALLER": "not-a-number"}}
    assert client.put(ROUTE, json=body).status_code == 422

    [refusal] = _refusals(records)
    assert refusal.reason == [  # type: ignore[attr-defined]
        {"loc": ["body", "minimum_confidence_by_risk", "<unrecognized>"], "type": "float_parsing"}
    ]
    assert "sk-live-CALLER" not in repr(refusal.__dict__)



def test_a_refusal_lists_at_most_ten_validation_errors(
    harness: tuple[TestClient, _Records],
) -> None:
    client, records = harness
    body = {"minimum_confidence_by_risk": {f"tier-{n}": "x" for n in range(40)}}
    assert client.put(ROUTE, json=body).status_code == 422

    [refusal] = _refusals(records)
    assert len(refusal.reason) == 11  # type: ignore[attr-defined]
    assert refusal.reason[-1] == {"more": 30}  # type: ignore[attr-defined]


def test_a_refusal_is_named_by_its_status_not_its_message(
    harness: tuple[TestClient, _Records],
) -> None:
    client, records = harness
    assert client.delete(ROUTE).status_code == 404
    [refusal] = _refusals(records)
    assert refusal.reason == "not_found"  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "header",
    [
        "A" * 129,
        "corr\r\nlevel=CRITICAL actor=admin",
        'corr", "actor": "admin',
        "corr\u2028actor=admin",
        "\x1b[31mcorr",
        "-starts-with-a-dash",
        "",
    ],
)
def test_a_correlation_id_that_is_not_a_short_token_is_never_logged(
    header: str, harness: tuple[TestClient, _Records]
) -> None:
    client, records = harness
    # Sent as bytes, as a raw HTTP caller would; the server reads them as latin-1.
    raw = header.encode("utf-8")
    response = client.put(
        ROUTE,
        json={"minimum_confidence_by_risk": {"low": 0.6}},
        headers={"x-correlation-id": raw},
    )
    assert response.status_code == 200
    [change] = _changes(records)
    assert change.correlation_id == "<invalid>"  # type: ignore[attr-defined]
    if header:
        received = raw.decode("latin-1")
        assert not any(received in str(value) for value in change.__dict__.values())


@pytest.mark.parametrize(
    "header", ["0d1e2f30-0000-4000-8000-000000000001", "corr-policy-1", "a" * 128]
)
def test_a_short_token_correlation_id_is_logged_as_sent(
    header: str, harness: tuple[TestClient, _Records]
) -> None:
    client, records = harness
    response = client.put(
        ROUTE,
        json={"minimum_confidence_by_risk": {"low": 0.6}},
        headers={"x-correlation-id": header},
    )
    assert response.status_code == 200
    [change] = _changes(records)
    assert change.correlation_id == header  # type: ignore[attr-defined]
