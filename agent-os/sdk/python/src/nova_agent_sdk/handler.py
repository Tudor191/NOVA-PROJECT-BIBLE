"""`AgentHandler` -- the standardized "syscall" interface every Agent
Package implements (doc 12 §4, verbatim method set). Every agent,
regardless of category or author, implements this Protocol from
`src/handler.py` (doc 12 §3).

`on_assign`'s `task` parameter is typed `TaskNodeSnapshot` (`nova_contracts`),
not planning-engine's own domain `TaskNode` doc 12 §4 names -- the domain-
vs-wire-payload split already applied to `AgentContext.task`
(`nova_contracts.entities`, Phase 3E Milestone 1) and to
`tools/scaffold-agent-package.py`'s generated `handler.py` stub: a
cross-engine consumer gets the published wire snapshot, never another
engine's internal domain type (ADR-004).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from nova_contracts import (
    AgentContext,
    AgentHealth,
    AgentMessage,
    AgentMetrics,
    AgentResult,
    TaskNodeSnapshot,
    ValidationOutcome,
)

from nova_agent_sdk.manifest import AgentManifest

__all__ = ["AgentHandler"]


@runtime_checkable
class AgentHandler(Protocol):
    """Doc 12 §4, verbatim method set."""

    # Lifecycle (Part 4 Agent Lifecycle, doc 12 §5)
    async def on_load(self, manifest: AgentManifest) -> None: ...
    async def on_unload(self) -> None: ...
    async def on_assign(self, task: TaskNodeSnapshot, context: AgentContext) -> None: ...
    async def execute(self) -> AgentResult: ...
    async def on_pause(self) -> None: ...
    async def on_resume(self) -> None: ...
    async def self_validate(self, result: AgentResult) -> ValidationOutcome: ...

    # Health (Part 4 "report uncertainty... fail gracefully")
    async def health_check(self) -> AgentHealth: ...

    # Communication (kernel-mediated only -- doc 12 §8)
    async def on_message(self, message: AgentMessage) -> AgentMessage | None: ...

    # Metrics (Part 4 "Agent Evolution")
    def metrics_snapshot(self) -> AgentMetrics: ...
