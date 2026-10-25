"""SAD 15 §9.1 item 10 for `cognitive-state-engine`: each subscription's
outcomes are **counted under the same name their log line already uses**,
ingestion is **timed**, and a fired initiative trigger is counted by the
reply status `DecisionTriggerClient` reported.

The handlers are driven directly with in-memory stores -- no broker, no
database -- and metrics are read from the process-global registry
`/internal/metrics` serves. Every assertion is a delta.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import PurePath
from typing import Any
from uuid import UUID, uuid4

from nova_cognitive_state_engine.domain.models import ActiveThought, AttentionLayer
from nova_cognitive_state_engine.domain.ports import ThoughtNotFoundError, TriggerDelivery
from nova_cognitive_state_engine.domain.sensor_state import SensorStateRecord
from nova_cognitive_state_engine.events.handlers import (
    SENSOR_HEALTH_SUBJECT,
    WORKSPACE_OBSERVED_SUBJECT,
    make_sensor_health_handler,
    make_workspace_observation_handler,
)
from nova_cognitive_state_engine.observability import (
    INGESTION_BUCKETS_SECONDS,
    OBSERVATION_OUTCOMES,
    SENSOR_REPORT_OUTCOMES,
    TRIGGER_STATUSES,
    create_metrics,
)
from nova_contracts import EventEnvelope
from nova_contracts.events.autonomy import AutonomyDecisionRequestedPayload
from nova_observability import configure_metrics
from prometheus_client import REGISTRY, generate_latest

# The unit tier never builds the app, so nothing else installs the global
# MeterProvider; without it `get_meter()` hands back a no-op meter and every
# count reads as zero. Safe to call more than once.
configure_metrics("cognitive-state-engine")

PRIMARY = UUID("00000000-0000-0000-0000-000000000001")
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


# --- fakes -------------------------------------------------------------------


class SensorStore:
    def __init__(self, *, changed: bool = True, broken: bool = False) -> None:
        self._changed = changed
        self._broken = broken

    async def apply_sensor_report(self, record: SensorStateRecord) -> bool:
        if self._broken:
            raise ConnectionError("store unavailable")
        return self._changed


class ThoughtStore:
    def __init__(self, *, insert_fails: bool = False, promotion_fails: bool = False) -> None:
        self.thoughts: dict[UUID, ActiveThought] = {}
        self._insert_fails = insert_fails
        self._promotion_fails = promotion_fails

    async def get_thought(self, thought_id: UUID) -> ActiveThought:
        if self._promotion_fails:
            raise ConnectionError("store unavailable")
        if thought_id not in self.thoughts:
            raise ThoughtNotFoundError(thought_id)
        return self.thoughts[thought_id]

    async def insert_thought_if_absent(self, thought: ActiveThought) -> ActiveThought | None:
        if self._insert_fails:
            raise ConnectionError("store unavailable")
        if thought.thought_id in self.thoughts:
            return None
        self.thoughts[thought.thought_id] = thought
        return thought

    async def compare_and_set_layer(
        self,
        thought_id: UUID,
        *,
        expected: AttentionLayer,
        target: AttentionLayer,
        updated_at: datetime,
    ) -> ActiveThought | None:
        current = self.thoughts.get(thought_id)
        if current is None or current.attention_layer is not expected:
            return None
        moved = current.model_copy(update={"attention_layer": target, "updated_at": updated_at})
        self.thoughts[thought_id] = moved
        return moved


class Trigger:
    def __init__(self, status: str = "decided") -> None:
        self._status = status

    async def request_decision(
        self, payload: AutonomyDecisionRequestedPayload, *, correlation_id: UUID
    ) -> TriggerDelivery:
        return TriggerDelivery(status=self._status, outcome="propose", subject_id=uuid4())  # type: ignore[arg-type]


def _sensor_envelope(**payload: Any) -> EventEnvelope:
    body = {"sensor_id": "companion-filesystem", "sensor_type": "filesystem", "status": "running"}
    body.update(payload)
    return EventEnvelope(
        subject=SENSOR_HEALTH_SUBJECT,
        source_engine="perception-engine",
        correlation_id=uuid4(),
        payload=body,
    )


def _observation(path: str | None = None, **overrides: object) -> EventEnvelope:
    path = path or f"/workspace/{uuid4()}/notes.md"
    body: dict[str, object] = {
        "object_id": "ws-" + hashlib.sha256(PurePath(path).as_posix().encode()).hexdigest(),
        "label": PurePath(path).name,
        "user_id": str(PRIMARY),
        "object_type": "project",
        "project_id": None,
        "sensor_id": "companion-filesystem",
        "observed_at": datetime.now(UTC).isoformat(),
        "schema_version": 1,
    }
    body.update(overrides)
    return EventEnvelope(
        subject=WORKSPACE_OBSERVED_SUBJECT,
        source_engine="perception-engine",
        correlation_id=uuid4(),
        payload=body,
    )


# --- sensor reports ----------------------------------------------------------


async def test_each_sensor_report_outcome_is_counted_under_its_log_name() -> None:
    metrics = create_metrics()
    name = "cognitive_state_sensor_reports_total"
    before = {o: _sample(name, outcome=o) for o in SENSOR_REPORT_OUTCOMES}

    await make_sensor_health_handler(SensorStore(), metrics=metrics)(_sensor_envelope())
    await make_sensor_health_handler(SensorStore(changed=False), metrics=metrics)(
        _sensor_envelope()
    )
    await make_sensor_health_handler(SensorStore(), metrics=metrics)(
        _sensor_envelope(status="melting")
    )
    await make_sensor_health_handler(SensorStore(), metrics=metrics)(
        _sensor_envelope(sensor_id=None)
    )
    await make_sensor_health_handler(SensorStore(broken=True), metrics=metrics)(_sensor_envelope())

    delta = {o: _sample(name, outcome=o) - before[o] for o in SENSOR_REPORT_OUTCOMES}
    assert delta == {
        "applied": 1,
        "ignored_duplicate_or_stale": 1,
        "rejected_unknown_status": 1,
        "rejected_invalid_payload": 1,
        "not_stored": 1,
    }


# --- workspace observations ---------------------------------------------------


async def test_an_ingested_observation_is_counted_timed_and_its_trigger_counted() -> None:
    metrics = create_metrics()
    created = _sample("cognitive_state_workspace_observations_total", outcome="created")
    timed = _sample("cognitive_state_ingestion_duration_seconds_count", outcome="created")
    decided = _sample("cognitive_state_initiative_triggers_total", status="decided")

    handle = make_workspace_observation_handler(
        ThoughtStore(), Trigger(), user_id=PRIMARY, metrics=metrics
    )
    await handle(_observation())

    assert _sample("cognitive_state_workspace_observations_total", outcome="created") - created == 1
    assert (
        _sample("cognitive_state_ingestion_duration_seconds_count", outcome="created") - timed == 1
    )
    assert _sample("cognitive_state_initiative_triggers_total", status="decided") - decided == 1


async def test_a_duplicate_a_foreign_user_and_an_invalid_payload_are_each_counted() -> None:
    metrics = create_metrics()
    name = "cognitive_state_workspace_observations_total"
    outcomes = ("duplicate", "foreign_user", "rejected_invalid_payload")
    before = {o: _sample(name, outcome=o) for o in outcomes}
    triggers = _sample("cognitive_state_initiative_triggers_total")

    store = ThoughtStore()
    handle = make_workspace_observation_handler(store, Trigger(), user_id=PRIMARY, metrics=metrics)
    path = f"/workspace/{uuid4()}/notes.md"
    await handle(_observation(path))
    await handle(_observation(path))  # the same file again: nothing is written
    await handle(_observation(user_id=str(uuid4())))
    await handle(_observation(object_type=None))

    for outcome in outcomes:
        assert _sample(name, outcome=outcome) - before[outcome] == 1, outcome
    # Only the first observation promoted a thought and fired a trigger.
    assert _sample("cognitive_state_initiative_triggers_total") - triggers == 1


async def test_a_failed_insert_and_a_lost_initiative_are_each_counted_and_timed() -> None:
    metrics = create_metrics()
    counted = "cognitive_state_workspace_observations_total"
    timed = "cognitive_state_ingestion_duration_seconds_count"
    outcomes = ("not_ingested", "initiative_lost")
    before = {o: (_sample(counted, outcome=o), _sample(timed, outcome=o)) for o in outcomes}

    for store in (ThoughtStore(insert_fails=True), ThoughtStore(promotion_fails=True)):
        handle = make_workspace_observation_handler(
            store, Trigger(), user_id=PRIMARY, metrics=metrics
        )
        await handle(_observation())

    for outcome in outcomes:
        assert _sample(counted, outcome=outcome) - before[outcome][0] == 1, outcome
        assert _sample(timed, outcome=outcome) - before[outcome][1] == 1, outcome


async def test_a_trigger_that_could_not_be_confirmed_is_counted_by_its_status() -> None:
    metrics = create_metrics()
    before = _sample("cognitive_state_initiative_triggers_total", status="unavailable")
    handle = make_workspace_observation_handler(
        ThoughtStore(), Trigger(status="unavailable"), user_id=PRIMARY, metrics=metrics
    )
    await handle(_observation())
    assert _sample("cognitive_state_initiative_triggers_total", status="unavailable") - before == 1


async def test_without_metrics_the_handlers_behave_exactly_as_before() -> None:
    """`metrics` is optional; omitting it must change nothing but the counts."""
    store = ThoughtStore()
    await make_workspace_observation_handler(store, Trigger(), user_id=PRIMARY)(_observation())
    await make_sensor_health_handler(SensorStore())(_sensor_envelope())
    assert len(store.thoughts) == 1


# --- bounded labels ----------------------------------------------------------


def test_every_emitted_label_is_from_its_closed_set() -> None:
    allowed = {
        "cognitive_state_sensor_reports_total": ("outcome", SENSOR_REPORT_OUTCOMES),
        "cognitive_state_workspace_observations_total": ("outcome", OBSERVATION_OUTCOMES),
        "cognitive_state_initiative_triggers_total": ("status", TRIGGER_STATUSES),
    }
    for line in generate_latest(REGISTRY).decode().splitlines():
        match = _SAMPLE.match(line)
        if match is None or match["name"] not in allowed:
            continue
        label, values = allowed[match["name"]]
        found = dict(re.findall(r'(\w+)="([^"]*)"', match["labels"] or ""))
        assert found[label] in values, line


def test_ingestion_buckets_reach_past_the_twenty_second_trigger_bound() -> None:
    assert max(INGESTION_BUCKETS_SECONDS) > 20.0
    assert min(INGESTION_BUCKETS_SECONDS) <= 0.005
