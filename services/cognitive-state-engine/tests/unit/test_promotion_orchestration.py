"""The trigger condition -- Phase 4F.6, A-4F6-2a (TDD 4F.6 §19 rows 1, 4, 9, 10).

**The negative tests are the point.** A trigger that fired slightly too eagerly
-- on a lower promotion, on a repeated promote, on a thought with no proposal --
would pass every happy-path assertion and still hand `autonomy-engine` a
decision nobody asked for. So every non-trigger has its own test.

Nothing here mocks the thing under test: `next_layer`, the ladder and
`promote_thought` are real. The repository is an in-memory fake that keeps the
real `CognitiveStateRepository` semantics (a missing thought raises), and the
trigger port is a recorder, because *how many requests were sent* is a fact
about `promote_thought` rather than about the transport -- the transport is
proven against a real broker in `tests/integration`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from nova_cognitive_state_engine.domain.models import (
    ATTENTION_LAYER_ORDER,
    ActiveThought,
    AttentionLayer,
)
from nova_cognitive_state_engine.domain.ports import ThoughtNotFoundError, TriggerDelivery
from nova_cognitive_state_engine.promotion_orchestration import (
    promote_thought,
    trigger_payload,
)
from nova_contracts import validate_payload
from nova_contracts.events.autonomy import AutonomyDecisionRequestedPayload

PROPOSAL = {
    "category": "delete",
    "risk": "high",
    "action_type": "terminal",
    "execution_target": "terminal",
    "verification_method": "exit_code",
    "title": "prune stale build artifacts",
    "detail": "older than thirty days",
}


class FakeRepository:
    def __init__(self, *thoughts: ActiveThought) -> None:
        self.thoughts = {t.thought_id: t for t in thoughts}
        self.moves: list[tuple[UUID, AttentionLayer]] = []

    async def get_thought(self, thought_id: UUID) -> ActiveThought:
        if thought_id not in self.thoughts:
            raise ThoughtNotFoundError(thought_id)
        return self.thoughts[thought_id]

    async def move_layer(self, thought_id: UUID, layer: AttentionLayer) -> ActiveThought:
        self.moves.append((thought_id, layer))
        moved = self.thoughts[thought_id].model_copy(update={"attention_layer": layer})
        self.thoughts[thought_id] = moved
        return moved


class RecordingTrigger:
    """Counts requests. **Counting is the assertion.**"""

    def __init__(self, reply: TriggerDelivery | None = None) -> None:
        self.requests: list[tuple[AutonomyDecisionRequestedPayload, UUID]] = []
        self._reply = reply or TriggerDelivery(status="decided", outcome="propose")

    async def request_decision(
        self, payload: AutonomyDecisionRequestedPayload, *, correlation_id: UUID
    ) -> TriggerDelivery:
        self.requests.append((payload, correlation_id))
        return self._reply


def _thought(
    layer: AttentionLayer = AttentionLayer.ACTIVE, *, proposal: dict | None = PROPOSAL, **overrides
) -> ActiveThought:
    moment = datetime.now(UTC)
    fields: dict = {
        "thought_id": uuid4(),
        "user_id": uuid4(),
        "description": "Keep the build directory bounded.",
        "priority": 4,
        "confidence": 0.2,
        "current_progress": 0.0,
        "attention_layer": layer,
        "created_at": moment,
        "updated_at": moment,
        "proposed_action": proposal,
    }
    fields.update(overrides)
    return ActiveThought(**fields)


# --- the one case that triggers ------------------------------------------------


async def test_promotion_to_immediate_with_a_complete_proposal_sends_exactly_one_request() -> None:
    thought = _thought(AttentionLayer.ACTIVE)
    repository, trigger = FakeRepository(thought), RecordingTrigger()

    result = await promote_thought(thought.thought_id, repository=repository, trigger=trigger)

    assert result.moved is True
    assert result.thought.attention_layer is AttentionLayer.IMMEDIATE
    assert len(trigger.requests) == 1
    assert result.trigger == TriggerDelivery(status="decided", outcome="propose")


async def test_every_authored_field_is_copied_verbatim() -> None:
    """`risk` above all: `high` here although the thought's confidence is 0.2 --
    nothing is derived from the thought's own signals."""
    thought = _thought(AttentionLayer.ACTIVE)
    trigger = RecordingTrigger()
    await promote_thought(thought.thought_id, repository=FakeRepository(thought), trigger=trigger)

    payload, correlation_id = trigger.requests[0]
    sent = payload.model_dump(mode="json")
    for field, value in PROPOSAL.items():
        assert sent[field] == value, field
    assert payload.thought_id == thought.thought_id
    assert payload.priority == thought.priority
    assert payload.requesting_engine == "cognitive-state-engine"
    assert payload.correlation_id == correlation_id


