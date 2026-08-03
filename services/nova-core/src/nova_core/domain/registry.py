"""The Module Registry: nova-core's record of which engines exist, and which boot
phase each belongs to (Bible Part 20, "Service Registry" / "Module Lifecycle").

In Phase 0, no engines are registered -- `NovaHost` boots through phases 2-4 against
an empty registry, proving the orchestration skeleton before any real intelligence is
built on top of it (docs/roadmap/ENGINEERING_ROADMAP.md, Phase 0). Starting in Phase 1
of the roadmap, engines running in `embedded` mode register themselves here at
process startup; in `standalone` mode this same registry instead tracks liveness
reported over the Event Bus (docs/architecture/03-backend-architecture.md §2).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import IntEnum


class BootPhase(IntEnum):
    """Mirrors Part 20's System Boot Sequence phases 1-7 verbatim."""

    BOOTSTRAP = 1
    DATA_ENGINES = 2
    COGNITIVE_ENGINES = 3
    AGENTS_AND_CAPABILITIES = 4
    HEALTH_CHECKS = 5
    CONTEXT_SYNC = 6
    READY = 7


@dataclass(frozen=True)
class ModuleDescriptor:
    """A module (engine) nova-core knows how to start and health-check."""

    name: str
    phase: BootPhase
    start: Callable[[], Awaitable[None]]
    health_check: Callable[[], Awaitable[bool]]


class ModuleRegistry:
    """In-process record of registered modules, grouped by the boot phase they start in."""

    def __init__(self) -> None:
        self._by_phase: dict[BootPhase, list[ModuleDescriptor]] = defaultdict(list)

    def register(self, descriptor: ModuleDescriptor) -> None:
        existing_names = {m.name for m in self._by_phase[descriptor.phase]}
        if descriptor.name in existing_names:
            raise ValueError(f"Module {descriptor.name!r} is already registered.")
        self._by_phase[descriptor.phase].append(descriptor)

    def modules_for(self, phase: BootPhase) -> list[ModuleDescriptor]:
        return list(self._by_phase[phase])

    def all_modules(self) -> list[ModuleDescriptor]:
        return [module for modules in self._by_phase.values() for module in modules]
