"""Contradiction detection -- docs/design/phase-1/02-knowledge-engine.md §1, §6,
§19. Never auto-resolves beyond structural cases, never deletes either side of a
conflict (§1's "Must never" column) -- `resolve()` only records a human/Reasoning
Engine decision, it never picks a winner itself.
"""

from __future__ import annotations

from nova_knowledge_engine.domain.models import Contradiction, KnowledgeNode
from nova_knowledge_engine.domain.normalization import slugify
from nova_knowledge_engine.domain.ports import KnowledgeMetadataRepository
from nova_knowledge_engine.domain.validation import ValidatedCandidate

MIN_CONFIDENCE_FOR_CONFLICT = 0.4
"""Below this, a candidate is too uncertain to flag a conflict over -- it is
accepted at low confidence instead, matching §17's "contradiction detection
failure falls back to accepting the new node at lower confidence" policy, applied
here as the same policy for low-confidence candidates generally rather than only
on detector failure."""


def _same_slug(node: KnowledgeNode, slug: str) -> bool:
    return slugify(node.name) == slug


async def check_for_conflicts(
    validated: ValidatedCandidate, *, repository: KnowledgeMetadataRepository
) -> Contradiction | None:
    """Same-name (same slug), different-label-or-domain nodes, both above
    `MIN_CONFIDENCE_FOR_CONFLICT`, are flagged as a structural contradiction --
    e.g. two candidates named "Postgres" acquired as a `:Technology` in the
    `programming` domain vs. a `:Company` in the `business` domain. This is a
    structural detector, not semantic/LLM-driven (docs/design/phase-1/
    02-knowledge-engine.md §20 notes deeper, LLM-driven contradiction resolution
    as a Phase 2 extension point that consumes this same typed `Contradiction`
    record) -- property-level contradiction (two candidates disagreeing about a
    fact on the *same* node) is out of scope for Phase 1's structural pass.

    Updating an *existing* node (`validated.existing is not None`, i.e. the
    candidate's own `node_id` already exists) is corroboration, never a conflict
    with itself.
    """
    candidate = validated.candidate
    if validated.existing is not None:
        return None
    if validated.confidence < MIN_CONFIDENCE_FOR_CONFLICT:
        return None

    slug = slugify(candidate.name)
    same_name_nodes = await repository.list_nodes(name_contains=candidate.name, limit=10)
    for other in same_name_nodes:
        if other.node_id == candidate.node_id:
            continue
        if not _same_slug(other, slug):
            continue
        if other.confidence < MIN_CONFIDENCE_FOR_CONFLICT:
            continue
        if other.label != candidate.label or (other.domain or "") != (candidate.domain or ""):
            return Contradiction(
                node_a_id=other.node_id,
                node_b_id=candidate.node_id,
                description=(
                    f"{other.label}:{other.name!r} (domain={other.domain!r}) conflicts "
                    f"with new {candidate.label}:{candidate.name!r} "
                    f"(domain={candidate.domain!r})"
                ),
            )
    return None
