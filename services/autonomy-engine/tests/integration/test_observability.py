"""SAD 15 §9.1 items 9 and 10 for `autonomy-engine`.

Two kinds of event must leave a trace an operator can find:

* **every change to the engine's own authority** -- the level, a policy, the
  permission matrix -- one `autonomy configuration changed` line with the
  values **before and after**, and one count. These are the changes that can
  let an action execute without approval, so "it was re-enabled" must be
  visible, not inferred;
* **every decision**, from the suggestion inbox and from the initiative
  trigger -- counted by bounded outcome, timed, and (for the trigger) logged
  with its `correlation_id`.

The app is the real one with the default tier's fakes (`tests/conftest.py`);
metrics are read from the process-global registry `/internal/metrics`
serves, and every assertion is a delta.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from nova_autonomy_engine.config import Settings
from nova_autonomy_engine.decision_orchestration import (
    DECISION_TRIGGER_SUBJECT,
    handle_decision_request,
)
from nova_autonomy_engine.domain.models import (
    AutonomyLevel,
    PermissionCategory,
    PermissionGrant,
)
from nova_autonomy_engine.observability import DECISION_OUTCOMES, create_metrics
from nova_contracts import EventEnvelope
from nova_contracts.events.planning import RiskLevel
from prometheus_client import REGISTRY, generate_latest

from tests.fakes.repository import FakeAutonomyRepository
from tests.fakes.trust_source import SpyTrustSource
from tests.integration.test_autonomy_api import _seed_suggestion

_SAMPLE = re.compile(r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(\{(?P<labels>[^}]*)\})? (?P<value>\S+)$")


def _sample(name: str, **labels: str) -> float:
    total = 0.0
    for line in generate_latest(REGISTRY).decode().splitlines():
        match = _SAMPLE.match(line)
        if match is None or match["name"] != name:
            continue
        found = dict(re.findall(r'(\w+)="([^"]*)"', match["labels"] or ""))
        if all(found.get(k) == v for k, v in labels.items()):
            total += float(match["value"])
    return total


class _Records(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def records() -> Iterator[list[logging.LogRecord]]:
    """On the engine's own logger: `configure_logging` replaces the root
    handlers on first use, which would detach pytest's `caplog`."""
    handler = _Records()
    engine_logger = logging.getLogger("autonomy-engine")
    engine_logger.addHandler(handler)
    previous = engine_logger.level
    engine_logger.setLevel(logging.DEBUG)
    try:
        yield handler.records
    finally:
        engine_logger.removeHandler(handler)
        engine_logger.setLevel(previous)


def _changes(records: list[logging.LogRecord], kind: str) -> list[logging.LogRecord]:
    return [
        r
        for r in records
        if r.getMessage() == "autonomy configuration changed"
        and getattr(r, "kind", None) == kind
    ]


# --- configuration changes ---------------------------------------------------


def test_a_level_change_is_logged_with_before_and_after_and_counted(
    client: TestClient, records: list[logging.LogRecord]
) -> None:
    before = _sample("autonomy_configuration_changes_total", kind="level", operation="set")
    assert client.put("/v1/autonomy/level", json={"level": 1}).status_code == 200
    assert client.put("/v1/autonomy/level", json={"level": 2}).status_code == 200

    first, second = _changes(records, "level")
    assert (first.level_before, first.level_after) == (None, 1)  # type: ignore[attr-defined]
    assert (second.level_before, second.level_after) == (1, 2)  # type: ignore[attr-defined]
    after = _sample("autonomy_configuration_changes_total", kind="level", operation="set")
    assert after - before == 2


def test_a_refused_level_is_neither_logged_as_a_change_nor_counted(
    client: TestClient, records: list[logging.LogRecord]
) -> None:
    before = _sample("autonomy_configuration_changes_total", kind="level")
    assert client.put("/v1/autonomy/level", json={"level": 3}).status_code == 422
    assert _changes(records, "level") == []
    assert _sample("autonomy_configuration_changes_total", kind="level") == before


