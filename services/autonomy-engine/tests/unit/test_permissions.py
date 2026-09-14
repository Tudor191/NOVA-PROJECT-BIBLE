"""Permission Matrix, and **negative controls 5 and 11** (TDD §16).

Control 5 -- *making an absent `PermissionGrant` permissive must fail*.
Control 11 -- *a 4D surface granting more than `action-engine` permits must
fail*. Control 11 is asserted **exhaustively**: every category x every risk x
every grant shape is swept, and none produces anything but a denial or a
requirement for approval. That is the strongest available form of the claim --
it does not depend on choosing the right example.
"""

from __future__ import annotations

import itertools
from uuid import uuid4

import pytest
from nova_autonomy_engine.domain.models import (
    PERMISSION_CATEGORY_ORDER,
    PermissionCategory,
    PermissionGrant,
)
from nova_autonomy_engine.domain.permissions import (
    evaluate_permission,
    find_grant,
    matrix_by_category,
)
from nova_autonomy_engine.domain.risk import RISK_ORDER
from nova_contracts.events.planning import RiskLevel

USER = uuid4()


def test_the_ten_bible_categories_verbatim_and_in_order() -> None:
    """docs/bible/part-14-autonomy-engine.md "PERMISSION MATRIX", lines
    201-219."""
    assert [category.value for category in PERMISSION_CATEGORY_ORDER] == [
        "read",
        "analyze",
        "recommend",
        "create",
        "modify",
        "delete",
        "execute",
        "deploy",
        "purchase",
        "communicate",
    ]


def test_the_order_tuple_covers_the_enum_exactly() -> None:
    """An eleventh category added to the enum without being ordered here fails
    the suite rather than rendering last by accident."""
    assert set(PERMISSION_CATEGORY_ORDER) == set(PermissionCategory)
    assert len(PERMISSION_CATEGORY_ORDER) == 10


# --- Negative control 5 ------------------------------------------------------
@pytest.mark.parametrize("category", list(PermissionCategory))
@pytest.mark.parametrize("risk", list(RiskLevel))
def test_control_5_an_absent_grant_denies_every_category_at_every_risk(
    category: PermissionCategory, risk: RiskLevel
) -> None:
    """**Negative control 5.** No row means no autonomous authority -- not
    unlimited, and not `negligible`-and-below. Same idiom as `action-engine`'s
    absent `IdentityConfidencePolicy`."""
    result = evaluate_permission(None, category=category, risk=risk)
    assert result.denied is True
    assert "absent grant confers no autonomous authority" in (result.reason or "")


@pytest.mark.parametrize("risk", list(RiskLevel))
def test_control_5_a_grant_with_no_ceiling_denies_identically(risk: RiskLevel) -> None:
    """`max_risk=None` on an existing row has granted nothing. The two
    spellings of "no authority" must not diverge."""
    grant = PermissionGrant(user_id=USER, category=PermissionCategory.DEPLOY, max_risk=None)
    result = evaluate_permission(grant, category=PermissionCategory.DEPLOY, risk=risk)
    assert result.denied is True
    assert "confers no autonomous authority" in (result.reason or "")


def test_a_grant_admits_risks_up_to_its_ceiling_and_denies_above_it() -> None:
    grant = PermissionGrant(
        user_id=USER, category=PermissionCategory.CREATE, max_risk=RiskLevel.LOW
    )
    for risk in (RiskLevel.NEGLIGIBLE, RiskLevel.LOW):
        assert evaluate_permission(
            grant, category=PermissionCategory.CREATE, risk=risk
        ).denied is False
    for risk in (RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.CRITICAL):
        result = evaluate_permission(grant, category=PermissionCategory.CREATE, risk=risk)
        assert result.denied is True
        assert "exceeds the maximum low" in (result.reason or "")


def test_requires_approval_above_is_a_floor_on_the_admitted_range() -> None:
    grant = PermissionGrant(
        user_id=USER,
        category=PermissionCategory.MODIFY,
        max_risk=RiskLevel.HIGH,
        requires_approval_above=RiskLevel.MODERATE,
    )
    assert (
        evaluate_permission(grant, category=PermissionCategory.MODIFY, risk=RiskLevel.LOW)
        .requires_approval
        is False
    )
    assert (
        evaluate_permission(grant, category=PermissionCategory.MODIFY, risk=RiskLevel.MODERATE)
        .requires_approval
        is True
    )


def test_find_grant_returns_none_rather_than_a_default_row() -> None:
    grants = [PermissionGrant(user_id=USER, category=PermissionCategory.READ)]
    assert find_grant(grants, PermissionCategory.READ) is not None
    assert find_grant(grants, PermissionCategory.DEPLOY) is None


def test_matrix_reports_every_category_including_the_ungranted_ones() -> None:
    """The panel must be able to show an ungranted category **as ungranted**
    rather than omitting it, or the user cannot tell "no authority" from "not
    displayed"."""
    grants = [
        PermissionGrant(
            user_id=USER, category=PermissionCategory.READ, max_risk=RiskLevel.MODERATE
        )
    ]
    matrix = matrix_by_category(grants)
    assert list(matrix) == list(PERMISSION_CATEGORY_ORDER)
    assert matrix[PermissionCategory.READ] is not None
    assert matrix[PermissionCategory.PURCHASE] is None


# --- Negative control 11, part 1 ---------------------------------------------
def test_control_11_the_verdict_type_can_express_only_denial_or_approval() -> None:
    """**Negative control 11**, structural half. `PermissionEvaluation` has
    exactly three fields and none of them is affirmative: there is no value it
    can carry that means "may act unattended". Adding an `allowed` or
    `may_execute` field fails here.

    The behavioural half -- that no grant configuration reaches
    `DecisionOutcome.EXECUTE` through the whole pipeline -- is swept
    exhaustively in `test_decision_pipeline.py`, which is where an escalation
    would actually have to surface.
    """
    result = evaluate_permission(None, category=PermissionCategory.READ, risk=RiskLevel.LOW)
    assert set(result.model_dump()) == {"denied", "reason", "requires_approval"}


def test_control_11_lowering_a_ceiling_never_widens_authority() -> None:
    """Monotonicity, swept over every category, risk and ceiling: a stricter
    ceiling can only ever deny at least as much as a looser one. A comparison
    accidentally inverted (the `StrEnum` trap `risk.py` exists for) breaks this
    without breaking any single-example test."""
    swept = 0
    for category, risk in itertools.product(PermissionCategory, RiskLevel):
        denials = [
            evaluate_permission(
                PermissionGrant(user_id=USER, category=category, max_risk=ceiling),
                category=category,
                risk=risk,
            ).denied
            for ceiling in RISK_ORDER
        ]
        # Ordered loosest-last: once a ceiling admits the risk, no looser one
        # may deny it. `denials` must therefore be non-increasing.
        assert denials == sorted(denials, reverse=True), (category, risk, denials)
        swept += 1
    assert swept == 10 * 5
