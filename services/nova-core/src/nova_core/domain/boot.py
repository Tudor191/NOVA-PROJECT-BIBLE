"""NovaHost: the 7-phase boot sequence from Bible Part 20, "System Boot Sequence",
implemented as an explicit state machine rather than a linear script -- so the
current phase, health, and uptime are queryable at any moment (feeds `/internal/health`
and the future System dashboard, docs/architecture/04-frontend-architecture.md).

Framework-free by design (docs/architecture/03-backend-architecture.md §1): this
module imports only `nova_contracts` and `nova_eventbus_sdk`'s Protocol, never
FastAPI -- `main.py` is what wires it into a running process.
"""

from __future__ import annotations

import time
from uuid import uuid4

from nova_contracts import (
    EventEnvelope,
    HeartbeatPayload,
    ModuleStatus,
    ModuleStatusChangedPayload,
)
from nova_eventbus_sdk.interface import EventBus

from nova_core.domain.registry import BootPhase, ModuleRegistry


class BootError(RuntimeError):
    """Raised when a module fails to start or fails its health check during boot."""


class NovaHost:
    """Drives NOVA's boot sequence and tracks the system's current lifecycle state."""

    def __init__(self, *, event_bus: EventBus, registry: ModuleRegistry) -> None:
        self._bus = event_bus
        self._registry = registry
        self._status = ModuleStatus.STARTING
        self._current_phase: BootPhase | None = None
        self._started_at: float | None = None

    @property
    def status(self) -> ModuleStatus:
        return self._status

    @property
    def current_phase(self) -> BootPhase | None:
        return self._current_phase

    @property
    def uptime_seconds(self) -> float:
        if self._started_at is None:
            return 0.0
        return time.monotonic() - self._started_at

    @property
    def is_ready(self) -> bool:
        return self._current_phase is BootPhase.READY and self._status is ModuleStatus.HEALTHY

    async def boot(self) -> None:
        """Run every boot phase in order. Raises `BootError` on failure; nova-core's
        lifespan is responsible for deciding whether to retry or exit on that error.
        """
        self._started_at = time.monotonic()
        await self._phase_1_bootstrap()
        await self._phase_2_data_engines()
        await self._phase_3_cognitive_engines()
        await self._phase_4_agents_and_capabilities()
        await self._phase_5_health_checks()
        await self._phase_6_context_sync()
        await self._phase_7_ready()

    async def shutdown(self) -> None:
        """Part 20 "Shutdown Sequence", minimal Phase 0 form: no in-flight tasks or
        working memory exist yet to drain/persist -- those steps arrive with the
        engines that produce that state (Roadmap Phases 1+).
        """
        self._status = ModuleStatus.DOWN
        await self._publish_status(ModuleStatus.DOWN, reason="shutdown requested")
        await self._bus.close()

    async def _phase_1_bootstrap(self) -> None:
        self._current_phase = BootPhase.BOOTSTRAP
        # Configuration is already loaded by the time NovaHost is constructed
        # (main.py); integrity/dependency verification and the security layer are
        # placeholders until nova-auth exists (Roadmap Phase 2/7).
        await self._bus.connect()
        await self._publish_status(ModuleStatus.STARTING, reason="phase 1: bootstrap")

    async def _phase_2_data_engines(self) -> None:
        self._current_phase = BootPhase.DATA_ENGINES
        await self._start_modules_for(BootPhase.DATA_ENGINES)

    async def _phase_3_cognitive_engines(self) -> None:
        self._current_phase = BootPhase.COGNITIVE_ENGINES
        await self._start_modules_for(BootPhase.COGNITIVE_ENGINES)

    async def _phase_4_agents_and_capabilities(self) -> None:
        self._current_phase = BootPhase.AGENTS_AND_CAPABILITIES
        await self._start_modules_for(BootPhase.AGENTS_AND_CAPABILITIES)

    async def _phase_5_health_checks(self) -> None:
        self._current_phase = BootPhase.HEALTH_CHECKS
        for module in self._registry.all_modules():
            healthy = await module.health_check()
            if not healthy:
                await self._publish_status(
                    ModuleStatus.DEGRADED, reason=f"module {module.name!r} failed health check"
                )
                raise BootError(f"Module {module.name!r} failed its health check during boot.")

    async def _phase_6_context_sync(self) -> None:
        self._current_phase = BootPhase.CONTEXT_SYNC
        # Placeholder until the World Model Engine exists to synchronize against
        # (Roadmap Phase 1).

    async def _phase_7_ready(self) -> None:
        self._current_phase = BootPhase.READY
        self._status = ModuleStatus.HEALTHY
        await self._publish_status(ModuleStatus.HEALTHY, reason="phase 7: system ready")

    async def _start_modules_for(self, phase: BootPhase) -> None:
        for module in self._registry.modules_for(phase):
            await module.start()

    async def _publish_status(self, status: ModuleStatus, *, reason: str) -> None:
        previous = self._status
        payload = ModuleStatusChangedPayload(
            module="nova-core", previous_status=previous, status=status, reason=reason
        )
        await self._bus.publish(
            EventEnvelope(
                subject="nova.module.status_changed",
                source_engine="nova-core",
                correlation_id=uuid4(),
                payload=payload.model_dump(mode="json"),
            )
        )
        self._status = status

    def heartbeat_payload(self) -> HeartbeatPayload:
        return HeartbeatPayload(
            module="nova-core",
            status=self._status,
            uptime_seconds=self.uptime_seconds,
            boot_phase=int(self._current_phase) if self._current_phase is not None else None,
        )
