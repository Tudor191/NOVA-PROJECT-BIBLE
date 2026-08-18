"""`FakeActionRepository` -- an in-memory `domain.ports.ActionRepository`,
mirroring `PostgresActionRepository`'s own behavior closely enough that
swapping one for the other in a test changes nothing observable, including
the `Action.id` primary-key uniqueness -> `ActionAlreadyExistsError`
translation the natural-key idempotency guard (§5.3) depends on."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from nova_action_engine.domain.models import IdentityConfidencePolicy, PendingApproval
from nova_action_engine.domain.ports import ActionAlreadyExistsError
from nova_contracts import Action


class FakeActionRepository:
    def __init__(self) -> None:
        self.actions: dict[UUID, Action] = {}
        self.results: dict[UUID, tuple[dict | None, str | None]] = {}
        self.pending_approvals: dict[UUID, PendingApproval] = {}
        self.execution_history: list[dict] = []
        self.identity_confidence_policies: dict[UUID, IdentityConfidencePolicy] = {}

    async def find_by_id(self, action_id: UUID) -> Action | None:
        return self.actions.get(action_id)

    async def insert(self, action: Action) -> Action:
        if action.id in self.actions:
            raise ActionAlreadyExistsError(f"action {action.id} already exists")
        self.actions[action.id] = action
        return action

    async def update_status(
        self, action_id: UUID, *, status: str, confidence: float | None = None
    ) -> None:
        action = self.actions.get(action_id)
        if action is None:
            return
        updates: dict[str, object] = {"status": status}
        if confidence is not None:
            updates["confidence"] = confidence
        self.actions[action_id] = action.model_copy(update=updates)

    async def record_result(
        self, action_id: UUID, *, result: dict | None, error: str | None
    ) -> None:
        self.results[action_id] = (result, error)

    async def get_result(self, action_id: UUID) -> tuple[dict | None, str | None] | None:
        return self.results.get(action_id)

    async def insert_pending_approval(self, approval: PendingApproval) -> None:
        self.pending_approvals[approval.action_id] = approval

    async def find_pending_approval(self, action_id: UUID) -> PendingApproval | None:
        return self.pending_approvals.get(action_id)

    async def decide_pending_approval(
        self, action_id: UUID, *, decision: Literal["approved", "denied"], decided_at: datetime
    ) -> None:
        approval = self.pending_approvals.get(action_id)
        if approval is None:
            return
        self.pending_approvals[action_id] = approval.model_copy(
            update={"decision": decision, "decided_at": decided_at}
        )

    async def record_execution_history(
        self,
        *,
        action_id: UUID,
        stage: str,
        outcome: str,
        detail: str | None = None,
    ) -> None:
        self.execution_history.append(
            {"action_id": action_id, "stage": stage, "outcome": outcome, "detail": detail}
        )

    async def find_identity_confidence_policy(
        self, user_id: UUID
    ) -> IdentityConfidencePolicy | None:
        return self.identity_confidence_policies.get(user_id)
