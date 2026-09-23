"""`decision_orchestration` -- the trigger's consumer, Phase 4F.6 (TDD 4F.6
§19 rows 3-14).

**Every trigger-path test enters through `handle_decision_request` with an
`EventEnvelope`**, exactly as `serve()` delivers one, and none of them calls
`decide()` directly. The last two tests are the exception, deliberately: they
pin `decide()`'s new `subject_id` keyword, which is a property of `decide()`
itself rather than of the trigger path. The policy engine, the permission matrix, the gate order
and `decide()` itself are all real; the repository is the in-memory fake this
engine's default tier already uses, the trust source is a spy, and the
dispatcher is a recorder, because *how many dispatches happened* is a fact about
the decision rather than the transport. The transport, the real `serve()` and
real Postgres are in `tests/integration/test_decision_trigger_real_infra.py`.
"""

from __future__ import annotations

from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

import pytest
from nova_autonomy_engine import decision_orchestration
from nova_autonomy_engine.decision_orchestration import (
    DECISION_TRIGGER_SUBJECT,
    decision_request,
    derive_subject_id,
    handle_decision_request,
)
from nova_autonomy_engine.domain.decision import DecisionRequest, decide
from nova_autonomy_engine.domain.models import (
    AutonomyLevel,
    DecisionOutcome,
    PermissionCategory,
    PermissionGrant,
    Policy,
    PolicyEffect,
    PolicyMatch,
)
from nova_autonomy_engine.domain.ports import (
    ActionDispatchResult,
    ActionDispatchTimeout,
)
from nova_contracts import ActionExecuteRequestPayload, EventEnvelope
from nova_contracts.events.planning import RiskLevel

from tests.fakes.repository import FakeAutonomyRepository
from tests.fakes.trust_source import SpyTrustSource

PRIMARY = UUID("00000000-0000-0000-0000-0000000004f6")


class RecordingDispatcher:
    def __init__(self, *, raises: Exception | None = None) -> None:
        self.payloads: list[ActionExecuteRequestPayload] = []
        self._raises = raises

    async def dispatch(
        self, payload: ActionExecuteRequestPayload, *, correlation_id: UUID | None = None
    ) -> ActionDispatchResult:
        self.payloads.append(payload)
        if self._raises is not None:
            raise self._raises
        return ActionDispatchResult(action_id=payload.action_id, status="completed")


class BrokenRepository(FakeAutonomyRepository):
    """Fails on the first server-side read -- the point before `decide()`."""

    async def get_level(self, user_id: UUID):  # type: ignore[no-untyped-def]
        raise ConnectionError("database unreachable")


class UnrecordableRepository(FakeAutonomyRepository):
    """Reads succeed; every write fails -- the point after `decide()`."""

    async def insert_suggestion(self, suggestion, log_entry):  # type: ignore[no-untyped-def]
        raise ConnectionError("database went away mid-write")

    async def append_decision_log(self, entry):  # type: ignore[no-untyped-def]
        raise ConnectionError("database went away mid-write")


def _payload(**overrides: object) -> dict:
    fields: dict = {
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
    }
    fields.update(overrides)
    return fields


def _envelope(payload: dict | None = None, *, event_id: UUID | None = None) -> EventEnvelope:
    fields: dict = {
        "subject": DECISION_TRIGGER_SUBJECT,
        "source_engine": "cognitive-state-engine",
        "correlation_id": uuid4(),
        "payload": payload if payload is not None else _payload(),
    }
    if event_id is not None:
        fields["event_id"] = event_id
    return EventEnvelope(**fields)


async def _configure(
    repository: FakeAutonomyRepository,
    *,
    level: AutonomyLevel | None,
    auto_execute: bool = False,
    grant: bool = True,
    deny: bool = False,
) -> None:
    if level is not None:
        await repository.set_level(PRIMARY, level)
    if auto_execute:
        await repository.create_policy(
            Policy(
                user_id=PRIMARY,
                name="auto-execute low-risk creates",
                effect=PolicyEffect.AUTO_EXECUTE,
                match=PolicyMatch(category=PermissionCategory.CREATE),
            )
        )
    if deny:
        await repository.create_policy(
            Policy(
                user_id=PRIMARY,
                name="never create",
                effect=PolicyEffect.DENY,
                match=PolicyMatch(category=PermissionCategory.CREATE),
            )
        )
    if grant:
        await repository.upsert_permission_grants(
            PRIMARY,
            [
                PermissionGrant(
                    user_id=PRIMARY, category=PermissionCategory.CREATE, max_risk=RiskLevel.CRITICAL
                )
            ],
        )


