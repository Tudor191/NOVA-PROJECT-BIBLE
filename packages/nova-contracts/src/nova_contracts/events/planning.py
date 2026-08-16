"""Planning Engine shared vocabulary (Bible Part 9), per
docs/design/phase-3/05-tdd-3b-planning-engine.md.

`RiskLevel` lives here, not in `nova_planning_engine.domain.models`, because
it is reused directly by a second engine's own domain model
(`action-engine`'s `ActionObject.risk: RiskLevel`, TDD 3D §2.1/§3.3) --
the identical "simple, structurally-shared enum defined once in
`nova_contracts`, imported by every domain layer that needs it" shape
`ReasoningMode` (`events/reasoning.py`) already establishes, rather than a
second, independently-defined risk scale that TDD 3D would otherwise have to
reinterpret. `TaskNode`/`TaskGraph`/`Estimate` do **not** live here (yet):
no other Phase 3 TDD references them directly (confirmed:
`06-tdd-3c-capability-engine.md` and `07-tdd-3d-action-engine.md` neither
name `TaskNode` nor `TaskGraph`), so they stay engine-local to
`nova_planning_engine.domain.models`, matching every other engine's own
"domain model distinct from any wire payload" convention (e.g.
`reasoning-engine`'s `ReasoningProcess`/`Decision`) until a real
cross-engine or wire-publishing need requires otherwise -- see
`docs/roadmap/architecture-reviews/phase-3b-domain-foundation-gate-review.md`
for the full evidence trail. No event payload is registered in this module
yet (Phase 3B's own event contracts -- `PlanningTaskGraphCreatedPayload`,
`PlanningDecomposeRequestPayload`/`Reply` -- land in the event-consumption
PR that actually publishes/serves them, not this domain-foundation one).
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["RiskLevel"]


class RiskLevel(StrEnum):
    """Bible Part 14's risk classification scale
    (`docs/bible/part-14-autonomy-engine.md:271-279`), reused verbatim --
    the one canonical risk-tier scale anywhere in this project, rather than
    a second, `planning-engine`-specific scale that `action-engine` (TDD 3D)
    would otherwise have to reinterpret or map."""

    NEGLIGIBLE = "negligible"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"