def test_re_enabling_an_auto_execute_policy_is_visible_in_the_log(
    client: TestClient, records: list[logging.LogRecord]
) -> None:
    """The panel can re-enable a disabled `AUTO_EXECUTE` policy (ledger L-17
    covers only authoring). The log must show that the effect is
    `auto_execute` and that `enabled` went from false to true."""
    created = client.post(
        "/v1/autonomy/policies",
        json={
            "name": "tidy scratch files",
            "effect": "auto_execute",
            "match_category": "modify",
            "enabled": False,
        },
    )
    assert created.status_code == 201
    policy_id = created.json()["id"]
    enabled = client.patch(f"/v1/autonomy/policies/{policy_id}", json={"enabled": True})
    assert enabled.status_code == 200

    create, update = _changes(records, "policy")
    assert create.operation == "create"  # type: ignore[attr-defined]
    assert create.policy_before is None  # type: ignore[attr-defined]
    assert create.policy_after["effect"] == "auto_execute"  # type: ignore[attr-defined]
    assert update.operation == "update"  # type: ignore[attr-defined]
    assert update.policy_id == policy_id  # type: ignore[attr-defined]
    assert update.policy_before["enabled"] is False  # type: ignore[attr-defined]
    assert update.policy_after["enabled"] is True  # type: ignore[attr-defined]
    assert update.policy_after["effect"] == "auto_execute"  # type: ignore[attr-defined]


def test_deleting_a_deny_policy_logs_what_was_removed(
    client: TestClient, records: list[logging.LogRecord]
) -> None:
    before = _sample("autonomy_configuration_changes_total", kind="policy", operation="delete")
    created = client.post(
        "/v1/autonomy/policies",
        json={"name": "never delete", "effect": "deny", "match_category": "delete"},
    )
    policy_id = created.json()["id"]
    assert client.delete(f"/v1/autonomy/policies/{policy_id}").status_code == 204
    assert client.delete(f"/v1/autonomy/policies/{policy_id}").status_code == 404

    deletions = [r for r in _changes(records, "policy") if r.operation == "delete"]  # type: ignore[attr-defined]
    assert len(deletions) == 1, "a 404 delete is not a change"
    assert deletions[0].policy_before["effect"] == "deny"  # type: ignore[attr-defined]
    assert deletions[0].policy_after is None  # type: ignore[attr-defined]
    after = _sample("autonomy_configuration_changes_total", kind="policy", operation="delete")
    assert after - before == 1


def test_a_permission_change_logs_each_named_category_before_and_after(
    client: TestClient, records: list[logging.LogRecord]
) -> None:
    grant = {
        "category": "read",
        "max_risk": "moderate",
        "requires_approval_above": None,
        "granted": True,
    }
    assert client.put("/v1/autonomy/permissions", json={"grants": [grant]}).status_code == 200
    widened = {**grant, "max_risk": "high"}
    assert client.put("/v1/autonomy/permissions", json={"grants": [widened]}).status_code == 200

    first, second = _changes(records, "permissions")
    assert first.changes == {  # type: ignore[attr-defined]
        "read": {"before": None, "after": {"max_risk": "moderate", "requires_approval_above": None}}
    }
    assert second.changes["read"]["before"]["max_risk"] == "moderate"  # type: ignore[attr-defined]
    assert second.changes["read"]["after"]["max_risk"] == "high"  # type: ignore[attr-defined]
    assert set(second.changes) == {"read"}  # type: ignore[attr-defined]


def _refusals(records: list[logging.LogRecord], kind: str) -> list[logging.LogRecord]:
    return [
        r
        for r in records
        if r.getMessage() == "autonomy configuration change refused"
        and getattr(r, "kind", None) == kind
    ]


