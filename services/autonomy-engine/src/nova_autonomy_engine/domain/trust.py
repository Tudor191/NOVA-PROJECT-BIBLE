"""Trust Engine -- TDD 4D §5, Bible Part 14 "TRUST ENGINE".

Bible Part 14: *"Trust is earned. Not assumed."* and *"NOVA maintains a
dynamic trust score for every category."* Two things follow, and both are
enforced here:

**1. The 2D-D signal is consumed, never re-derived.** Master scope §5:
*"The Trust Engine consumes Phase 2D-D's conversational trust-development
signal as one input rather than re-deriving an unrelated one."*
`digital-twin-engine` computes `correction_frequency` as *average corrections
per completed session over a rolling window*
(`digital_twin_engine/domain/trust_metric.py`). This module reads that number
and maps it to a score. It does **not** recompute it, does not look at
sessions, and does not compute either `*_acceptance_rate` -- those are 2D-D's
own deferred work, and computing them here would relocate another engine's
backlog into this one.

**2. Every `None` stays `None`.** Three fail-closed paths, each with a
negative control (TDD §16 controls 3 and 4):

* the source could not be consulted -> `score=None`, `UNAVAILABLE`;
* the source answered but has no metric for this user -> `score=None`,
  `NO_DATA`;
* a metric exists but `correction_frequency is None` (2D-D's *"no completed
  sessions in the window"*) -> `score=None`, `NO_DATA`. **Never `0.0`** --
  2D-D's own docstring: *"'no data yet' is not the same claim as 'measured
  zero corrections'"*, and `0.0` corrections would read as *perfect* trust,
  the exactly-inverted error.

`satisfies_threshold` is the only place a score is compared to a requirement,
and an unknown score never satisfies one.

**Trust does not deny in 4D.** Nothing executes at Levels 0-1, so there is no
threshold for trust to gate; the score is computed, recorded on the decision
and rendered by the panel. `satisfies_threshold` exists because the fail-closed
semantics of an unknown score must be fixed *now*, tested now, and
control-4-protected now -- not written for the first time by whichever
milestone first needs to gate on it.

**The score is not an autonomy level.** Part 14: *"As NOVA demonstrates
reliable performance, **the user may** gradually increase autonomy."* Nothing
in this module writes `AutonomyLevelSetting`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from nova_autonomy_engine.domain.models import (
    ExecutionOutcomeSummary,
    PermissionCategory,
    TrustInputStatus,
    TrustMetricSnapshot,
    TrustScore,
)

__all__ = [
    "conversational_component",
    "compute_trust_score",
    "satisfies_threshold",
]


def conversational_component(correction_frequency: float | None) -> float | None:
    """Map 2D-D's *corrections per session* to a `0.0`-`1.0` trust component,
    or `None` when there is no measurement.

        score = 1 / (1 + correction_frequency)

    Chosen because `correction_frequency` is an unbounded average on
    `[0, inf)` while a trust score must be bounded, and this map is the
    simplest one that is **monotone decreasing, needs no arbitrary cap, and
    never reaches either endpoint spuriously**: zero corrections gives `1.0`,
    one correction per session gives `0.5`, three gives `0.25`, and no finite
    correction rate gives `0.0`. A linear `1 - k * frequency` would need an
    invented `k` and would clamp to `0.0` at an invented rate, making a
    heavily-corrected user indistinguishable from an impossible one.

    A negative `correction_frequency` cannot occur (it is a count divided by a
    positive count) and is rejected rather than silently producing a score
    above `1.0`.
    """
    if correction_frequency is None:
        return None
    if correction_frequency < 0:
        raise ValueError(
            f"correction_frequency must be non-negative, got {correction_frequency!r}"
        )
    return 1.0 / (1.0 + correction_frequency)


def compute_trust_score(
    *,
    user_id: UUID,
    category: PermissionCategory,
    conversational: TrustMetricSnapshot | None,
    status: TrustInputStatus = TrustInputStatus.AVAILABLE,
    detail: str | None = None,
    execution: ExecutionOutcomeSummary | None = None,
    now: datetime | None = None,
) -> TrustScore:
    """Build the per-category score from the inputs actually available.

    `execution` is **`None` in 4D by construction** -- nothing executes at
    Levels 0-1, so there are no execution outcomes to learn from. The
    parameter exists so the second input has a declared home (TDD §5.2), and
    passing a non-`None` value is accepted and recorded but contributes
    nothing to the score: inventing a weighting for evidence this milestone
    cannot produce would be fabricating a formula, not implementing one.

    `evidence_count` reports 2D-D's own `window_session_count` -- the number of
    completed sessions the input was computed from -- so a score of `1.0` from
    one session is visibly weaker than the same score from fifty, without this
    module inventing a confidence interval it has no basis for.
    """
    resolved_status = status
    if status is TrustInputStatus.AVAILABLE and conversational is None:
        resolved_status = TrustInputStatus.NO_DATA

    score: float | None = None
    evidence_count = 0
    if conversational is not None:
        score = conversational_component(conversational.correction_frequency)
        evidence_count = conversational.window_session_count
        if score is None:
            # A metric row exists but the window held no completed sessions:
            # 2D-D's own "no data yet", which is not a measured zero.
            resolved_status = TrustInputStatus.NO_DATA

    return TrustScore(
        user_id=user_id,
        category=category,
        score=score,
        evidence_count=evidence_count,
        conversational=conversational,
        execution=execution,
        input_status=resolved_status,
        detail=detail,
        computed_at=now or datetime.now(UTC),
    )


def satisfies_threshold(score: float | None, threshold: float) -> bool:
    """**`False` for `None`, always.** An unknown trust score never satisfies a
    requirement -- the same fail-closed shape as `action-engine`'s absent
    `IdentityConfidencePolicy` (absent -> threshold `1.0`) and its absent
    identity signal (absent -> confidence `0.0`). TDD §16 control 4 requires
    that making an absent score satisfy a threshold fails the suite."""
    if score is None:
        return False
    return score >= threshold
