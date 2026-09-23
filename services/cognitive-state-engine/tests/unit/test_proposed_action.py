"""`ProposedAction` -- Phase 4F.6, A-4F6-2a (TDD 4F.6 §4.7, §19 rows 1 and 19).

**All-or-nothing is the property under test.** A thought either carries a
complete proposal or none at all; there is no representable half-proposal a
later stage would have to fill in by guessing.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import nova_cognitive_state_engine
import pytest
from nova_cognitive_state_engine.domain import models
from nova_cognitive_state_engine.domain.models import (
    ActiveThought,
    AttentionLayer,
    ProposedAction,
)
from nova_contracts.events.autonomy import PermissionCategory
from nova_contracts.events.planning import RiskLevel
from pydantic import ValidationError

REQUIRED = ["category", "risk", "action_type", "execution_target", "verification_method", "title"]


def _fields(**overrides: object) -> dict:
    fields: dict = {
        "category": "create",
        "risk": "low",
        "action_type": "filesystem",
        "execution_target": "filesystem",
        "verification_method": "none",
        "title": "rotate the scratch directory",
    }
    fields.update(overrides)
    return fields


def _thought(**overrides: object) -> ActiveThought:
    moment = datetime.now(UTC)
    fields: dict = {
        "thought_id": uuid4(),
        "user_id": uuid4(),
        "description": "Keep the scratch directory bounded.",
        "priority": 2,
        "confidence": 0.7,
        "current_progress": 0.1,
        "attention_layer": AttentionLayer.ACTIVE,
        "created_at": moment,
        "updated_at": moment,
    }
    fields.update(overrides)
    return ActiveThought(**fields)


def test_the_required_fields_are_exactly_the_ratified_six() -> None:
    required = sorted(name for name, f in ProposedAction.model_fields.items() if f.is_required())
    assert required == sorted(REQUIRED)


@pytest.mark.parametrize("missing", REQUIRED)
def test_an_incomplete_proposal_is_invalid_at_the_model_boundary(missing: str) -> None:
    """**§19 row 1.** Incomplete is invalid -- not stored, not defaulted."""
    fields = _fields()
    del fields[missing]
    with pytest.raises(ValidationError):
        ProposedAction.model_validate(fields)


@pytest.mark.parametrize("field", ["execution_target", "verification_method", "title"])
def test_required_strings_may_not_be_empty(field: str) -> None:
    with pytest.raises(ValidationError):
        ProposedAction.model_validate(_fields(**{field: ""}))


def test_detail_is_the_only_optional_field() -> None:
    assert ProposedAction.model_validate(_fields()).detail == ""


def test_values_are_neither_guessed_nor_coerced() -> None:
    """An action type `action-engine` cannot run, and a category outside the
    Bible's ten, are refused rather than mapped to something nearby."""
    with pytest.raises(ValidationError):
        ProposedAction.model_validate(_fields(action_type="deploy"))
    with pytest.raises(ValidationError):
        ProposedAction.model_validate(_fields(category="administer"))
    with pytest.raises(ValidationError):
        ProposedAction.model_validate(_fields(risk="medium"))


def test_a_thought_without_a_proposal_carries_none_not_a_default() -> None:
    assert _thought().proposed_action is None


def test_a_thought_accepts_a_complete_proposal() -> None:
    thought = _thought(proposed_action=_fields())
    assert thought.proposed_action is not None
    assert thought.proposed_action.category is PermissionCategory.CREATE
    assert thought.proposed_action.risk is RiskLevel.LOW


def test_a_thought_refuses_a_partial_proposal() -> None:
    partial = _fields()
    del partial["risk"]
    with pytest.raises(ValidationError):
        _thought(proposed_action=partial)


def test_risk_is_authored_not_derived_from_the_thoughts_own_signals() -> None:
    """A thought at maximal confidence and priority still carries exactly the
    risk its proposal names -- nothing on `ActiveThought` feeds into it."""
    thought = _thought(
        priority=99, confidence=1.0, current_progress=1.0, proposed_action=_fields(risk="high")
    )
    assert thought.proposed_action is not None
    assert thought.proposed_action.risk is RiskLevel.HIGH


# --- §19 row 19: one PermissionCategory, no duplicate here ---------------------


def test_the_category_type_is_the_contracts_own() -> None:
    assert models.PermissionCategory is PermissionCategory
    assert ProposedAction.model_fields["category"].annotation is PermissionCategory


def test_no_permission_category_is_defined_in_this_engine() -> None:
    """**A-4F6-2b Option A**: no second `PermissionCategory` type -- asserted on
    the AST, so a lookalike under any import alias still fails."""
    root = Path(nova_cognitive_state_engine.__file__).parent
    for path in root.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            assert not (isinstance(node, ast.ClassDef) and node.name == "PermissionCategory"), path