def test_a_change_names_its_request_its_target_and_that_no_actor_is_known(
    client: TestClient, records: list[logging.LogRecord]
) -> None:
    response = client.put(
        "/v1/autonomy/level", json={"level": 1}, headers={"x-correlation-id": "corr-level-1"}
    )
    assert response.status_code == 200

    (change,) = _changes(records, "level")
    assert change.outcome == "applied"  # type: ignore[attr-defined]
    assert change.correlation_id == "corr-level-1"  # type: ignore[attr-defined]
    assert change.user_id == str(client.app.state.settings.primary_user_id)  # type: ignore[attr-defined]
    assert change.actor is None  # type: ignore[attr-defined]


def test_a_change_without_a_correlation_header_says_so(
    client: TestClient, records: list[logging.LogRecord]
) -> None:
    assert client.put("/v1/autonomy/level", json={"level": 1}).status_code == 200
    (change,) = _changes(records, "level")
    assert change.correlation_id is None  # type: ignore[attr-defined]


def test_a_level_the_engine_refuses_is_logged_as_refused(
    client: TestClient, records: list[logging.LogRecord]
) -> None:
    response = client.put(
        "/v1/autonomy/level", json={"level": 3}, headers={"x-correlation-id": "corr-level-3"}
    )
    assert response.status_code == 422

    (refusal,) = _refusals(records, "level")
    assert refusal.levelno == logging.WARNING
    assert (refusal.operation, refusal.outcome, refusal.status_code) == ("set", "refused", 422)  # type: ignore[attr-defined]
    assert refusal.correlation_id == "corr-level-3"  # type: ignore[attr-defined]
    assert refusal.actor is None  # type: ignore[attr-defined]
    assert _changes(records, "level") == []


def test_a_body_rejected_by_validation_is_logged_as_refused_without_its_values(
    client: TestClient, records: list[logging.LogRecord]
) -> None:
    """Request validation answers before the handler runs, so this is the
    path the handler alone could never log."""
    response = client.post(
        "/v1/autonomy/policies",
        json={"name": "x", "effect": "do_whatever_it_likes", "match_category": "modify"},
    )
    assert response.status_code == 422

    (refusal,) = _refusals(records, "policy")
    assert (refusal.operation, refusal.status_code) == ("create", 422)  # type: ignore[attr-defined]
    assert ["body", "effect"] in [entry["loc"] for entry in refusal.reason]  # type: ignore[attr-defined]
    assert "do_whatever_it_likes" not in repr(refusal.reason)  # type: ignore[attr-defined]


def test_writes_to_an_unknown_policy_are_logged_as_refused(
    client: TestClient, records: list[logging.LogRecord]
) -> None:
    missing = uuid4()
    assert (
        client.patch(f"/v1/autonomy/policies/{missing}", json={"enabled": True}).status_code == 404
    )
    assert client.delete(f"/v1/autonomy/policies/{missing}").status_code == 404

    refusals = _refusals(records, "policy")
    assert [(r.operation, r.status_code) for r in refusals] == [("update", 404), ("delete", 404)]  # type: ignore[attr-defined]


def test_a_refused_read_is_not_logged_as_a_refused_configuration_change(
    client: TestClient, records: list[logging.LogRecord]
) -> None:
    assert client.get("/v1/autonomy/suggestions", params={"cursor": "not-ours"}).status_code == 422
    assert [r for r in records if r.getMessage() == "autonomy configuration change refused"] == []


# --- suggestion inbox --------------------------------------------------------


async def test_a_suggestion_decision_is_logged_and_counted_and_a_refusal_is_logged(
    client: TestClient,
    repository: FakeAutonomyRepository,
    settings: Settings,
    records: list[logging.LogRecord],
) -> None:
    suggestion = await _seed_suggestion(repository, settings)
    await repository.upsert_permission_grants(
        settings.primary_user_id,
        [
            PermissionGrant(
                user_id=settings.primary_user_id,
                category=PermissionCategory.MODIFY,
                max_risk=RiskLevel.CRITICAL,
            )
        ],
    )
    before = _sample("autonomy_decisions_total", source="suggestion_inbox", outcome="propose")
    url = f"/v1/autonomy/suggestions/{suggestion.id}/decide"

    assert client.post(url, json={"decision": "approve"}).status_code == 200
    assert client.post(url, json={"decision": "approve"}).status_code == 409
    assert (
        client.post(f"/v1/autonomy/suggestions/{uuid4()}/decide", json={"decision": "reject"})
        .status_code
        == 404
    )

    results = [
        r.result  # type: ignore[attr-defined]
        for r in records
        if r.getMessage() == "suggestion decision"
    ]
    assert results == ["approved", "refused_already_decided", "not_found"]
    after = _sample("autonomy_decisions_total", source="suggestion_inbox", outcome="propose")
    assert after - before == 1, "only the decision that was made is counted"


