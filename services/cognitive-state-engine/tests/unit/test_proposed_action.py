"""`ProposedAction` -- Phase 4F.6, A-4F6-2a (TDD 4F.6 §4.7, §19 rows 1 and 19).

**All-or-nothing is the property under test.** A thought either carries a
complete proposal or none at all; there is no representable half-proposal a
later stage would have to fill in by guessing.

*(Phase 4F.P, A-4FP-4 -- TDD 4F.P §30.2: `operation` and `parameters` join
all-or-nothing, so the required fields are eight, not six. The exact forms of
both are tested at the end of this module.)*
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

REQUIRED = [
    "category",
    "risk",
    "action_type",
    "execution_target",
    "verification_method",
    "title",
    "operation",
    "parameters",
]


def _fields(**overrides: object) -> dict:
    fields: dict = {
        "category": "create",
        "risk": "low",
        "action_type": "filesystem",
        "execution_target": "filesystem",
        "verification_method": "none",
        "title": "rotate the scratch directory",
        "operation": "list",
        "parameters": {},
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


def test_the_required_fields_are_exactly_the_ratified_eight() -> None:
    """**Retargeted by Phase 4F.P, not retired** -- A-4FP-4 amends A-4F6-2a's
    six required fields to eight.

    *(This test was `test_the_required_fields_are_exactly_the_ratified_six`,
    with the same body over `REQUIRED`'s original six: `category`, `risk`,
    `action_type`, `execution_target`, `verification_method`, `title`.
    Preserved per protocol §0.3.4.)*"""
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


# --- Phase 4F.P, A-4FP-4: `operation` and `parameters` --------------------------


def test_operation_is_accepted_in_its_exact_form() -> None:
    assert ProposedAction.model_validate(_fields(operation="list")).operation == "list"


@pytest.mark.parametrize("operation", ["", " list", "list ", "\tlist", "List", "LIST"])
def test_operation_must_be_non_empty_unpadded_and_lower_case(operation: str) -> None:
    """Refused, never normalised: `action-engine` classifies risk from the
    stripped, lower-cased operation but hands the adapter the raw string, so a
    padded or upper-case value would be classified as one operation and run as
    another."""
    with pytest.raises(ValidationError, match="A-4FP-4"):
        ProposedAction.model_validate(_fields(operation=operation))


def test_empty_parameters_are_allowed_when_given_explicitly() -> None:
    assert ProposedAction.model_validate(_fields(parameters={})).parameters == {}


def test_parameters_have_no_default() -> None:
    """A-4FP-4: never defaulted to `{}` -- absent is invalid, not empty."""
    assert ProposedAction.model_fields["parameters"].is_required()
    fields = _fields()
    del fields["parameters"]
    with pytest.raises(ValidationError):
        ProposedAction.model_validate(fields)


def test_parameters_may_never_name_the_operation() -> None:
    """**TDD 4F.P NP-5.** `autonomy-engine` builds `{"operation": operation,
    **parameters}`; a second `"operation"` here would override the one risk was
    classified from."""
    with pytest.raises(ValidationError, match='"operation"'):
        ProposedAction.model_validate(_fields(parameters={"operation": "delete"}))
    with pytest.raises(ValidationError, match='"operation"'):
        ProposedAction.model_validate(_fields(parameters={"path": "notes", "operation": "list"}))


def test_parameters_are_a_json_object() -> None:
    assert ProposedAction.model_validate(
        _fields(parameters={"path": "notes", "depth": 1, "all": True, "tags": ["a"]})
    ).parameters == {"path": "notes", "depth": 1, "all": True, "tags": ["a"]}
    for not_an_object in (["path"], "path", 1, None):
        with pytest.raises(ValidationError):
            ProposedAction.model_validate(_fields(parameters=not_an_object))


def test_a_thought_refuses_a_proposal_whose_parameters_name_the_operation() -> None:
    with pytest.raises(ValidationError):
        _thought(proposed_action=_fields(parameters={"operation": "list"}))
