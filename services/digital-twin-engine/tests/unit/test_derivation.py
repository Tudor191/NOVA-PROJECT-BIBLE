"""Bible Part 16 domain derivation -- the pure rules (TDD 4E Sec14.1).

`domain/derivation.py` takes evidence and returns models, with `now` as a
parameter and no I/O, so every state this milestone can report is drivable here
without a database, a bus, or a clock. The four states (Sec12), the ratified
per-domain floor (Sec19.1), the privacy allow-list (Sec19.3 read per Sec0.1.6)
and AC-6's gap arithmetic are all decided in this module, so this is where they
are asserted.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from nova_contracts import PrivacyLevel
from nova_digital_twin_engine.domain.derivation import (
    CONTRIBUTING_PRIVACY_LEVELS,
    DOMAIN_SPECS,
    derive_domain,
    derive_project_models,
    evidence_from_attention_observed,
    evidence_from_decision_recorded,
    evidence_from_memory_created,
)
from nova_digital_twin_engine.domain.models import (
    PART_16_DOMAIN_ORDER,
    PHASE_4E_DOMAINS,
    SHIPPED_2DD_DOMAINS,
    DomainEvidence,
    DomainReasonCode,
    DomainState,
    EvidenceKind,
    TwinDomain,
)

NOW = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
USER = uuid4()


def _memory_evidence(
    domain: TwinDomain,
    *,
    age_days: float | None = 1.0,
    memory_type: str = "episodic",
    **attributes: object,
) -> DomainEvidence:
    return DomainEvidence(
        user_id=USER,
        domain=domain,
        kind=EvidenceKind.MEMORY_LONG_TERM_CREATED,
        source_record_id=uuid4(),
        source_created_at=None if age_days is None else NOW - timedelta(days=age_days),
        observed_at=NOW,
        attributes={"memory_type": memory_type, **attributes},
    )


# --- Part 16's own vocabulary ----------------------------------------------


def test_the_eleven_domains_are_part_16s_own_list() -> None:
    """Part 16 Secs71-95, verbatim and in order. Asserted as a literal rather than
    derived from the enum: the point is that the enum matches the Bible, and
    checking the enum against itself would prove nothing."""
    assert [d.value for d in PART_16_DOMAIN_ORDER] == [
        "personal_workflow",
        "projects",
        "software_environment",
        "hardware_environment",
        "knowledge_profile",
        "skill_profile",
        "communication_style",
        "productivity_patterns",
        "goals",
        "preferences",
        "learning_progress",
    ]


def test_the_arithmetic_closes_at_eleven_minus_two_equals_nine() -> None:
    assert len(PART_16_DOMAIN_ORDER) == 11
    assert len(SHIPPED_2DD_DOMAINS) == 2
    assert len(PHASE_4E_DOMAINS) == 9
    assert set(DOMAIN_SPECS) == PHASE_4E_DOMAINS, (
        "every 4E domain needs a derivation spec, and no shipped 2D-D domain may "
        "have one -- those are read from their own tables"
    )


# --- the four states --------------------------------------------------------


@pytest.mark.parametrize("domain", sorted(PHASE_4E_DOMAINS, key=lambda d: d.value))
def test_a_domain_with_no_evidence_is_empty_with_a_machine_readable_reason(
    domain: TwinDomain,
) -> None:
    """Sec14.5 control 10. No zero, no average over an empty set, no default."""
    model = derive_domain(domain, [], user_id=USER, now=NOW)

    assert model.state is DomainState.EMPTY
    assert model.reason is not None
    assert isinstance(model.reason.code, DomainReasonCode)
    assert model.reason.detail
    assert model.evidence_count == 0
    assert model.facts == {}, "an empty domain rendered a fact"


def test_a_domain_with_real_evidence_is_populated() -> None:
    model = derive_domain(
        TwinDomain.PERSONAL_WORKFLOW,
        [_memory_evidence(TwinDomain.PERSONAL_WORKFLOW) for _ in range(3)],
        user_id=USER,
        now=NOW,
    )

    assert model.state is DomainState.POPULATED
    assert model.reason is None
    assert model.evidence_count == 3
    assert model.facts["observation_count"] == 3


def test_evidence_without_a_source_timestamp_reports_it_rather_than_guessing() -> None:
    """The `created_at`-is-optional path (Sec0.1.5). Substituting the delivery
    time would silently collapse AC-6's gap to zero, so the absence is a state."""
    model = derive_domain(
        TwinDomain.PERSONAL_WORKFLOW,
        [_memory_evidence(TwinDomain.PERSONAL_WORKFLOW, age_days=None)],
        user_id=USER,
        now=NOW,
    )

    assert model.state is DomainState.PARTIALLY_POPULATED
    assert model.reason is not None
    assert model.reason.code is DomainReasonCode.SOURCE_TIMESTAMP_MISSING
    assert "first_evidence_at" not in model.facts


