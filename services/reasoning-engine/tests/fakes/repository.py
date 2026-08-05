"""`FakeReasoningRepository` -- an in-memory `domain.ports.ReasoningRepository`."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from nova_reasoning_engine.domain.models import (
    Alternative,
    Decision,
    Evidence,
    HumanOverrideRequest,
    Hypothesis,
    LifecycleStatus,
    ReasoningProcess,
    ReasoningTrace,
)
from nova_reasoning_engine.domain.ports import OutboxEvent, OutboxRow


class FakeReasoningRepository:
    def __init__(self) -> None:
        self.processes: dict[UUID, ReasoningProcess] = {}
        self.hypotheses: list[Hypothesis] = []
        self.evidence: list[Evidence] = []
        self.alternatives: list[Alternative] = []
        self.decisions: dict[UUID, Decision] = {}
        self.decisions_by_process: dict[UUID, UUID] = {}
        self.traces: dict[UUID, ReasoningTrace] = {}
        self.traces_by_process: dict[UUID, UUID] = {}
        self.outbox: list[OutboxEvent] = []

    async def create_process(self, process: ReasoningProcess) -> ReasoningProcess:
        self.processes[process.id] = process
        return process

    async def transition_process(
        self,
        process_id: UUID,
        *,
        status: LifecycleStatus,
        completed_at: datetime | None = None,
    ) -> None:
        process = self.processes[process_id]
        self.processes[process_id] = process.model_copy(
            update={"status": status, "completed_at": completed_at}
        )

    async def get_process(self, process_id: UUID) -> ReasoningProcess | None:
        return self.processes.get(process_id)

    async def record_hypotheses(self, hypotheses: list[Hypothesis]) -> None:
        self.hypotheses.extend(hypotheses)

    async def update_hypothesis_status(
        self, hypothesis_id: UUID, *, status: Literal["investigating", "supported", "unsupported"]
    ) -> None:
        for i, h in enumerate(self.hypotheses):
            if h.id == hypothesis_id:
                self.hypotheses[i] = h.model_copy(update={"status": status})

    async def record_evidence(self, evidence: list[Evidence]) -> None:
        self.evidence.extend(evidence)

    async def record_alternatives(self, alternatives: list[Alternative]) -> None:
        self.alternatives.extend(alternatives)

    async def finalize(
        self,
        *,
        process: ReasoningProcess,
        decision: Decision,
        trace: ReasoningTrace,
        outbox_event: OutboxEvent | None = None,
    ) -> Decision:
        # Mirrors PostgresReasoningRepository.finalize(): persists exactly the
        # `status`/`completed_at` the caller set on `process`, never its own
        # derived timestamp -- a fake that clobbered these would mask a caller
        # bug that forgets to set them before calling finalize().
        self.processes[process.id] = process
        self.decisions[decision.id] = decision
        self.decisions_by_process[decision.reasoning_process_id] = decision.id
        self.traces[trace.id] = trace
        self.traces_by_process[trace.reasoning_process_id] = trace.id
        if outbox_event is not None:
            self.outbox.append(outbox_event)
        return decision

    async def get_decision(self, decision_id: UUID) -> Decision | None:
        return self.decisions.get(decision_id)

    async def get_decision_for_process(self, reasoning_process_id: UUID) -> Decision | None:
        decision_id = self.decisions_by_process.get(reasoning_process_id)
        return self.decisions.get(decision_id) if decision_id else None

    async def get_trace(self, trace_id: UUID) -> ReasoningTrace | None:
        return self.traces.get(trace_id)

    async def get_trace_for_process(self, reasoning_process_id: UUID) -> ReasoningTrace | None:
        trace_id = self.traces_by_process.get(reasoning_process_id)
        return self.traces.get(trace_id) if trace_id else None

    async def list_traces(
        self, *, user_id: UUID | None = None, limit: int = 100
    ) -> list[ReasoningTrace]:
        traces = list(self.traces.values())
        if user_id is not None:
            traces = [
                t
                for t in traces
                if (p := self.processes.get(t.reasoning_process_id)) is not None
                and p.user_id == user_id
            ]
        return traces[:limit]

    async def apply_override(
        self,
        decision_id: UUID,
        override: HumanOverrideRequest,
        *,
        outbox_event: OutboxEvent | None = None,
    ) -> Decision:
        decision = self.decisions[decision_id]
        updates: dict = {"human_override": override}
        if override.action == "redirect" and override.redirect_alternative_id is not None:
            updates["selected_alternative_id"] = override.redirect_alternative_id
        updated = decision.model_copy(update=updates)
        self.decisions[decision_id] = updated
        if outbox_event is not None:
            self.outbox.append(outbox_event)
        return updated

    async def enqueue_outbox(self, event: OutboxEvent) -> UUID:
        self.outbox.append(event)
        return uuid4()

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]:
        return []

    async def mark_dispatched(self, outbox_id: UUID) -> None:
        return None
