"""Orchestration: read evidence, derive, persist. The impure half of Phase 4E.

`domain/derivation.py` holds the **rules** and is pure -- source records in,
domain model out, no clock and no I/O. This module holds the **wiring**: it reads
through `DigitalTwinRepository`, calls those rules, and writes the result back.
The split follows `proactive_delivery.py`'s own precedent in this engine, and it
is what keeps every `empty`/`partially_populated`/`unavailable` path drivable in
the unit tier without a database.

**Where a domain's state comes from, by domain.** The nine 4E domains derive from
`domain_evidence` rows this engine accumulated from the three subscribed subjects
(TDD 4E Sec8.1). The two 2D-D domains do not: `Communication Style` and
`Preferences` already have their own tables, and 4E reports their state **from
those tables** rather than restating them as evidence rows. Two sources of truth
for one fact is how they drift.

**Why refresh re-derives from this engine's own rows and not from Memory.**
ADR-004 forbids reading `memory-engine` over HTTP, and the Event Bus is the only
legal channel (TDD 4E Sec0.1.5). So the evidence this engine has accumulated is
the only source it owns, and `POST /domains/{domain}/refresh` recomputes from it.
The disclosed consequence is that memories written before this subscriber existed
produce no evidence and therefore do not appear -- a stream-fed model learns
forward. That is Part 16's *"continuously evolving"* read literally, and it is
stated rather than papered over.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from nova_digital_twin_engine.domain.derivation import DOMAIN_SPECS, derive_domain
from nova_digital_twin_engine.domain.derivation import (
    derive_project_models as _derive_project_models,
)
from nova_digital_twin_engine.domain.models import (
    PART_16_DOMAIN_ORDER,
    DomainEvidence,
    DomainModel,
    DomainReason,
    DomainReasonCode,
    DomainState,
    ProjectModel,
    TwinDomain,
)
from nova_digital_twin_engine.domain.ports import DigitalTwinRepository

__all__ = [
    "derive_all_domains",
    "derive_one_domain",
    "record_evidence",
]


def _now() -> datetime:
    return datetime.now(UTC)


async def _derive_shipped_2dd_domain(
    repository: DigitalTwinRepository, domain: TwinDomain, *, user_id: UUID, now: datetime
) -> DomainModel:
    """`Communication Style` and `Preferences` -- Phase 2D-D's, read not rewritten.

    Their evidence is their own tables. `evidence_count` is a real count from
    those tables rather than a placeholder, so `DomainModel`'s "populated needs
    evidence" invariant means the same thing here as everywhere else.
    """
    if domain is TwinDomain.COMMUNICATION_STYLE:
        profile = await repository.get_communication_profile(user_id)
        # `source == "learned"` is 2D-D's own marker that at least one field has
        # actually been promoted past its static default. A row sitting at its
        # defaults is not evidence of a learned communication style -- reporting
        # it as populated would be the exact claim Part 16 Sec69 forbids.
        learned = profile is not None and profile.source == "learned"
        if not learned:
            return DomainModel(
                user_id=user_id,
                domain=domain,
                state=DomainState.EMPTY,
                reason=DomainReason(
                    code=DomainReasonCode.NO_EVIDENCE_OBSERVED,
                    detail=(
                        "No communication-style field has been promoted past its static "
                        "default yet. Phase 2D-D shipped the mechanism "
                        "(preference_evolution.evolve_field) and the wire path; no "
                        "production call site feeds it an inferred candidate, so the "
                        "profile still reports source='static_default'."
                    ),
                ),
                evidence_count=0,
                derived_at=now,
            )
        assert profile is not None  # `learned` implies it
        return DomainModel(
            user_id=user_id,
            domain=domain,
            state=DomainState.POPULATED,
            evidence_count=1,
            facts={
                "verbosity": profile.verbosity,
                "technical_depth": profile.technical_depth,
                "conversation_pacing": profile.conversation_pacing,
                "habit_timing_hint": profile.habit_timing_hint,
                "source": profile.source,
                "updated_at": profile.updated_at.isoformat(),
            },
            derived_at=now,
        )

    promoted = await repository.count_preference_evolution_entries(user_id)
    if promoted == 0:
        return DomainModel(
            user_id=user_id,
            domain=domain,
            state=DomainState.EMPTY,
            reason=DomainReason(
                code=DomainReasonCode.NO_EVIDENCE_OBSERVED,
                detail=(
                    "No preference has changed yet: preference_evolution_history is "
                    "empty for this user. The history is append-only and records only "
                    "real promotions, never observations, so an empty table means "
                    "nothing has evolved rather than that nothing was observed."
                ),
            ),
            evidence_count=0,
            derived_at=now,
        )
    return DomainModel(
        user_id=user_id,
        domain=domain,
        state=DomainState.POPULATED,
        evidence_count=promoted,
        facts={"promoted_field_changes": promoted},
        derived_at=now,
    )


async def derive_one_domain(
    repository: DigitalTwinRepository,
    domain: TwinDomain,
    *,
    user_id: UUID,
    now: datetime | None = None,
) -> DomainModel:
    """Re-derive one domain and persist it. `POST /domains/{domain}/refresh`.

    Also re-derives the project models when `domain is PROJECTS`: a project row is
    the `projects` domain's detail view, and leaving it stale while its own domain
    model advanced would make the two disagree within one transaction's reach.
    """
    now = now or _now()

    if domain not in DOMAIN_SPECS:
        model = await _derive_shipped_2dd_domain(repository, domain, user_id=user_id, now=now)
        await repository.record_domain_derivation(models=[model])
        return model

    evidence = await repository.list_domain_evidence(user_id, domain)
    model = derive_domain(domain, evidence, user_id=user_id, now=now)
    projects: Sequence[ProjectModel] = (
        _derive_project_models(evidence, user_id=user_id, now=now)
        if domain is TwinDomain.PROJECTS
        else ()
    )
    await repository.record_domain_derivation(models=[model], projects=projects)
    return model


async def derive_all_domains(
    repository: DigitalTwinRepository, *, user_id: UUID, now: datetime | None = None
) -> list[DomainModel]:
    """All eleven, in Part 16's own order, persisted in one transaction.

    Eleven and not nine: `GET /domains` renders Part 16's complete list, so an
    operator sees the whole model rather than the part this milestone happened to
    add. The two 2D-D domains are read from their own tables and left untouched.
    """
    now = now or _now()
    all_evidence = await repository.list_domain_evidence(user_id)
    by_domain: dict[TwinDomain, list[DomainEvidence]] = {}
    for row in all_evidence:
        by_domain.setdefault(row.domain, []).append(row)

    models: list[DomainModel] = []
    for domain in PART_16_DOMAIN_ORDER:
        if domain in DOMAIN_SPECS:
            models.append(
                derive_domain(domain, by_domain.get(domain, []), user_id=user_id, now=now)
            )
        else:
            models.append(
                await _derive_shipped_2dd_domain(repository, domain, user_id=user_id, now=now)
            )

    projects = _derive_project_models(
        by_domain.get(TwinDomain.PROJECTS, []), user_id=user_id, now=now
    )
    await repository.record_domain_derivation(models=models, projects=projects)
    return models


async def record_evidence(
    repository: DigitalTwinRepository,
    evidence: Sequence[DomainEvidence],
    *,
    user_id: UUID,
    now: datetime | None = None,
) -> None:
    """The subscriber path: fold new evidence in and re-derive what it touches.

    Only the domains the new rows actually affect are re-derived, plus their
    persisted evidence -- an attention observation does not restate the Projects
    model. The whole thing lands in **one** `record_domain_derivation` call so a
    domain's state and the evidence justifying it are never separately committed.

    A no-op for empty `evidence`, which is what a `CONFIDENTIAL` or
    `HIGHLY_SENSITIVE` memory produces (`domain/derivation.py`'s allow-list):
    nothing is recorded, nothing is re-derived, and no domain moves.
    """
    if not evidence:
        return
    now = now or _now()

    touched = {row.domain for row in evidence}
    existing: dict[TwinDomain, list[DomainEvidence]] = {}
    for domain in touched:
        existing[domain] = list(await repository.list_domain_evidence(user_id, domain))

    # Fold the new rows in by the same key the table uses, so a redelivered event
    # re-derives to the identical model rather than to a larger count.
    for row in evidence:
        rows = existing[row.domain]
        rows = [r for r in rows if r.source_record_id != row.source_record_id]
        rows.append(row)
        existing[row.domain] = rows

    models = [
        derive_domain(domain, rows, user_id=user_id, now=now)
        for domain, rows in existing.items()
    ]
    projects: Sequence[ProjectModel] = (
        _derive_project_models(existing[TwinDomain.PROJECTS], user_id=user_id, now=now)
        if TwinDomain.PROJECTS in existing
        else ()
    )
    await repository.record_domain_derivation(
        models=models, evidence=evidence, projects=projects
    )
