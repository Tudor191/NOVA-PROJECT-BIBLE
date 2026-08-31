"""`FakeReasoningPort`/`FakeDecisionMemoryPort` -- in-memory
`domain.ports.ReasoningPort`/`DecisionMemoryPort` for `domain/conflict.py`
unit tests."""

from __future__ import annotations

from uuid import UUID

from nova_agent_os_supervisors.domain.ports import ReasoningOutcome

__all__ = ["FakeDecisionMemoryPort", "FakeReasoningPort"]


class FakeReasoningPort:
    def __init__(self, *, outcome: ReasoningOutcome) -> None:
        self._outcome = outcome
        self.calls: list[str] = []

    async def reason(
        self, *, objective_text: str, user_id: UUID, correlation_id: UUID | None = None
    ) -> ReasoningOutcome:
        self.calls.append(objective_text)
        return self._outcome


class FakeDecisionMemoryPort:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    async def record(
        self,
        *,
        objective: str,
        alternatives: list[str],
        chosen_alternative: str,
        reasoning: str,
        correlation_id: UUID,
    ) -> None:
        self.records.append(
            {
                "objective": objective,
                "alternatives": alternatives,
                "chosen_alternative": chosen_alternative,
                "reasoning": reasoning,
                "correlation_id": correlation_id,
            }
        )
