"""Permission Matrix -- TDD 4D §7, Bible Part 14 "PERMISSION MATRIX".

Ten categories, each with its own risk ceiling. *"Each permission should
support granular configuration"* is satisfied by per-category rows with their
own ceilings, not by one global setting.

**Absent grant fails closed.** No row for a category means *no autonomous
authority in that category* -- not unlimited authority, and not
`negligible`-and-below. This is the same idiom `action-engine` already uses
for `IdentityConfidencePolicy` (absent policy -> threshold `1.0`, the
strictest possible) and `digital-twin-engine` for `ProactiveBoundaryPolicy`.
A negative control (TDD §16 control 5) requires that making an absent grant
permissive fails the suite.

`max_risk is None` on a row that *does* exist is treated identically to the
row being absent, and deliberately so: a grant created with no ceiling has
granted nothing, and the two spellings of "no authority" must not diverge.

**This module cannot widen anything** (TDD §10 item 6, §16 control 11). Its
only outputs are "denied" and "requires approval". There is no code path
here, for any grant configuration over any (category, risk) pair, that
produces permission to execute -- so no Permission Matrix setting can grant
more than `action-engine`'s own pipeline permits, which remains the sole
authority over execution.
"""

from __future__ import annotations

from collections.abc import Sequence

from nova_contracts.events.planning import RiskLevel
from pydantic import BaseModel

from nova_autonomy_engine.domain.models import (
    PERMISSION_CATEGORY_ORDER,
    PermissionCategory,
    PermissionGrant,
)
from nova_autonomy_engine.domain.risk import risk_at_least, risk_at_most

__all__ = [
    "PermissionEvaluation",
    "evaluate_permission",
    "find_grant",
    "matrix_by_category",
]


class PermissionEvaluation(BaseModel):
    """The Permission stage's verdict. As with `PolicyEvaluation`, there is no
    field meaning "allowed to execute" -- the two possible outcomes are a
    denial and a requirement for approval."""

    denied: bool = False
    reason: str | None = None
    requires_approval: bool = False


def find_grant(
    grants: Sequence[PermissionGrant], category: PermissionCategory
) -> PermissionGrant | None:
    """First grant for `category`, or `None`. `None` is a meaningful answer
    here -- see this module's docstring -- and callers must not substitute a
    default-constructed `PermissionGrant` for it."""
    for grant in grants:
        if grant.category is category:
            return grant
    return None


def evaluate_permission(
    grant: PermissionGrant | None, *, category: PermissionCategory, risk: RiskLevel
) -> PermissionEvaluation:
    """Deny unless an explicit grant covers `risk` in `category`.

    Three denial cases, kept separate so the decision log's reason says which
    one applied:

    * no grant row at all -- the fail-closed default;
    * a row whose `max_risk` is `None` -- granted nothing;
    * a row whose ceiling is below the request's risk.
    """
    if grant is None:
        return PermissionEvaluation(
            denied=True,
            reason=(
                f"no permission grant for category={category.value}; absent grant confers "
                f"no autonomous authority"
            ),
        )
    if grant.max_risk is None:
        return PermissionEvaluation(
            denied=True,
            reason=(
                f"permission grant for category={category.value} sets no maximum risk; "
                f"it confers no autonomous authority"
            ),
        )
    if not risk_at_most(risk, grant.max_risk):
        return PermissionEvaluation(
            denied=True,
            reason=(
                f"risk={risk.value} exceeds the maximum {grant.max_risk.value} granted for "
                f"category={category.value}"
            ),
        )
    requires_approval = grant.requires_approval_above is not None and risk_at_least(
        risk, grant.requires_approval_above
    )
    return PermissionEvaluation(requires_approval=requires_approval)


def matrix_by_category(
    grants: Sequence[PermissionGrant],
) -> dict[PermissionCategory, PermissionGrant | None]:
    """The full ten-category matrix in Bible Part 14's order, with `None` for
    every category that has no grant.

    Returning the absent categories explicitly -- rather than only the rows
    that exist -- is what lets the panel render the complete matrix and show
    an ungranted category as ungranted, instead of omitting it and leaving the
    user unable to tell "no authority" from "not displayed".
    """
    found = {category: find_grant(grants, category) for category in PERMISSION_CATEGORY_ORDER}
    return found
