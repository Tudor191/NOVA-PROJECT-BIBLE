"""`FakeExecutiveRepository` -- an in-memory `domain.ports.ExecutiveRepository`,
mirroring `PostgresExecutiveRepository`'s own behavior (§13, §19) closely
enough that swapping one for the other in a test changes nothing observable."""

from __future__ import annotations

from uuid import UUID, uuid4

from nova_executive_cognition_engine.domain.models import (
    ExecutiveDecisionTrace,
    ExecutiveRequest,
    HumanOverrideRequest,
)
from nova_executive_cognition_engine.domain.ports import OutboxEvent, OutboxRow


class FakeExecutiveRepository:
    def __init__(self) -> None:
        self.requests: dict[UUID, ExecutiveRequest] = {}
        self.decisions: dict[UUID, ExecutiveDecisionTrace] = {}
        self.outcome_reports: list[tuple[UUID, str, float | None, str | None]] = []
        self.outbox: list[OutboxEvent] = []

    async def record_request(self, request: ExecutiveRequest) -> None:
        self.requests[request.correlation_id] = request

    async def requests_for_goal(
        self, goal_id: UUID, *, exclude_correlation_id: UUID | None = None, limit: int = 20
    ) -> list[ExecutiveRequest]:
        return [
            r
            for r in self.requests.values()
            if r.goal_id == goal_id and r.correlation_id != exclude_correlation_id
        ][:limit]

    async def finalize_decision(
        self, *, trace: ExecutiveDecisionTrace, outbox_event: OutboxEvent | None = None
    ) -> ExecutiveDecisionTrace:
        self.decisions[trace.id] = trace
        if outbox_event is not None:
            self.outbox.append(outbox_event)
        return trace

    async def get_decision(self, decision_id: UUID) -> ExecutiveDecisionTrace | None:
        return self.decisions.get(decision_id)

    async def list_decisions(
        self, *, requesting_engine: str | None = None, limit: int = 100
    ) -> list[ExecutiveDecisionTrace]:
        traces = list(self.decisions.values())
        if requesting_engine is not None:
            traces = [
                t
                for t in traces
                if any(
                    c.correlation_id == t.correlation_id
                    and c.requesting_engine == requesting_engine
                    for c in t.contending_requests
                )
            ]
        return traces[:limit]

    async def record_outcome_report(
        self,
        *,
        correlation_id: UUID,
        outcome: str,
        actual_duration_ms: float | None,
        note: str | None,
    ) -> None:
        self.outcome_reports.append((correlation_id, outcome, actual_duration_ms, note))

    async def apply_override(
        self,
        decision_id: UUID,
        override: HumanOverrideRequest,
        *,
        outbox_event: OutboxEvent | None = None,
    ) -> ExecutiveDecisionTrace:
        trace = self.decisions[decision_id]
        trace = trace.model_copy(update={"human_override": override})
        if override.action == "redirect" and override.redirect_outcome is not None:
            trace = trace.model_copy(update={"outcome": override.redirect_outcome})
        self.decisions[decision_id] = trace
        if outbox_event is not None:
            self.outbox.append(outbox_event)
        return trace

    async def enqueue_outbox(self, event: OutboxEvent) -> UUID:
        self.outbox.append(event)
        return uuid4()

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]:
        return []

    async def mark_dispatched(self, outbox_id: UUID) -> None:
        return None
