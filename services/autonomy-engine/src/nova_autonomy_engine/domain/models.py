"""Autonomy Engine domain entities (Bible Part 14), per
docs/design/phase-4/04-tdd-4d-autonomy-engine.md §4–§7.

**Everything here is engine-local and stays out of `nova_contracts`.** 4D
claims no `autonomy.*` Event Bus subject (ratified decision **D-4D-1**, TDD
§0.1/§8.2), so none of these entities is ever published and none needs a
shared schema. This is the same boundary `action-engine`'s `PendingApproval`
and `IdentityConfidencePolicy` already established -- repository-internal
concerns are not promoted to the contracts package.

`RiskLevel` is the one exception and is **imported, never redefined**:
`nova_contracts.events.planning.RiskLevel` is, in its own docstring, *"the one
canonical risk-tier scale anywhere in this project"*, taken verbatim from
Bible Part 14's risk classification. A second scale here would need a mapping
layer, and a mapping layer is where the two drift.

**Three `None`s in this module are load-bearing and must not be flattened to a
number** -- each means *"no evidence"*, which is not the same claim as *"zero"*:
`TrustScore.score`, `TrustMetricSnapshot.correction_frequency`, and
`PermissionGrant.max_risk`. All three fail closed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from uuid import UUID, uuid4

from nova_contracts.events.planning import RiskLevel
from pydantic import BaseModel, Field

__all__ = [
    "AUTONOMY_LEVEL_NAMES",
    "DEFINED_LEVELS",
    "PERMISSION_CATEGORY_ORDER",
    "SELECTABLE_LEVELS",
    "AutonomyLevel",
    "AutonomyLevelSetting",
    "DecisionLogEntry",
    "DecisionOutcome",
    "ExecutionOutcomeSummary",
    "PermissionCategory",
    "PermissionGrant",
    "Policy",
    "PolicyCheck",
    "PolicyEffect",
    "PolicyMatch",
    "RiskLevel",
    "Suggestion",
    "SuggestionStatus",
    "TrustInputStatus",
    "TrustMetricSnapshot",
    "TrustScore",
]


class AutonomyLevel(IntEnum):
    """Bible Part 14 "AUTONOMY LEVELS", all six named so the vocabulary is
    complete and nobody invents a seventh. **Naming a level is not enabling
    it** -- see `DEFINED_LEVELS` and `SELECTABLE_LEVELS`.

    `IntEnum` because doc 07's canonical `autonomy.decision_log.autonomy_level`
    column is `SMALLINT`; the ordering is also meaningful (higher = more
    autonomous), which a `StrEnum` would not carry.
    """

    OBSERVATION_ONLY = 0
    SUGGESTIVE = 1
    ASSISTED = 2
    SUPERVISED = 3
    HIGHLY_AUTONOMOUS = 4
    FULL_ORGANIZATIONAL = 5


AUTONOMY_LEVEL_NAMES: dict[AutonomyLevel, str] = {
    AutonomyLevel.OBSERVATION_ONLY: "Observation Only",
    AutonomyLevel.SUGGESTIVE: "Suggestive",
    AutonomyLevel.ASSISTED: "Assisted",
    AutonomyLevel.SUPERVISED: "Supervised",
    AutonomyLevel.HIGHLY_AUTONOMOUS: "Highly Autonomous",
    AutonomyLevel.FULL_ORGANIZATIONAL: "Full Organizational Autonomy",
}
"""Bible Part 14's own names, verbatim. Rendered by the panel (TDD §12) so the
UI and the Bible cannot drift apart in wording."""

DEFINED_LEVELS: frozenset[AutonomyLevel] = frozenset(
    {AutonomyLevel.OBSERVATION_ONLY, AutonomyLevel.SUGGESTIVE, AutonomyLevel.ASSISTED}
)
"""Levels 0-2 have defined semantics in 4D (TDD §1 row 2). Levels 3-5 are
named in the vocabulary and deliberately undefined."""

SELECTABLE_LEVELS: frozenset[AutonomyLevel] = frozenset(
    {AutonomyLevel.OBSERVATION_ONLY, AutonomyLevel.SUGGESTIVE}
)
"""**Only Levels 0 and 1 may be selected.** Level 2 is defined but disabled --
decision **D-1** assigns enabling it to milestone 4F. `SELECTABLE_LEVELS` is
deliberately a separate, smaller set than `DEFINED_LEVELS`: collapsing them
would make "defined" and "enabled" the same idea, which is exactly the
distinction D-1 turns on."""


class DecisionOutcome(StrEnum):
    """TDD §4.3's four outcomes. `EXECUTE` is **declared and unreachable** in
    4D: no code path produces it, and `domain/decision.py` asserts that it
    cannot be produced at a selectable level. It is named so that a future
    milestone enabling Level 2 extends a known vocabulary rather than
    inventing one, and so the negative control has something to force."""

    OBSERVE_ONLY = "observe_only"
    PROPOSE = "propose"
    DENY = "deny"
    EXECUTE = "execute"


class SuggestionStatus(StrEnum):
    """The AC-5 lifecycle. `PROPOSED` is the only state a decision may leave,
    and `APPROVED`/`REJECTED` are terminal -- which is what makes a second
    decision a 409 rather than an overwrite (TDD §13)."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PermissionCategory(StrEnum):
    """Bible Part 14 "PERMISSION MATRIX" -- the ten categories, verbatim and in
    the Bible's own order. `PERMISSION_CATEGORY_ORDER` pins the ordering
    separately because `StrEnum` membership alone would let a later edit
    reorder them silently."""

    READ = "read"
    ANALYZE = "analyze"
    RECOMMEND = "recommend"
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
    EXECUTE = "execute"
    DEPLOY = "deploy"
    PURCHASE = "purchase"
    COMMUNICATE = "communicate"


