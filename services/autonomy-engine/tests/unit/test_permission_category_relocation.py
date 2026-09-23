"""`PermissionCategory` moved to `nova_contracts.events.autonomy` -- Phase 4F.6,
A-4F6-2b Option A.

Moved, **not copied**. These tests pin the three things the move had to
preserve: one definition, every existing import path, and the Bible order the
permission panel renders.
"""

from __future__ import annotations

from nova_autonomy_engine.domain.models import PERMISSION_CATEGORY_ORDER
from nova_autonomy_engine.domain.models import PermissionCategory as EngineCategory
from nova_contracts.events.autonomy import PermissionCategory as ContractCategory


def test_there_is_exactly_one_permission_category_type() -> None:
    """The engine's name for it must be this very object, not a lookalike with
    the same members -- a lookalike would compare unequal the moment one side
    gained a member the other lacked."""
    assert EngineCategory is ContractCategory


def test_the_existing_import_path_still_resolves() -> None:
    """Sixteen files in this engine import it from `domain.models`. The
    re-export -- the same one `RiskLevel` already uses -- is what keeps every one
    of them unchanged."""
    import nova_autonomy_engine.domain.models as models

    assert "PermissionCategory" in models.__all__
    assert models.PermissionCategory is ContractCategory


def test_the_pinned_bible_order_still_covers_every_member() -> None:
    assert list(PERMISSION_CATEGORY_ORDER) == list(ContractCategory)