async def _handle(
    envelope: EventEnvelope,
    repository: FakeAutonomyRepository,
    *,
    dispatcher: RecordingDispatcher | None = None,
    trust: SpyTrustSource | None = None,
):  # type: ignore[no-untyped-def]
    return await handle_decision_request(
        envelope,
        repository=repository,
        trust_source=trust or SpyTrustSource(),
        dispatcher=dispatcher or RecordingDispatcher(),
        user_id=PRIMARY,
    )


@pytest.fixture
def decide_calls(monkeypatch: pytest.MonkeyPatch) -> list[DecisionRequest]:
    """Wraps the real `decide()` to count invocations -- the evidence for every
    *"`decide()` is not invoked"* claim below. It still runs the real one."""
    calls: list[DecisionRequest] = []

    async def _counting(request, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(request)
        return await decide(request, **kwargs)

    monkeypatch.setattr(decision_orchestration, "decide", _counting)
    return calls


# --- §19 row 3: identity -------------------------------------------------------


def test_the_namespace_is_the_pinned_literal() -> None:
    """A moved namespace would silently re-key every redelivered trigger."""
    namespace = decision_orchestration._DECISION_TRIGGER_NAMESPACE
    assert namespace == UUID("0c81f3b8-e30f-5f0a-9241-8985e4b83489")
    # Its documented provenance (TDD 4F.6 §5.2) still reproduces it.
    assert namespace == uuid5(NAMESPACE_DNS, "autonomy.decision.requested.nova")


def test_subject_id_is_uuid5_of_the_event_id_string_and_nothing_else() -> None:
    event_id = uuid4()
    namespace = UUID("0c81f3b8-e30f-5f0a-9241-8985e4b83489")
    assert derive_subject_id(event_id) == uuid5(namespace, str(event_id))
    assert derive_subject_id(event_id) == derive_subject_id(UUID(str(event_id)))
    assert derive_subject_id(event_id) != derive_subject_id(uuid4())


async def test_the_same_event_id_derives_the_same_subject_whatever_else_differs() -> None:
    """`occurred_at`, `correlation_id` and the payload are non-participants."""
    event_id = uuid4()
    first = await _handle(
        _envelope(_payload(title="one"), event_id=event_id), FakeAutonomyRepository()
    )
    second = await _handle(
        _envelope(_payload(title="two", priority=9), event_id=event_id), FakeAutonomyRepository()
    )
    assert first.subject_id == second.subject_id == derive_subject_id(event_id)


async def test_the_decision_log_carries_the_derived_subject() -> None:
    repository = FakeAutonomyRepository()
    envelope = _envelope()
    reply = await _handle(envelope, repository)
    assert [entry.subject_id for entry in repository.decision_log] == [
        derive_subject_id(envelope.event_id)
    ]
    assert reply.subject_id == derive_subject_id(envelope.event_id)


# --- §19 row 4 and §9: the producer cannot name identity or user ----------------


@pytest.mark.parametrize("field", ["subject_id", "user_id"])
async def test_a_producer_supplied_identity_field_is_rejected_before_decide(
    field: str, decide_calls: list[DecisionRequest]
) -> None:
    repository, dispatcher, trust = (
        FakeAutonomyRepository(),
        RecordingDispatcher(),
        SpyTrustSource(),
    )
    reply = await _handle(
        _envelope(_payload(**{field: str(uuid4())})),
        repository,
        dispatcher=dispatcher,
        trust=trust,
    )
    assert reply.rejected is True
    assert reply.degraded is False
    assert reply.outcome is None
    assert reply.subject_id is None
    assert decide_calls == []
    assert repository.decision_log == []
    assert dispatcher.payloads == []
    assert not trust.was_consulted


@pytest.mark.parametrize(
    "payload",
    [
        {k: v for k, v in _payload().items() if k != "risk"},
        _payload(category="administer"),
        _payload(action_type="deploy"),
        _payload(title=""),
        {},
    ],
    ids=["missing-risk", "unknown-category", "unrunnable-action-type", "empty-title", "empty"],
)
async def test_a_malformed_trigger_is_rejected_and_decide_is_not_invoked(
    payload: dict, decide_calls: list[DecisionRequest]
) -> None:
    repository = FakeAutonomyRepository()
    reply = await _handle(_envelope(payload), repository)
    assert reply.rejected is True
    assert decide_calls == []
    assert repository.decision_log == []


async def test_user_id_is_resolved_server_side(decide_calls: list[DecisionRequest]) -> None:
    """**§19 row 7.** The decision is made for `primary_user_id` -- the payload
    has no user, and the trust read, the request and the suggestion all agree."""
    repository, trust = FakeAutonomyRepository(), SpyTrustSource()
    await _configure(repository, level=AutonomyLevel.SUGGESTIVE)
    await _handle(_envelope(), repository, trust=trust)

    assert [request.user_id for request in decide_calls] == [PRIMARY]
    assert trust.reads == [PRIMARY]
    assert [s.user_id for s in repository.suggestions.values()] == [PRIMARY]


def test_decision_request_maps_every_field_and_invents_none() -> None:
    from nova_contracts.events.autonomy import AutonomyDecisionRequestedPayload

    payload = AutonomyDecisionRequestedPayload.model_validate(_payload(risk="high"))
    request = decision_request(payload, user_id=PRIMARY)
    assert request.user_id == PRIMARY
    assert request.category is PermissionCategory.CREATE
    assert request.risk is RiskLevel.HIGH
    assert (request.title, request.detail, request.priority) == (
        payload.title,
        payload.detail,
        payload.priority,
    )
    assert (request.action_type, request.execution_target, request.verification_method) == (
        "filesystem",
        "filesystem",
        "none",
    )
    assert request.capability_class is None


def test_decision_request_has_no_subject_id_field() -> None:
    """`subject_id` reaches `decide()` as a keyword from the orchestrator,
    never as a field anything upstream could set."""
    assert "subject_id" not in DecisionRequest.model_fields


# --- §19 row 7: the level is read server-side, and chooses --------------------


async def test_an_unconfigured_instance_only_observes() -> None:
    repository, dispatcher = FakeAutonomyRepository(), RecordingDispatcher()
    await _configure(repository, level=None, auto_execute=True)
    reply = await _handle(_envelope(), repository, dispatcher=dispatcher)
    assert reply.outcome == DecisionOutcome.OBSERVE_ONLY.value
    assert dispatcher.payloads == []
    assert repository.suggestions == {}


async def test_level_zero_observes_and_never_executes() -> None:
    repository, dispatcher = FakeAutonomyRepository(), RecordingDispatcher()
    await _configure(repository, level=AutonomyLevel.OBSERVATION_ONLY, auto_execute=True)
    reply = await _handle(_envelope(), repository, dispatcher=dispatcher)
    assert reply.outcome == DecisionOutcome.OBSERVE_ONLY.value
    assert dispatcher.payloads == []


async def test_level_one_proposes_and_never_executes() -> None:
    """Even with an `AUTO_EXECUTE` policy: Level 1 is not execution-eligible."""
    repository, dispatcher = FakeAutonomyRepository(), RecordingDispatcher()
    await _configure(repository, level=AutonomyLevel.SUGGESTIVE, auto_execute=True)
    envelope = _envelope()
    reply = await _handle(envelope, repository, dispatcher=dispatcher)

    assert reply.outcome == DecisionOutcome.PROPOSE.value
    assert dispatcher.payloads == []
    assert list(repository.suggestions) == [derive_subject_id(envelope.event_id)]


async def test_level_two_with_every_gate_satisfied_executes_exactly_once() -> None:
    """The one path to `action.execute`, and the identity it carries: the
    dispatched `action_id` **is** the derived `subject_id`."""
    repository, dispatcher = FakeAutonomyRepository(), RecordingDispatcher()
    await _configure(repository, level=AutonomyLevel.ASSISTED, auto_execute=True)
    envelope = _envelope()
    reply = await _handle(envelope, repository, dispatcher=dispatcher)

    assert reply.outcome == DecisionOutcome.EXECUTE.value
    assert [p.action_id for p in dispatcher.payloads] == [derive_subject_id(envelope.event_id)]
    assert [e.outcome for e in repository.decision_log] == [DecisionOutcome.EXECUTE]
    assert repository.suggestions == {}


async def test_level_two_without_a_policy_proposes() -> None:
    """Fail-closed: no `AUTO_EXECUTE` policy, no execution."""
    repository, dispatcher = FakeAutonomyRepository(), RecordingDispatcher()
    await _configure(repository, level=AutonomyLevel.ASSISTED)
    reply = await _handle(_envelope(), repository, dispatcher=dispatcher)
    assert reply.outcome == DecisionOutcome.PROPOSE.value
    assert dispatcher.payloads == []


@pytest.mark.parametrize("risk", ["moderate", "high", "critical"])
async def test_above_low_never_auto_executes(risk: str) -> None:
    repository, dispatcher = FakeAutonomyRepository(), RecordingDispatcher()
    await _configure(repository, level=AutonomyLevel.ASSISTED, auto_execute=True)
    reply = await _handle(_envelope(_payload(risk=risk)), repository, dispatcher=dispatcher)
    assert reply.outcome != DecisionOutcome.EXECUTE.value
    assert dispatcher.payloads == []


async def test_a_policy_denial_denies_and_dispatches_nothing() -> None:
    repository, dispatcher, trust = (
        FakeAutonomyRepository(),
        RecordingDispatcher(),
        SpyTrustSource(),
    )
    await _configure(repository, level=AutonomyLevel.ASSISTED, auto_execute=True, deny=True)
    reply = await _handle(_envelope(), repository, dispatcher=dispatcher, trust=trust)
    assert reply.outcome == DecisionOutcome.DENY.value
    assert dispatcher.payloads == []
    assert not trust.was_consulted
    assert [e.outcome for e in repository.decision_log] == [DecisionOutcome.DENY]


async def test_a_permission_denial_denies_and_dispatches_nothing() -> None:
    repository, dispatcher = FakeAutonomyRepository(), RecordingDispatcher()
    await _configure(repository, level=AutonomyLevel.ASSISTED, auto_execute=True, grant=False)
    reply = await _handle(_envelope(), repository, dispatcher=dispatcher)
    assert reply.outcome == DecisionOutcome.DENY.value
    assert dispatcher.payloads == []


async def test_a_dispatch_timeout_is_recorded_once_and_not_retried() -> None:
    repository = FakeAutonomyRepository()
    dispatcher = RecordingDispatcher(raises=ActionDispatchTimeout("no reply within 15.0s"))
    await _configure(repository, level=AutonomyLevel.ASSISTED, auto_execute=True)
    reply = await _handle(_envelope(), repository, dispatcher=dispatcher)
    assert reply.outcome == DecisionOutcome.TIMEOUT.value
    assert len(dispatcher.payloads) == 1
    assert [e.outcome for e in repository.decision_log] == [DecisionOutcome.TIMEOUT]


# --- §19 row 8: no Layer 2 ------------------------------------------------------


async def test_two_event_ids_with_identical_payloads_are_two_decisions() -> None:
    """Different `event_id`s are **distinct transport identities** -- no logical
    deduplication is invented (A-4F6-3 Layer 2 is DEFERRED)."""
    repository, dispatcher = FakeAutonomyRepository(), RecordingDispatcher()
    await _configure(repository, level=AutonomyLevel.ASSISTED, auto_execute=True)
    payload = _payload()
    first = await _handle(_envelope(dict(payload)), repository, dispatcher=dispatcher)
    second = await _handle(_envelope(dict(payload)), repository, dispatcher=dispatcher)

    assert first.subject_id != second.subject_id
    assert len(dispatcher.payloads) == 2
    assert len(repository.decision_log) == 2


async def test_a_redelivered_envelope_dispatches_under_the_same_action_id() -> None:
    """Layer 1: the redelivery reaches `action-engine` with the **same**
    `action_id`, which is what its terminal-replay guard keys on."""
    repository, dispatcher = FakeAutonomyRepository(), RecordingDispatcher()
    await _configure(repository, level=AutonomyLevel.ASSISTED, auto_execute=True)
    envelope = _envelope()
    await _handle(envelope, repository, dispatcher=dispatcher)
    await _handle(envelope, repository, dispatcher=dispatcher)

    assert [p.action_id for p in dispatcher.payloads] == [derive_subject_id(envelope.event_id)] * 2


# --- §19 rows 11-14: Design A ----------------------------------------------------


async def test_a_failure_before_deciding_is_degraded_and_decide_is_not_invoked(
    decide_calls: list[DecisionRequest],
) -> None:
    repository, dispatcher, trust = BrokenRepository(), RecordingDispatcher(), SpyTrustSource()
    reply = await _handle(_envelope(), repository, dispatcher=dispatcher, trust=trust)

    assert reply.degraded is True
    assert reply.rejected is False
    assert reply.outcome is None
    assert reply.subject_id is None  # the marker for "nothing was decided"
    assert reply.error is not None and "ConnectionError" in reply.error
    assert decide_calls == []
    assert dispatcher.payloads == []
    assert not trust.was_consulted
    assert repository.decision_log == []


async def test_decide_raising_is_degraded_with_the_subject_and_not_retried(
    decide_calls: list[DecisionRequest],
) -> None:
    """An unknown dispatch fault propagates out of `decide()` exactly as 4F.5
    left it; the orchestrator turns it into a reply, once."""
    repository = FakeAutonomyRepository()
    dispatcher = RecordingDispatcher(raises=RuntimeError("unknown transport fault"))
    await _configure(repository, level=AutonomyLevel.ASSISTED, auto_execute=True)
    envelope = _envelope()
    reply = await _handle(envelope, repository, dispatcher=dispatcher)

    assert reply.degraded is True
    assert reply.outcome is None
    assert reply.subject_id == derive_subject_id(envelope.event_id)
    assert len(decide_calls) == 1
    assert len(dispatcher.payloads) == 1
    assert repository.decision_log == []


async def test_a_failure_to_record_is_degraded_and_names_the_outcome() -> None:
    repository = UnrecordableRepository()
    await _configure(repository, level=AutonomyLevel.SUGGESTIVE)
    reply = await _handle(_envelope(), repository)

    assert reply.degraded is True
    assert reply.outcome == DecisionOutcome.PROPOSE.value
    assert reply.subject_id is not None


async def test_the_outcome_vocabulary_is_unchanged() -> None:
    """**§19 row 13.** No new `DecisionOutcome` -- Design A reports through the
    reply, not through the log."""
    assert {o.value for o in DecisionOutcome} == {
        "observe_only",
        "propose",
        "deny",
        "execute",
        "timeout",
    }


# --- decide()'s new keyword leaves every existing caller unchanged -------------


async def test_decide_without_a_subject_id_still_mints_a_fresh_one() -> None:
    request = DecisionRequest(
        user_id=PRIMARY, category=PermissionCategory.CREATE, risk=RiskLevel.LOW, title="t"
    )
    kwargs = {
        "level": AutonomyLevel.SUGGESTIVE,
        "policies": [],
        "grants": [],
        "trust_source": SpyTrustSource(),
    }
    first = await decide(request, **kwargs)  # type: ignore[arg-type]
    second = await decide(request, **kwargs)  # type: ignore[arg-type]
    assert first.log_entry.subject_id != second.log_entry.subject_id


async def test_decide_uses_a_supplied_subject_id_everywhere_it_names_one() -> None:
    subject_id = uuid4()
    result = await decide(
        DecisionRequest(
            user_id=PRIMARY, category=PermissionCategory.CREATE, risk=RiskLevel.LOW, title="t"
        ),
        level=AutonomyLevel.SUGGESTIVE,
        policies=[],
        grants=[
            PermissionGrant(
                user_id=PRIMARY, category=PermissionCategory.CREATE, max_risk=RiskLevel.CRITICAL
            )
        ],
        trust_source=SpyTrustSource(),
        subject_id=subject_id,
    )
    assert result.log_entry.subject_id == subject_id
    assert result.suggestion is not None
    assert result.suggestion.id == subject_id
