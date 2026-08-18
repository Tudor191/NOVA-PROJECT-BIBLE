"""`FakeCapabilityPort` -- an in-memory `domain.ports.CapabilityPort`,
scriptable per test: pre-seed `capabilities_by_name` and `invoke_results`
(keyed by `(capability_id, operation)`, a queue popped in call order --
Fork 3C-3's rollback mechanism calls `invoke()` with `operation="write"`
twice for the same capability_id, once for the action's own execute stage
and once for the restore, so a single fixed result per key is not enough)
rather than a real `capability.resolve.request`/`capability.invoke.request`
RPC round trip."""

from __future__ import annotations

from collections import deque
from uuid import UUID

from nova_action_engine.domain.ports import CapabilityInvokeOutcome
from nova_contracts import Capability

_InvokeResult = tuple[CapabilityInvokeOutcome, dict | None, str | None]
_DEFAULT_RESULT: _InvokeResult = ("success", {}, None)


class FakeCapabilityPort:
    def __init__(self) -> None:
        self.capabilities_by_name: dict[str, Capability] = {}
        self.invoke_results: dict[tuple[UUID, str], deque[_InvokeResult]] = {}
        self.invoke_calls: list[dict] = []
        self.resolve_calls: list[str] = []

    def queue_invoke_result(
        self, capability_id: UUID, operation: str, result: _InvokeResult
    ) -> None:
        self.invoke_results.setdefault((capability_id, operation), deque()).append(result)

    async def resolve(
        self, *, name: str, correlation_id: UUID | None = None
    ) -> Capability | None:
        self.resolve_calls.append(name)
        return self.capabilities_by_name.get(name)

    async def invoke(
        self,
        *,
        capability_id: UUID,
        operation: str,
        parameters: dict,
        correlation_id: UUID | None = None,
    ) -> tuple[CapabilityInvokeOutcome, dict | None, str | None]:
        self.invoke_calls.append(
            {"capability_id": capability_id, "operation": operation, "parameters": parameters}
        )
        queue = self.invoke_results.get((capability_id, operation))
        if queue:
            return queue.popleft()
        return _DEFAULT_RESULT
