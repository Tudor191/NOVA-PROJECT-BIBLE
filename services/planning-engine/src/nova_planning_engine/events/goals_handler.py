"""`planning.goals.current.request` request/reply RPC handler (TDD 3E §8)
-- the real-RPC replacement for both `reasoning-engine`'s and
`executive-cognition-engine`'s own `GoalsPort` placeholder, which
previously always returned an empty list. Mirrors `decompose_handler.py`'s
own structure exactly (this engine's other served RPC).

**Disclosed scope limitation, not a silent gap.** TDD 3E §8 describes this
RPC as mapping "a user's active `TaskGraph`s" to `Goal`s, but the
`task_graph` table (TDD 3B §4) carries no `user_id`/ownership column --
`payload.user_id` is accepted (the contract requires it) but is **not**
used to filter `TaskGraph`s, since no persisted attribution exists to
filter by. This reply currently reflects every active `TaskGraph` in the
system, not one user's own subset. `payload.scope` is accepted and
similarly unused -- no document defines what it should filter either.
Both are flagged here for a follow-on slice, per `domain/ports.py::
PlanningRepository.list_all`'s own matching disclosure -- not something
this GoalsPort-migration-only slice is authorized to redesign.
"""

from __future__ import annotations

from fastapi import FastAPI
from nova_contracts import (
    EventEnvelope,
    PlanningGoalsCurrentReplyPayload,
    PlanningGoalsCurrentRequestPayload,
)
from nova_observability import get_logger

from nova_planning_engine.domain.goals import is_active, rank_active_graphs, to_goal_snapshot

__all__ = ["make_goals_current_request_handler"]

logger = get_logger("planning-engine.events.goals_handler")


def make_goals_current_request_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> PlanningGoalsCurrentReplyPayload:
        state = app.state
        payload = PlanningGoalsCurrentRequestPayload.model_validate(envelope.payload)

        all_graphs = await state.repository.list_all()
        active_graphs = rank_active_graphs([g for g in all_graphs if is_active(g)])
        goals = [
            to_goal_snapshot(graph, rank_index=index, total=len(active_graphs))
            for index, graph in enumerate(active_graphs)
        ]

        state.metrics.planning_goals_current_request_served_total.add(1)
        logger.info(
            "planning.goals.current.request served",
            extra={
                "requesting_engine": payload.requesting_engine,
                "goal_count": len(goals),
            },
        )
        return PlanningGoalsCurrentReplyPayload(goals=goals)

    return handle
