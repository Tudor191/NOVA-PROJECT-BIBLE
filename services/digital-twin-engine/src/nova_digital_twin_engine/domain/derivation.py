"""Turning evidence into Bible Part 16 domain models -- pure, and deliberately so.

Every function here takes evidence rows and returns a model. No I/O, no clock of
its own (`now` is always a parameter), no repository, no bus. That is what lets
TDD 4E Sec14.1's unit tier drive every `empty`/`partially_populated`/`unavailable`
path directly, and it is why the one rule this milestone cannot break --
Part 16 Sec69's *"Never create assumptions without evidence"* -- is checkable by
reading one file.

**What "derive" means here, and what it does not.** A domain's state describes how
completely it was derived *from the evidence that exists*, never how completely it
fills Part 16's aspirational field list. Part 16's Goal Model names priority,
progress, dependencies and estimated completion; nothing in this repository
produces any of them. A domain therefore reports `populated` when it derived
everything its evidence supports, and names the Part 16 fields it could not reach
in `unavailable_fields` -- which the panel renders. Rounding that down to
`partially_populated` for every domain would make the state carry no information
at all; rounding it up while silently dropping the gap would be the assumption
Part 16 forbids.

**Privacy (TDD 4E Sec0.1.6, ratified Sec19.3).** `PrivacyLevel` has no `PRIVATE`
member -- it is `PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `HIGHLY_SENSITIVE`. The
ratified intent is implemented as a **fail-closed allow-list**: only `PUBLIC` and
`INTERNAL` contribute. A level added in a later phase is excluded by default
rather than silently admitted, which is the opposite of what a deny-list would do.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from nova_contracts import PrivacyLevel

from nova_digital_twin_engine.domain.models import (
    DomainEvidence,
    DomainModel,
    DomainReason,
    DomainReasonCode,
    DomainState,
    EvidenceKind,
    ProjectModel,
    TwinDomain,
)

__all__ = [
    "CONTRIBUTING_PRIVACY_LEVELS",
    "DOMAIN_SPECS",
    "DomainSpec",
    "derive_domain",
    "derive_project_models",
    "evidence_from_attention_observed",
    "evidence_from_decision_recorded",
    "evidence_from_memory_created",
]


CONTRIBUTING_PRIVACY_LEVELS: frozenset[PrivacyLevel] = frozenset(
    {PrivacyLevel.PUBLIC, PrivacyLevel.INTERNAL}
)
"""The allow-list, stated once. `CONFIDENTIAL` and `HIGHLY_SENSITIVE` never reach
a derived domain (ratified Sec19.3, read per Sec0.1.6)."""


class DomainSpec:
    """One domain's binding derivation rule.

    A table rather than nine bespoke functions, because the interesting property
    is the *comparison* between domains: which evidence each consumes, how high a
    state each may claim, and what it says when it has nothing. Spreading that
    across nine functions is how one of them quietly acquires a default.
    """

    __slots__ = ("domain", "kinds", "max_state", "no_evidence_reason", "unavailable_fields")

    def __init__(
        self,
        domain: TwinDomain,
        *,
        kinds: frozenset[EvidenceKind],
        max_state: DomainState,
        no_evidence_reason: DomainReason,
        unavailable_fields: Sequence[str] = (),
    ) -> None:
        self.domain = domain
        self.kinds = kinds
        self.max_state = max_state
        self.no_evidence_reason = no_evidence_reason
        self.unavailable_fields = tuple(unavailable_fields)


_MEMORY = frozenset({EvidenceKind.MEMORY_LONG_TERM_CREATED})
_DECISION = frozenset({EvidenceKind.MEMORY_DECISION_RECORDED})
_ATTENTION = frozenset({EvidenceKind.PERCEPTION_ATTENTION_OBSERVED})
_NOTHING: frozenset[EvidenceKind] = frozenset()


DOMAIN_SPECS: dict[TwinDomain, DomainSpec] = {
    TwinDomain.PERSONAL_WORKFLOW: DomainSpec(
        TwinDomain.PERSONAL_WORKFLOW,
        kinds=_MEMORY,
        max_state=DomainState.POPULATED,
        no_evidence_reason=DomainReason(
            code=DomainReasonCode.NO_EVIDENCE_OBSERVED,
            detail=(
                "No episodic or procedural memory has been recorded for this user yet. "
                "Personal Workflow is derived from memory.long_term.created; one memory "
                "starts populating it."
            ),
        ),
        unavailable_fields=(
            "application_launch_sequences",
            "repository_and_tool_invocations",
        ),
    ),
    TwinDomain.PROJECTS: DomainSpec(
        TwinDomain.PROJECTS,
        kinds=_MEMORY,
        max_state=DomainState.POPULATED,
        no_evidence_reason=DomainReason(
            code=DomainReasonCode.NO_EVIDENCE_OBSERVED,
            detail=(
                "No memory carrying a project_id has been recorded for this user yet. "
                "MemoryRecord.project_id is the only project identity in the system."
            ),
        ),
        unavailable_fields=(
            "architecture",
            "milestones",
            "files",
            "repositories",
            "dependencies",
            "agents_involved",
            "known_issues",
            "future_roadmap",
        ),
    ),
    TwinDomain.SOFTWARE_ENVIRONMENT: DomainSpec(
        TwinDomain.SOFTWARE_ENVIRONMENT,
        kinds=_NOTHING,
        max_state=DomainState.EMPTY,
        no_evidence_reason=DomainReason(
            code=DomainReasonCode.NO_SOURCE_ENGINE,
            detail=(
                "No engine in this release reports installed applications, development "
                "tools, package managers or runtimes. The populator is Phase 4F's "
                "nova-companion, which does not exist yet."
            ),
        ),
        unavailable_fields=(
            "installed_applications",
            "development_tools",
            "package_managers",
            "cloud_platforms",
            "containers",
            "virtual_machines",
            "local_ai_models",
            "automation_software",
            "version_control_systems",
        ),
    ),
    TwinDomain.HARDWARE_ENVIRONMENT: DomainSpec(
        TwinDomain.HARDWARE_ENVIRONMENT,
        kinds=_NOTHING,
        max_state=DomainState.EMPTY,
        no_evidence_reason=DomainReason(
            code=DomainReasonCode.NO_SOURCE_ENGINE,
            detail=(
                "No engine in this release reports CPU, GPU, memory, storage, displays "
                "or peripherals. The populator is Phase 4F's nova-companion, which does "
                "not exist yet."
            ),
        ),
        unavailable_fields=(
            "cpu",
            "gpu",
            "ram",
            "storage",
            "displays",
            "audio_devices",
            "peripherals",
            "network",
            "battery",
            "temperature_sensors",
            "connected_devices",
        ),
    ),
    TwinDomain.KNOWLEDGE_PROFILE: DomainSpec(
        TwinDomain.KNOWLEDGE_PROFILE,
        kinds=_MEMORY,
        max_state=DomainState.PARTIALLY_POPULATED,
        no_evidence_reason=DomainReason(
            code=DomainReasonCode.NO_EVIDENCE_OBSERVED,
            detail=(
                "No memory carrying a knowledge_node_id has been recorded for this user "
                "yet. Familiarity is counted per knowledge node; nothing else about a "
                "concept is inferable from the subscribed payloads."
            ),
        ),
        unavailable_fields=(
            "known_versus_learning_versus_unknown_classification",
            "areas_requiring_improvement",
            "teaching_strategy",
        ),
    ),
    TwinDomain.SKILL_PROFILE: DomainSpec(
        TwinDomain.SKILL_PROFILE,
        kinds=_MEMORY,
        max_state=DomainState.PARTIALLY_POPULATED,
        no_evidence_reason=DomainReason(
            code=DomainReasonCode.NO_EVIDENCE_OBSERVED,
            detail=(
                "No procedural memory has been recorded for this user yet. Procedural "
                "density is the only skill signal available; naming the skill itself "
                "would require classifying memory content, which this engine never sees."
            ),
        ),
        unavailable_fields=(
            "named_skills",
            "ability_estimate_per_skill",
            "estimate_confidence",
            "learning_recommendations",
        ),
    ),
    TwinDomain.PRODUCTIVITY_PATTERNS: DomainSpec(
        TwinDomain.PRODUCTIVITY_PATTERNS,
        kinds=_ATTENTION,
        max_state=DomainState.POPULATED,
        no_evidence_reason=DomainReason(
            code=DomainReasonCode.NO_AUTONOMOUS_PRODUCER,
            detail=(
                "perception.attention.observed is real, published and consumed, but "
                "nothing in a stock deployment emits it: the only ingress is "
                "POST /v1/perception/observations, and nova-companion is Phase 4F's. "
                "One posted observation starts populating this domain."
            ),
        ),
        unavailable_fields=(
            "average_coding_session",
            "preferred_break_intervals",
            "task_completion_speed",
            "context_switching_frequency",
            "planning_accuracy",
        ),
    ),
    TwinDomain.GOALS: DomainSpec(
        TwinDomain.GOALS,
        kinds=_DECISION,
        max_state=DomainState.POPULATED,
        no_evidence_reason=DomainReason(
            code=DomainReasonCode.NO_EVIDENCE_OBSERVED,
            detail=(
                "No decision has been recorded for this user yet. Goals are derived from "
                "memory.decision.recorded; one recorded decision starts populating it."
            ),
        ),
        unavailable_fields=(
            "priority",
            "progress",
            "dependencies",
            "estimated_completion",
            "knowledge_requirements",
        ),
    ),
    TwinDomain.LEARNING_PROGRESS: DomainSpec(
        TwinDomain.LEARNING_PROGRESS,
        kinds=_MEMORY,
        max_state=DomainState.POPULATED,
        no_evidence_reason=DomainReason(
            code=DomainReasonCode.NO_EVIDENCE_OBSERVED,
            detail=(
                "No semantic or procedural memory has been recorded for this user yet. "
                "Learning Progress counts them over time; one memory starts populating it."
            ),
        ),
        unavailable_fields=("mastery_level_per_concept", "retention_estimates"),
    ),
}
"""The nine 4E domains. `Communication Style` and `Preferences` are absent because
2D-D derives them from its own tables, not from evidence rows -- see
`api/digital_twin.py`, which reports their state from those tables and leaves both
untouched."""


# ---------------------------------------------------------------------------
# Event payload -> evidence rows
# ---------------------------------------------------------------------------


def evidence_from_memory_created(
    *,
    user_id: UUID,
    memory_id: UUID,
    memory_type: str,
    privacy_level: PrivacyLevel,
    project_id: UUID | None,
    knowledge_node_id: str | None,
    source_created_at: datetime | None,
    observed_at: datetime,
) -> list[DomainEvidence]:
    """Which domains one `memory.long_term.created` event contributes to.

    Returns **an empty list** for a memory the privacy allow-list excludes -- not a
    filtered row, not a redacted one. The evidence simply never exists, which is
    what makes the negative control (TDD 4E Sec14.5 control 6) provable at every
    layer above rather than only at the rendering edge.
    """
    if privacy_level not in CONTRIBUTING_PRIVACY_LEVELS:
        return []

    def _row(domain: TwinDomain, **attributes: Any) -> DomainEvidence:
        return DomainEvidence(
            user_id=user_id,
            domain=domain,
            kind=EvidenceKind.MEMORY_LONG_TERM_CREATED,
            source_record_id=memory_id,
            source_created_at=source_created_at,
            observed_at=observed_at,
            attributes={"memory_type": memory_type, **attributes},
        )

    rows: list[DomainEvidence] = []

    if memory_type in ("episodic", "procedural"):
        rows.append(_row(TwinDomain.PERSONAL_WORKFLOW))
    if project_id is not None:
        rows.append(_row(TwinDomain.PROJECTS, project_id=str(project_id)))
    if knowledge_node_id is not None:
        rows.append(_row(TwinDomain.KNOWLEDGE_PROFILE, knowledge_node_id=knowledge_node_id))
    if memory_type == "procedural":
        rows.append(_row(TwinDomain.SKILL_PROFILE))
    if memory_type in ("semantic", "procedural"):
        rows.append(_row(TwinDomain.LEARNING_PROGRESS))
    return rows


def evidence_from_decision_recorded(
    *,
    user_id: UUID,
    decision_id: UUID,
    confidence_at_decision: float | None,
    source_created_at: datetime | None,
    observed_at: datetime,
) -> list[DomainEvidence]:
    """`memory.decision.recorded` -> the Goals domain.

    **`objective` and `chosen_alternative` are deliberately not carried.**
    `DecisionRecordedPayload` has no `privacy_level`, so this engine cannot tell
    whether the memory behind a decision was one the allow-list would exclude.
    Storing free text it cannot privacy-check would be exactly the leak Sec19.3
    forbids, so Goals is derived from counts and confidences alone and says so in
    `unavailable_fields`.
    """
    return [
        DomainEvidence(
            user_id=user_id,
            domain=TwinDomain.GOALS,
            kind=EvidenceKind.MEMORY_DECISION_RECORDED,
            source_record_id=decision_id,
            source_created_at=source_created_at,
            observed_at=observed_at,
            attributes=(
                {} if confidence_at_decision is None else {"confidence": confidence_at_decision}
            ),
        )
    ]


def evidence_from_attention_observed(
    *,
    user_id: UUID,
    observation_id: UUID,
    attention_state: str,
    gaze_direction: str,
    confidence: float,
    observed_at: datetime,
) -> list[DomainEvidence]:
    """`perception.attention.observed` -> Productivity Patterns.

    `source_created_at` is `observed_at`: unlike a memory, an attention
    observation has no separate creation timestamp on the wire, and the moment it
    was observed *is* the moment it describes. Inventing a different value would
    be the fabrication this engine exists to avoid.

    `user_id` is supplied by the caller, not the payload:
    `PerceptionAttentionObservedPayload` carries only a nullable `identity_id`.
    Under ADR-025 there is exactly one trusted user per instance, so the handler
    attributes it to the configured one -- see `events/handlers.py`.
    """
    return [
        DomainEvidence(
            user_id=user_id,
            domain=TwinDomain.PRODUCTIVITY_PATTERNS,
            kind=EvidenceKind.PERCEPTION_ATTENTION_OBSERVED,
            source_record_id=observation_id,
            source_created_at=observed_at,
            observed_at=observed_at,
            attributes={
                "attention_state": attention_state,
                "gaze_direction": gaze_direction,
                "confidence": confidence,
            },
        )
    ]


# ---------------------------------------------------------------------------
# Evidence rows -> domain models
# ---------------------------------------------------------------------------


def derive_domain(
    domain: TwinDomain,
    evidence: Sequence[DomainEvidence],
    *,
    user_id: UUID,
    now: datetime,
) -> DomainModel:
    """One domain's current state, derived from its own evidence rows and nothing
    else.

    `evidence` is already scoped to this domain and user by the caller. A domain
    with no rows returns its spec's own `no_evidence_reason` -- never a zero,
    never an average over an empty set, never a default.
    """
    spec = DOMAIN_SPECS[domain]

    if not evidence:
        return DomainModel(
            user_id=user_id,
            domain=domain,
            state=DomainState.EMPTY,
            reason=spec.no_evidence_reason,
            evidence_count=0,
            # Reported even when empty: a domain with no source should still say
            # what it *would* hold, so an operator reading `Hardware Environment`
            # sees the eleven Part 16 fields awaiting 4F rather than a blank card
            # that could equally mean "nothing to show" or "not implemented".
            unavailable_fields=list(spec.unavailable_fields),
            derived_at=now,
        )

    facts = _facts_for(domain, evidence)
    timestamps = [e.source_created_at for e in evidence if e.source_created_at is not None]
    if timestamps:
        facts["first_evidence_at"] = min(timestamps).isoformat()
        facts["last_evidence_at"] = max(timestamps).isoformat()
    else:
        facts["timestamped_evidence_count"] = 0

    state = spec.max_state
    reason: DomainReason | None = None
    if state is DomainState.PARTIALLY_POPULATED:
        reason = DomainReason(
            code=DomainReasonCode.EVIDENCE_PARTIAL,
            detail=(
                f"Derived from {len(evidence)} real evidence row(s). The Part 16 fields "
                f"named in unavailable_fields have no source in this release."
            ),
        )
    elif not timestamps:
        # Evidence arrived, but none of it could be placed in time. Reported, not
        # backfilled from the clock (TDD 4E Sec0.1.5).
        state = DomainState.PARTIALLY_POPULATED
        reason = DomainReason(
            code=DomainReasonCode.SOURCE_TIMESTAMP_MISSING,
            detail=(
                f"All {len(evidence)} evidence row(s) arrived without the source "
                "record's own created_at, so nothing here can be placed on a timeline."
            ),
        )

    return DomainModel(
        user_id=user_id,
        domain=domain,
        state=state,
        reason=reason,
        evidence_count=len(evidence),
        facts=facts,
        unavailable_fields=list(spec.unavailable_fields),
        derived_at=now,
    )


def _facts_for(domain: TwinDomain, evidence: Sequence[DomainEvidence]) -> dict[str, Any]:
    """What each domain actually derives. Counts and identifiers only -- there is
    no memory content in any subscribed payload, and none is synthesised here."""
    if domain is TwinDomain.PROJECTS:
        project_ids = {
            e.attributes["project_id"] for e in evidence if "project_id" in e.attributes
        }
        return {"project_count": len(project_ids), "memory_count": len(evidence)}

    if domain is TwinDomain.KNOWLEDGE_PROFILE:
        nodes = Counter(
            str(e.attributes["knowledge_node_id"])
            for e in evidence
            if "knowledge_node_id" in e.attributes
        )
        return {
            "known_node_count": len(nodes),
            "observations_per_node": dict(nodes.most_common(20)),
        }

    if domain is TwinDomain.GOALS:
        confidences = [
            float(e.attributes["confidence"]) for e in evidence if "confidence" in e.attributes
        ]
        return {
            "decision_count": len(evidence),
            # `None`, never 0.0: no decision carried a confidence is a different
            # claim from every decision being made with no confidence at all.
            "mean_confidence_at_decision": (
                sum(confidences) / len(confidences) if confidences else None
            ),
        }

    if domain is TwinDomain.PRODUCTIVITY_PATTERNS:
        states = Counter(str(e.attributes.get("attention_state", "unknown")) for e in evidence)
        return {"observation_count": len(evidence), "attention_state_counts": dict(states)}

    # Personal Workflow, Skill Profile, Learning Progress: memory-type density.
    types = Counter(str(e.attributes.get("memory_type", "unknown")) for e in evidence)
    return {"observation_count": len(evidence), "memory_type_counts": dict(types)}


def derive_project_models(
    evidence: Iterable[DomainEvidence], *, user_id: UUID, now: datetime
) -> list[ProjectModel]:
    """Bible Part 16's Project Model, one per `project_id` seen -- **AC-6's
    reconstruction**.

    `gap_days` is measured from the newest persisted `source_created_at` to `now`.
    That is the whole of the "simulated multi-week gap": the timestamps are real
    column values written weeks in the past, so the gap is a subtraction rather
    than a simulation. Nothing here reads the system clock except through `now`,
    which the caller supplies.

    Ordered most-recently-active first, with projects that have no timestamped
    evidence last -- an unplaceable project is not a *stale* one, and sorting it
    among the stale ones would assert something the evidence does not support.
    """
    by_project: dict[str, list[DomainEvidence]] = {}
    for row in evidence:
        project_id = row.attributes.get("project_id")
        if project_id is None:
            continue
        by_project.setdefault(str(project_id), []).append(row)

    models: list[ProjectModel] = []
    for project_id, rows in by_project.items():
        timestamps = [r.source_created_at for r in rows if r.source_created_at is not None]
        first = min(timestamps) if timestamps else None
        last = max(timestamps) if timestamps else None
        models.append(
            ProjectModel(
                user_id=user_id,
                project_id=UUID(project_id),
                memory_count=len(rows),
                memory_type_counts=dict(
                    Counter(str(r.attributes.get("memory_type", "unknown")) for r in rows)
                ),
                first_activity_at=first,
                last_activity_at=last,
                gap_days=(
                    max((now - last).total_seconds() / 86400.0, 0.0) if last is not None else None
                ),
                derived_at=now,
            )
        )

    models.sort(
        key=lambda m: (m.last_activity_at is not None, m.last_activity_at or now), reverse=True
    )
    return models