# --- initiative trigger ------------------------------------------------------

PRIMARY = UUID("00000000-0000-0000-0000-0000000004f6")


def _trigger(payload: dict | None = None) -> EventEnvelope:
    return EventEnvelope(
        subject=DECISION_TRIGGER_SUBJECT,
        source_engine="cognitive-state-engine",
        correlation_id=uuid4(),
        payload=payload
        if payload is not None
        else {
            "thought_id": str(uuid4()),
            "category": "create",
            "risk": "low",
            "action_type": "filesystem",
            "execution_target": "filesystem",
            "verification_method": "none",
            "title": "rotate the scratch directory",
            "detail": "keep the last seven",
            "priority": 3,
            "requesting_engine": "cognitive-state-engine",
            "correlation_id": str(uuid4()),
            "operation": "list",
            "parameters": {},
        },
    )


async def test_a_triggered_decision_is_counted_timed_and_logged_with_its_correlation_id(
    records: list[logging.LogRecord],
) -> None:
    repository = FakeAutonomyRepository()
    await repository.set_level(PRIMARY, AutonomyLevel.SUGGESTIVE)
    await repository.upsert_permission_grants(
        PRIMARY,
        [
            PermissionGrant(
                user_id=PRIMARY, category=PermissionCategory.CREATE, max_risk=RiskLevel.LOW
            )
        ],
    )
    metrics = create_metrics()
    envelope = _trigger()
    counted = _sample("autonomy_decisions_total", source="trigger", outcome="propose")
    timed = _sample("autonomy_decision_duration_seconds_count", outcome="propose")

    reply = await handle_decision_request(
        envelope,
        repository=repository,
        trust_source=SpyTrustSource(),
        dispatcher=None,
        user_id=PRIMARY,
        metrics=metrics,
    )

    assert reply.outcome == "propose"
    assert _sample("autonomy_decisions_total", source="trigger", outcome="propose") - counted == 1
    assert _sample("autonomy_decision_duration_seconds_count", outcome="propose") - timed == 1
    [record] = [r for r in records if r.getMessage() == "autonomy decision recorded"]
    assert record.correlation_id == str(envelope.correlation_id)  # type: ignore[attr-defined]
    assert record.event_id == str(envelope.event_id)  # type: ignore[attr-defined]
    assert record.subject_id == str(reply.subject_id)  # type: ignore[attr-defined]


async def test_a_rejected_trigger_is_counted_as_rejected_and_not_logged_as_recorded(
    records: list[logging.LogRecord],
) -> None:
    before = _sample("autonomy_decisions_total", source="trigger", outcome="rejected")
    reply = await handle_decision_request(
        _trigger({"not": "a decision request"}),
        repository=FakeAutonomyRepository(),
        trust_source=SpyTrustSource(),
        dispatcher=None,
        user_id=PRIMARY,
        metrics=create_metrics(),
    )
    assert reply.rejected is True
    assert _sample("autonomy_decisions_total", source="trigger", outcome="rejected") - before == 1
    assert [r for r in records if r.getMessage() == "autonomy decision recorded"] == []


def test_every_outcome_label_emitted_is_from_the_bounded_set(client: TestClient) -> None:
    for line in generate_latest(REGISTRY).decode().splitlines():
        if line.startswith("autonomy_decisions_total{"):
            outcome = re.search(r'outcome="([^"]*)"', line)
            assert outcome is not None and outcome.group(1) in DECISION_OUTCOMES
