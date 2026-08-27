"""`GoalsClient` -- `domain.ports.GoalsPort` implementation (docs/design/
phase-2c/00-executive-cognition-engine.md §5.7), migrated per TDD 3E §8: a
real RPC against `planning-engine`'s own `planning.goals.current.request`,
replacing the placeholder that always returned an empty list. `GoalsPort`'s
own shape and every caller of `current_goals()` are unchanged (§24) -- the
same "swap the placeholder implementation for a real RPC-backed one"
precedent `PersonalContextPort` already established in Phase 2D-D, mirrored
here field-for-field on `WorldModelClient`'s own request/timeout-degrade
shape. Unlike Reasoning Engine's own `Goal`, this engine's own `Goal`
carries `goal_tier` (ADR-029) -- populated directly from `GoalSnapshot.goal_tier`,
`planning-engine`'s own read-time derivation.

A timeout degrades to an empty list, never an exception -- `long_term_alignment`
(§6.1) already treats "no current goals" as a valid, handled state (the
same value this placeholder always returned), so callers observe no
behavior change on a timeout versus before this migration.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from nova_contracts import PlanningGoalsCurrentReplyPayload, PlanningGoalsCurrentRequestPayload

from nova_executive_cognition_engine.domain.models import Goal
from nova_executive_cognition_engine.domain.ports import EventPublisher

__all__ = ["GoalsClient"]

SOURCE_ENGINE = "executive-cognition-engine"
DEFAULT_TIMEOUT_MS = 2000


class GoalsClient:
    def __init__(
        self, event_publisher: EventPublisher, *, timeout_ms: int = DEFAULT_TIMEOUT_MS
    ) -> None:
        self._event_publisher = event_publisher
        self._timeout_ms = timeout_ms

    async def current_goals(
        self, *, user_id: UUID, scope: str | None = None, correlation_id: UUID | None = None
    ) -> list[Goal]:
        try:
            reply = await self._event_publisher.request(
                "planning.goals.current.request",
                PlanningGoalsCurrentRequestPayload(
                    user_id=user_id,
                    scope=scope,
                    requesting_engine=SOURCE_ENGINE,
                    correlation_id=correlation_id or uuid4(),
                ),
                source_engine=SOURCE_ENGINE,
                correlation_id=correlation_id,
                timeout_ms=self._timeout_ms,
            )
        except TimeoutError:
            return []
        parsed = PlanningGoalsCurrentReplyPayload.model_validate(reply.payload)
        return [
            Goal(
                id=snapshot.id,
                description=snapshot.description,
                priority=snapshot.priority,
                goal_tier=snapshot.goal_tier,
            )
            for snapshot in parsed.goals
        ]
