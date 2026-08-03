"""The Heartbeat System (Bible Part 20): nova-core periodically publishes its own
liveness, and (starting in Roadmap Phase 1+) will aggregate every other module's
heartbeat into the overall system Health Index this class's docstring promises.

Every beat is recorded twice, for two different audiences: as a `nova.heartbeat`
Event Bus message (for other engines / the future Command Center UI) and as
Prometheus metrics (for the Grafana heartbeat dashboard,
infra/observability/grafana/dashboards/nova-core-heartbeat.json) -- the same
observable fact, exposed through both of NOVA's two observability channels
(docs/architecture/09 vs. docs/architecture/11 §3).
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Iterable
from uuid import uuid4

from nova_contracts import EventEnvelope
from nova_eventbus_sdk.interface import EventBus
from nova_observability import get_meter
from opentelemetry.metrics import CallbackOptions, Observation

from nova_core.domain.boot import NovaHost


class HeartbeatPublisher:
    """Publishes `nova.heartbeat` on a fixed interval for as long as it is running."""

    def __init__(self, *, event_bus: EventBus, host: NovaHost, interval_s: float = 5.0) -> None:
        self._bus = event_bus
        self._host = host
        self._interval_s = interval_s
        self._task: asyncio.Task[None] | None = None

        meter = get_meter("nova_core.heartbeat")
        self._heartbeat_counter = meter.create_counter(
            "nova_core_heartbeat_total", description="Number of heartbeats published by nova-core."
        )
        meter.create_observable_gauge(
            "nova_core_uptime_seconds",
            callbacks=[self._observe_uptime],
            description="Seconds since nova-core completed its boot sequence.",
        )

    def _observe_uptime(self, _options: CallbackOptions) -> Iterable[Observation]:
        yield Observation(self._host.uptime_seconds, {"module": "nova-core"})

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop(), name="nova-core-heartbeat")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def beat_once(self) -> None:
        """Publish a single heartbeat immediately (used by `start()`'s loop and by tests)."""
        payload = self._host.heartbeat_payload()
        await self._bus.publish(
            EventEnvelope(
                subject="nova.heartbeat",
                source_engine="nova-core",
                correlation_id=uuid4(),
                payload=payload.model_dump(mode="json"),
            )
        )
        self._heartbeat_counter.add(1, {"module": "nova-core", "status": payload.status.value})

    async def _loop(self) -> None:
        while True:
            await self.beat_once()
            await asyncio.sleep(self._interval_s)