async def test_the_request_carries_no_subject_id_and_no_user_id() -> None:
    """**§19 row 4.** The producer cannot name a decision or a user -- and the
    payload it builds survives the consumer's `extra="forbid"` validation."""
    thought = _thought(AttentionLayer.ACTIVE)
    trigger = RecordingTrigger()
    await promote_thought(thought.thought_id, repository=FakeRepository(thought), trigger=trigger)

    wire = trigger.requests[0][0].model_dump(mode="json")
    assert "subject_id" not in wire
    assert "user_id" not in wire
    assert isinstance(
        validate_payload("autonomy.decision.requested", wire), AutonomyDecisionRequestedPayload
    )


# --- every case that does not ----------------------------------------------------


async def test_a_thought_without_a_proposal_never_triggers() -> None:
    """**§19 row 1.** Absence is never read as a default."""
    thought = _thought(AttentionLayer.ACTIVE, proposal=None)
    repository, trigger = FakeRepository(thought), RecordingTrigger()

    result = await promote_thought(thought.thought_id, repository=repository, trigger=trigger)

    assert result.moved is True
    assert result.thought.attention_layer is AttentionLayer.IMMEDIATE
    assert trigger.requests == []
    assert result.trigger is None


@pytest.mark.parametrize("start", ATTENTION_LAYER_ORDER[2:])
async def test_a_promotion_that_does_not_reach_immediate_never_triggers(
    start: AttentionLayer,
) -> None:
    thought = _thought(start)
    repository, trigger = FakeRepository(thought), RecordingTrigger()

    result = await promote_thought(thought.thought_id, repository=repository, trigger=trigger)

    assert result.moved is True
    assert result.thought.attention_layer is not AttentionLayer.IMMEDIATE
    assert trigger.requests == []


async def test_promoting_an_already_immediate_thought_moves_nothing_and_triggers_nothing() -> None:
    """The ladder has nowhere to go, so `next_layer` returns `None` -- which is
    what stops a repeated promote from re-firing the trigger."""
    thought = _thought(AttentionLayer.IMMEDIATE)
    repository, trigger = FakeRepository(thought), RecordingTrigger()

    result = await promote_thought(thought.thought_id, repository=repository, trigger=trigger)

    assert result.moved is False
    assert repository.moves == []
    assert trigger.requests == []


async def test_the_transition_goes_through_the_repository() -> None:
    """The existing mechanism records the move -- nothing re-implements it."""
    thought = _thought(AttentionLayer.ACTIVE)
    repository = FakeRepository(thought)
    await promote_thought(thought.thought_id, repository=repository, trigger=RecordingTrigger())
    assert repository.moves == [(thought.thought_id, AttentionLayer.IMMEDIATE)]


async def test_a_missing_thought_raises_and_sends_nothing() -> None:
    trigger = RecordingTrigger()
    with pytest.raises(ThoughtNotFoundError):
        await promote_thought(uuid4(), repository=FakeRepository(), trigger=trigger)
    assert trigger.requests == []


# --- §19 row 10: no retry, whatever the port reports -----------------------------


@pytest.mark.parametrize("status", ["rejected", "degraded", "unavailable", "unconfirmed", "failed"])
async def test_no_outcome_is_retried(status: str) -> None:
    thought = _thought(AttentionLayer.ACTIVE)
    trigger = RecordingTrigger(TriggerDelivery(status=status, error="x"))  # type: ignore[arg-type]

    result = await promote_thought(
        thought.thought_id, repository=FakeRepository(thought), trigger=trigger
    )

    assert len(trigger.requests) == 1
    assert result.trigger is not None
    assert result.trigger.status == status
    # The promotion itself stands: a lost trigger does not undo the move.
    assert result.thought.attention_layer is AttentionLayer.IMMEDIATE


def test_trigger_payload_is_pure() -> None:
    thought = _thought(AttentionLayer.IMMEDIATE)
    assert thought.proposed_action is not None
    correlation_id = uuid4()
    first = trigger_payload(thought, thought.proposed_action, correlation_id=correlation_id)
    second = trigger_payload(thought, thought.proposed_action, correlation_id=correlation_id)
    assert first == second


async def test_each_trigger_gets_its_own_correlation_id() -> None:
    """The producer sets `correlation_id` (TDD 4F.6 §8) fresh per trigger; it
    is a trace id, not a decision identity, so two triggers never share one."""
    first, second = _thought(AttentionLayer.ACTIVE), _thought(AttentionLayer.ACTIVE)
    repository, trigger = FakeRepository(first, second), RecordingTrigger()

    await promote_thought(first.thought_id, repository=repository, trigger=trigger)
    await promote_thought(second.thought_id, repository=repository, trigger=trigger)

    assert len(trigger.requests) == 2
    assert trigger.requests[0][1] != trigger.requests[1][1]