# --- the ratified per-domain floor (Sec12, Sec19.1) -------------------------


@pytest.mark.parametrize(
    "domain", [TwinDomain.SOFTWARE_ENVIRONMENT, TwinDomain.HARDWARE_ENVIRONMENT]
)
def test_the_4f_domains_report_no_source_engine_and_cannot_be_populated(
    domain: TwinDomain,
) -> None:
    model = derive_domain(domain, [], user_id=USER, now=NOW)

    assert model.state is DomainState.EMPTY
    assert model.reason is not None
    assert model.reason.code is DomainReasonCode.NO_SOURCE_ENGINE
    assert DOMAIN_SPECS[domain].max_state is DomainState.EMPTY
    assert DOMAIN_SPECS[domain].unavailable_fields, (
        "a domain with no source must still say which Part 16 fields it would hold"
    )


@pytest.mark.parametrize(
    "domain", [TwinDomain.KNOWLEDGE_PROFILE, TwinDomain.SKILL_PROFILE]
)
def test_the_partial_domains_cannot_claim_populated_even_with_evidence(
    domain: TwinDomain,
) -> None:
    model = derive_domain(
        domain,
        [
            _memory_evidence(
                domain, memory_type="procedural", knowledge_node_id="concept:asyncio"
            )
        ],
        user_id=USER,
        now=NOW,
    )

    assert model.state is DomainState.PARTIALLY_POPULATED
    assert model.reason is not None
    assert model.reason.code is DomainReasonCode.EVIDENCE_PARTIAL
    assert model.unavailable_fields, "partially_populated must name the missing part"


def test_productivity_patterns_distinguishes_no_producer_from_no_data() -> None:
    """Sec0.1.4's disclosure, as a reason code. `perception.attention.observed` is
    real and consumed; nothing in a stock deployment emits it. That is a different
    claim from "this user has produced nothing", and the panel must be able to
    tell them apart."""
    model = derive_domain(TwinDomain.PRODUCTIVITY_PATTERNS, [], user_id=USER, now=NOW)

    assert model.reason is not None
    assert model.reason.code is DomainReasonCode.NO_AUTONOMOUS_PRODUCER
    assert "nova-companion" in model.reason.detail


# --- privacy (ratified Sec19.3, read per Sec0.1.6) --------------------------


def test_the_privacy_allow_list_is_public_and_internal_only() -> None:
    """Stated as an allow-list so a level added later is excluded by default. A
    deny-list would admit it silently, which is the failure mode worth designing
    against."""
    assert set(CONTRIBUTING_PRIVACY_LEVELS) == {PrivacyLevel.PUBLIC, PrivacyLevel.INTERNAL}
    assert not hasattr(PrivacyLevel, "PRIVATE"), (
        "if a PRIVATE member is ever added, Sec0.1.6's mapping needs revisiting"
    )


@pytest.mark.parametrize(
    "level", [PrivacyLevel.CONFIDENTIAL, PrivacyLevel.HIGHLY_SENSITIVE]
)
def test_a_restricted_memory_produces_no_evidence_at_all(level: PrivacyLevel) -> None:
    """Not a filtered row, not a redacted one -- none. The evidence never exists,
    so there is nothing for any layer above to leak (Sec14.5 control 6)."""
    rows = evidence_from_memory_created(
        user_id=USER,
        memory_id=uuid4(),
        memory_type="procedural",
        privacy_level=level,
        project_id=uuid4(),
        knowledge_node_id="concept:secrets",
        source_created_at=NOW,
        observed_at=NOW,
    )
    assert rows == []


@pytest.mark.parametrize("level", [PrivacyLevel.PUBLIC, PrivacyLevel.INTERNAL])
def test_a_permitted_memory_fans_out_to_the_domains_it_supports(
    level: PrivacyLevel,
) -> None:
    rows = evidence_from_memory_created(
        user_id=USER,
        memory_id=uuid4(),
        memory_type="procedural",
        privacy_level=level,
        project_id=uuid4(),
        knowledge_node_id="concept:asyncio",
        source_created_at=NOW,
        observed_at=NOW,
    )

    assert {r.domain for r in rows} == {
        TwinDomain.PERSONAL_WORKFLOW,
        TwinDomain.PROJECTS,
        TwinDomain.KNOWLEDGE_PROFILE,
        TwinDomain.SKILL_PROFILE,
        TwinDomain.LEARNING_PROGRESS,
    }
    assert all(r.source_created_at == NOW for r in rows)


