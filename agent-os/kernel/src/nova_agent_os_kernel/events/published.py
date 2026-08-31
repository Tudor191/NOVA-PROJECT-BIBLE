"""Every subject Kernel is permitted to publish. See ADR-004
(docs/architecture/00-overview-and-decisions.md).

The three RPC subjects (`agent_os.registry.find_healthy_package.request`,
`agent_os.supervisor.restart_plan.request`, `ai_model.generate.request`) are
outbound request/reply calls the Kernel Scheduler makes as a caller
(`RegistryClient`/`SupervisorClient`/`ModelGatewayClient`), not wire events
this component owns -- listed here because `BoundEventBus.request()`
enforces this same allow-list for outbound RPC subjects, identically to how
`agent-os/registry`'s own `events/published.py` lists its own two outbound
RPC subjects for the same Fork D precedent."""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "agent_os.task.completed",
        "agent_os.registry.find_healthy_package.request",
        "agent_os.supervisor.restart_plan.request",
        "agent_os.supervisor.peer_review.request",
        "ai_model.generate.request",
        "action.execute",
    }
)
