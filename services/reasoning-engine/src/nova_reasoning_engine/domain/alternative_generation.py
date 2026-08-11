"""Alternative Solution Generation (docs/design/phase-2b/00-reasoning-engine.md
§14) -- Bible Part 8: "For every important problem, produce at least three
approaches... never become attached to the first idea."

Converts every `Hypothesis` with `status == "supported"` (§13) into a
concrete `Alternative`. When fewer than the minimum survive evidence
collection, requests additional hypotheses from §12 up to a bounded retry
count -- never an unbounded loop -- before proceeding with fewer than the
minimum, which is recorded as a named, visible condition
(`alternatives_below_minimum`), never silently accepted as if the minimum
had been met.
"""

from __future__ import annotations

from uuid import UUID

from nova_contracts import PrivacyLevel

from nova_reasoning_engine.domain.evidence_collection import collect_evidence
from nova_reasoning_engine.domain.hypothesis_generation import (
    HypothesisGenerationError,
    generate_hypotheses,
)
from nova_reasoning_engine.domain.models import (
    Alternative,
    ContextBundle,
    Evidence,
    Hypothesis,
    HypothesisGenerationRequest,
)
from nova_reasoning_engine.domain.ports import ModelOrchestrationPort

__all__ = ["MAX_HYPOTHESIS_RETRIES", "generate_alternatives"]

MAX_HYPOTHESIS_RETRIES = 1
"""A bounded retry walk (§14, §22) -- one additional hypothesis-generation
call at most, never an unbounded loop chasing the minimum."""


async def generate_alternatives(
    hypotheses: list[Hypothesis],
    evidence: list[Evidence],
    context: ContextBundle,
    *,
    reasoning_process_id: UUID,
    objective: str,
    minimum: int,
    model_port: ModelOrchestrationPort,
    requesting_engine: str,
    correlation_id: UUID,
    thinking_mode_hint: str | None = None,
    privacy_hint: PrivacyLevel = PrivacyLevel.INTERNAL,
) -> tuple[list[Alternative], list[Hypothesis], list[Evidence], bool]:
    """Returns `(alternatives, all_hypotheses_seen, all_evidence_seen,
    alternatives_below_minimum)` -- the latter three feed the reasoning trace
    (§19) so a caller can see the full hypothesis/evidence history, not just
    the winning alternatives."""
    supported = [h for h in hypotheses if h.status == "supported"]
    all_hypotheses = list(hypotheses)
    all_evidence = list(evidence)

    retries = 0
    while len(supported) < minimum and retries < MAX_HYPOTHESIS_RETRIES:
        retries += 1
        try:
            new_hypotheses, _model_used, _is_correction = await generate_hypotheses(
                HypothesisGenerationRequest(
                    objective=objective,
                    context=context,
                    minimum_hypotheses=minimum,
                    thinking_mode_hint=thinking_mode_hint,
                ),
                reasoning_process_id=reasoning_process_id,
                model_port=model_port,
                requesting_engine=requesting_engine,
                correlation_id=correlation_id,
                privacy_hint=privacy_hint,
            )
        except HypothesisGenerationError:
            break

        verified, new_evidence = collect_evidence(new_hypotheses, context)
        all_hypotheses.extend(verified)
        all_evidence.extend(new_evidence)
        supported.extend(h for h in verified if h.status == "supported")

    alternatives_below_minimum = len(supported) < minimum

    alternatives = [
        Alternative(
            reasoning_process_id=reasoning_process_id,
            hypothesis_id=h.id,
            description=h.description,
            supporting_evidence_ids=[e.id for e in all_evidence if e.hypothesis_id == h.id],
        )
        for h in supported
    ]
    return alternatives, all_hypotheses, all_evidence, alternatives_below_minimum