PERMISSION_CATEGORY_ORDER: tuple[PermissionCategory, ...] = (
    PermissionCategory.READ,
    PermissionCategory.ANALYZE,
    PermissionCategory.RECOMMEND,
    PermissionCategory.CREATE,
    PermissionCategory.MODIFY,
    PermissionCategory.DELETE,
    PermissionCategory.EXECUTE,
    PermissionCategory.DEPLOY,
    PermissionCategory.PURCHASE,
    PermissionCategory.COMMUNICATE,
)
"""Bible Part 14's order, pinned. The panel renders the matrix in this order,
and `tests/unit/test_permission_matrix.py` asserts the tuple against the
Bible's own list -- ten categories, that sequence, no additions."""


class PolicyEffect(StrEnum):
    """**There is deliberately no `ALLOW`** (TDD §6). An `allow` effect can
    only matter where something would otherwise happen automatically -- Level
    2+, which 4D does not enable -- so shipping it would mean shipping an
    effect with no reachable behaviour, and inviting a later reader to assume
    auto-execution exists."""

    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class PolicyMatch(BaseModel):
    """What a policy matches on. Every field is optional and `None` means
    *"do not constrain on this axis"*, so an all-`None` match matches
    everything -- which is a legitimate "deny all" policy, not a
    misconfiguration.

    `min_risk` is a **floor**, not a ceiling: a policy that denies at
    `moderate` and above sets `min_risk=moderate`."""

    category: PermissionCategory | None = None
    min_risk: RiskLevel | None = None
    capability_class: str | None = None


