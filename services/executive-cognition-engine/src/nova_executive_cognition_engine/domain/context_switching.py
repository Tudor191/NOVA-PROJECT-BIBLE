"""Context switching (docs/design/phase-2c/00-executive-cognition-engine.md
§11) -- evaluated before recommending that an already-in-flight,
lower-priority request be interrupted rather than merely queued (`WAIT`,
§7). "Switching attention has a cost... switch only when justified" (Bible
Part 19). No real caller supplies `current_progress` yet (§11's own honest
scope note) -- specified in full now so it has real effect the moment one
does.
"""

from __future__ import annotations

from nova_executive_cognition_engine.domain.models import ContextSwitchEvaluation

__all__ = ["DEFAULT_SWITCH_MARGIN", "evaluate_context_switch"]

DEFAULT_SWITCH_MARGIN = 0.0
"""§11: a `Settings`-tunable margin -- `potential_benefit` must exceed
`recovery_cost + interruption_impact` by at least this much before a switch
is recommended. `0.0` means "any net positive benefit is enough"; raising it
makes switching a deliberately higher bar to clear."""


def evaluate_context_switch(
    *,
    current_progress: float,
    recovery_cost: float,
    interruption_impact: float,
    potential_benefit: float,
    margin: float = DEFAULT_SWITCH_MARGIN,
) -> ContextSwitchEvaluation:
    """§11's formula: `potential_benefit > (recovery_cost + interruption_impact)
    + margin`. `current_progress` is recorded on the evaluation for
    explainability (§16) but is not itself a term in the formula -- a
    request that is 90% complete and one that is 10% complete carry the
    same `recovery_cost`/`interruption_impact` signals unless the caller's
    own estimate of those two already reflects progress, which this
    function trusts rather than re-derives (ADR-028)."""
    switch_recommended = potential_benefit > (recovery_cost + interruption_impact) + margin
    return ContextSwitchEvaluation(
        current_progress=current_progress,
        recovery_cost=recovery_cost,
        interruption_impact=interruption_impact,
        potential_benefit=potential_benefit,
        switch_recommended=switch_recommended,
    )