def test_no_evidence_row_ever_carries_memory_content() -> None:
    """Structural, not incidental: none of the three subscribed payloads includes
    content, and derivation adds none. A domain that cannot hold a memory's text
    cannot leak one."""
    rows = [
        *evidence_from_memory_created(
            user_id=USER,
            memory_id=uuid4(),
            memory_type="episodic",
            privacy_level=PrivacyLevel.INTERNAL,
            project_id=uuid4(),
            knowledge_node_id="concept:x",
            source_created_at=NOW,
            observed_at=NOW,
        ),
        *evidence_from_decision_recorded(
            user_id=USER,
            decision_id=uuid4(),
            confidence_at_decision=0.8,
            source_created_at=NOW,
            observed_at=NOW,
        ),
        *evidence_from_attention_observed(
            user_id=USER,
            observation_id=uuid4(),
            attention_state="focused",
            gaze_direction="screen",
            confidence=0.9,
            observed_at=NOW,
        ),
    ]
    for row in rows:
        assert "content" not in row.attributes
        assert "objective" not in row.attributes
        assert "chosen_alternative" not in row.attributes


# --- AC-6: the project model and its gap ------------------------------------


def test_the_project_model_computes_a_multi_week_gap_from_persisted_timestamps() -> None:
    """**AC-6's arithmetic.** The gap is a subtraction over real persisted
    timestamps, not a simulation: nothing here reads a clock except `now`, which
    the caller supplies."""
    project_id = uuid4()
    rows = [
        _memory_evidence(
            TwinDomain.PROJECTS,
            age_days=age,
            memory_type="project",
            project_id=str(project_id),
        )
        for age in (60.0, 45.0, 31.0)
    ]

    models = derive_project_models(rows, user_id=USER, now=NOW)

    assert len(models) == 1
    project = models[0]
    assert project.project_id == project_id
    assert project.memory_count == 3
    assert project.first_activity_at == NOW - timedelta(days=60)
    assert project.last_activity_at == NOW - timedelta(days=31)
    assert project.gap_days == pytest.approx(31.0)
    assert project.gap_days > 21, "a multi-week gap must read as multi-week"


def test_a_project_with_no_timestamped_evidence_reports_a_null_gap_not_zero() -> None:
    """`0.0` would render as "active today" -- the opposite of what is known."""
    models = derive_project_models(
        [
            _memory_evidence(
                TwinDomain.PROJECTS, age_days=None, project_id=str(uuid4())
            )
        ],
        user_id=USER,
        now=NOW,
    )

    assert models[0].gap_days is None
    assert models[0].last_activity_at is None


def test_projects_are_ordered_most_recently_active_first_with_unplaceable_last() -> None:
    stale, fresh, unplaceable = uuid4(), uuid4(), uuid4()
    rows = [
        _memory_evidence(TwinDomain.PROJECTS, age_days=90.0, project_id=str(stale)),
        _memory_evidence(TwinDomain.PROJECTS, age_days=2.0, project_id=str(fresh)),
        _memory_evidence(TwinDomain.PROJECTS, age_days=None, project_id=str(unplaceable)),
    ]

    order = [m.project_id for m in derive_project_models(rows, user_id=USER, now=NOW)]

    assert order == [fresh, stale, unplaceable]


def test_evidence_without_a_project_id_never_becomes_a_project() -> None:
    models = derive_project_models(
        [_memory_evidence(TwinDomain.PERSONAL_WORKFLOW)], user_id=USER, now=NOW
    )
    assert models == []


# --- the derived facts ------------------------------------------------------


def test_goals_reports_a_null_mean_confidence_when_no_decision_carried_one() -> None:
    """`None`, never `0.0`: "no decision recorded a confidence" and "every decision
    was made with zero confidence" are different claims."""
    model = derive_domain(
        TwinDomain.GOALS,
        [
            DomainEvidence(
                user_id=USER,
                domain=TwinDomain.GOALS,
                kind=EvidenceKind.MEMORY_DECISION_RECORDED,
                source_record_id=uuid4(),
                source_created_at=NOW,
                observed_at=NOW,
            )
        ],
        user_id=USER,
        now=NOW,
    )

    assert model.facts["decision_count"] == 1
    assert model.facts["mean_confidence_at_decision"] is None


def test_knowledge_profile_counts_nodes_rather_than_naming_concepts() -> None:
    rows = [
        _memory_evidence(
            TwinDomain.KNOWLEDGE_PROFILE, knowledge_node_id=node, memory_type="semantic"
        )
        for node in ("concept:asyncio", "concept:asyncio", "concept:sql")
    ]

    model = derive_domain(TwinDomain.KNOWLEDGE_PROFILE, rows, user_id=USER, now=NOW)

    assert model.facts["known_node_count"] == 2
    assert model.facts["observations_per_node"]["concept:asyncio"] == 2