class Policy(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    name: str
    effect: PolicyEffect
    match: PolicyMatch = Field(default_factory=PolicyMatch)
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PolicyCheck(BaseModel):
    """One consulted policy, recorded whether or not it fired. TDD §6 item 3:
    *"the decision log must show which policies were consulted, not only which
    fired."* Without the non-firing entries a reader cannot tell a policy that
    did not match from a policy that did not exist."""

    policy_id: UUID
    name: str
    effect: PolicyEffect
    matched: bool


class PermissionGrant(BaseModel):
    """`max_risk is None` means **no autonomous authority in this category** --
    the absent-grant fail-closed default (TDD §7). It is not "unlimited", and
    it is not `negligible`."""

    user_id: UUID
    category: PermissionCategory
    max_risk: RiskLevel | None = None
    requires_approval_above: RiskLevel | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TrustMetricSnapshot(BaseModel):
    """What 4D read from `digital-twin-engine`'s 2D-D `TrustMetric`, copied at
    read time so the decision log records the input as it was.

    **`correction_frequency is None` means "no completed sessions in the
    window"** -- 2D-D's own docstring: *"'no data yet' is not the same claim as
    'measured zero corrections'"*. Coercing it to `0.0` would read as perfect
    trust, and a negative control exists for exactly that (TDD §16 control 3).

    The two `*_acceptance_rate` fields are **reserved and always `None` in
    2D-D**. 4D copies them through if present and **never computes them** --
    computing them here would re-derive 2D-D's own deferred work in the wrong
    engine."""

    correction_frequency: float | None = None
    window_session_count: int = 0
    clarification_acceptance_rate: float | None = None
    proactive_suggestion_acceptance_rate: float | None = None
    computed_at: datetime | None = None


class ExecutionOutcomeSummary(BaseModel):
    """Reserved, and **always empty in 4D by construction**: nothing executes
    at Levels 0-1, so there are no execution outcomes to learn from. Declared
    now rather than migrated in later, following 2D-D's own precedent for
    reserved-but-uncomputed fields."""

    total: int = 0
    succeeded: int = 0
    failed: int = 0


class TrustInputStatus(StrEnum):
    """Why a trust input is what it is. **Three states, not two**, because
    TDD §16 control 12 forbids reporting a degraded upstream as an empty
    success: `NO_DATA` (the source answered, this user has no metric yet) and
    `UNAVAILABLE` (the source could not be consulted at all) both yield
    `TrustScore.score is None`, and they must remain distinguishable in the
    response so the panel can say which.

    Not part of TDD §5.2's sketch of `TrustScore`; added because §13's first
    row and control 12 together require the distinction to survive as far as
    the API, and carrying it on the score is the only place it is available to
    every reader of one."""

    AVAILABLE = "available"
    NO_DATA = "no_data"
    UNAVAILABLE = "unavailable"


class TrustScore(BaseModel):
    """Per-category, per Bible Part 14: *"NOVA maintains a dynamic trust score
    for every category."*

    **`score is None` is a first-class state and it is fail-closed** -- an
    unknown score never satisfies a threshold. It is not `0.0`; `0.0` would be
    a measured floor, which is a different claim.

    **Trust never raises an autonomy level by itself.** Part 14: *"As NOVA
    demonstrates reliable performance, **the user may** gradually increase
    autonomy."* Level changes are a user action (TDD §5.2)."""

    user_id: UUID
    category: PermissionCategory
    score: float | None = None
    evidence_count: int = 0
    conversational: TrustMetricSnapshot | None = None
    execution: ExecutionOutcomeSummary | None = None
    input_status: TrustInputStatus = TrustInputStatus.NO_DATA
    detail: str | None = None
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AutonomyLevelSetting(BaseModel):
    """One row per user (ADR-025: one trusted user per instance, so in practice
    one row). Keyed by `user_id` because the schema already is, **not** because
    4D introduces multi-user -- TDD §10 item 5."""

    user_id: UUID
    level: AutonomyLevel = AutonomyLevel.OBSERVATION_ONLY
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Suggestion(BaseModel):
    """What Level 1 produces and the panel renders. **A suggestion is a
    proposal, never an execution** -- nothing in 4D acts on an approved
    suggestion; approval records the user's decision and stops there (TDD
    §18's AC-5 mapping)."""

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    category: PermissionCategory
    risk: RiskLevel
    title: str
    detail: str = ""
    status: SuggestionStatus = SuggestionStatus.PROPOSED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    decided_at: datetime | None = None


class DecisionLogEntry(BaseModel):
    """Doc 07's canonical `autonomy.decision_log`, append-only.

    `subject_id` carries doc 07's `action_id` column. The column name is
    doc 07's and is kept; the field is named for what 4D actually puts in it --
    the suggestion's id -- because 4D creates no `Action` (the `action-engine`
    boundary, TDD §8.1). A future milestone that decides real Actions writes
    an Action id into the same column.

    `confidence` is `REAL NOT NULL` in doc 07, so an absent trust score is
    recorded as the fail-closed `0.0` **in the log only** -- `TrustScore.score`
    itself stays `None`. The log records what the gate acted on; the score
    records what was known."""

    id: UUID = Field(default_factory=uuid4)
    subject_id: UUID
    autonomy_level: AutonomyLevel
    risk: RiskLevel
    confidence: float
    policy_checks: list[PolicyCheck] = Field(default_factory=list)
    outcome: DecisionOutcome | None = None
    reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
