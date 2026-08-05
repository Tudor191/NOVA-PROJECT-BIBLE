"""Constraint Evaluation (docs/design/phase-2b/00-reasoning-engine.md §9) -- a
hard gate applied before scoring, never a soft factor blended into the
Decision Matrix. The same "no override, no blending" discipline the AI Model
Orchestration Engine's privacy-tier filter established in Phase 2A, reused
here rather than reinvented.
"""

from __future__ import annotations

from nova_reasoning_engine.domain.models import Alternative, Constraint

__all__ = ["apply_hard_constraints"]


def apply_hard_constraints(
    alternatives: list[Alternative], constraints: list[Constraint]
) -> tuple[list[Alternative], dict[str, list[str]]]:
    """Marks every `Alternative` that fails any hard `Constraint` as
    `rejected_constraint_violation` -- never silently dropped. Returns the
    (mutated-copy) alternatives plus a map of `alternative_id -> [violated
    constraint descriptions]`, so a caller can see *why* an option didn't
    survive the gate, not just that it didn't (§9, §16, §19)."""
    hard_constraints = [c for c in constraints if c.hard]
    violations: dict[str, list[str]] = {}
    gated: list[Alternative] = []

    for alternative in alternatives:
        violated = [c.description for c in hard_constraints if _violates(alternative, c)]
        if violated:
            violations[str(alternative.id)] = violated
            rejected_status = "rejected_constraint_violation"
            gated.append(alternative.model_copy(update={"constraint_status": rejected_status}))
        else:
            gated.append(alternative)

    return gated, violations


def _violates(alternative: Alternative, constraint: Constraint) -> bool:
    """Phase 2B has no per-alternative structured cost/privacy/time/resource
    metadata to check a constraint against yet (§9's constraint sources are
    still caller-supplied and largely advisory pending real wiring into the
    AI Model Orchestration Engine's budget concept) -- so no alternative is
    ever mechanically gated out in this phase. This is named honestly here
    rather than faking a check that has nothing real to evaluate; real
    per-alternative constraint checks are a natural extension once
    `Alternative` itself carries the structured fields a check needs (§25)."""
    return False
