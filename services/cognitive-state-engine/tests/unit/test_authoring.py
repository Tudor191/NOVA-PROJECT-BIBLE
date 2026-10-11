"""The closed `ProposedAction` authoring table -- Phase 4F.P, A-4FP-3 (TDD 4F.P
§30.2).

**This module pins the table.** Adding an entry, or changing any value of T1, is
a new ratification, and it fails here first. Rule 1 (authored risk ≥
`action-engine`'s classification) is asserted in
`tests/contract/test_authoring_risk_drift.py`, which reads `action-engine`'s
source as text; rule 2 (no observation-derived value in `parameters`) is
asserted here.
"""

from __future__ import annotations

import dataclasses
import inspect
from types import MappingProxyType

import pytest
from nova_cognitive_state_engine.domain.authoring import (
    AUTHORING_TABLE,
    T1,
    WORKSPACE_OBSERVATION,
    AuthoringEntry,
    entry_for,
)
from nova_cognitive_state_engine.domain.models import ProposedAction
from nova_contracts.events.autonomy import PermissionCategory
from nova_contracts.events.planning import RiskLevel
from pydantic import JsonValue

A_PATH_LIKE_LABEL = "/home/someone/private/project-x"
"""Not what `perception-engine` sends -- its `label` is a final path segment --
but the worst a label could carry, which is exactly why rule 2 must be
structural."""


def test_the_table_is_exactly_one_entry_for_the_one_ingestion_input() -> None:
    assert WORKSPACE_OBSERVATION == "perception.workspace.observed"
    assert dict(AUTHORING_TABLE) == {WORKSPACE_OBSERVATION: T1}


def test_the_table_is_read_only_at_runtime() -> None:
    assert isinstance(AUTHORING_TABLE, MappingProxyType)
    with pytest.raises(TypeError):
        AUTHORING_TABLE["perception.presence.observed"] = T1  # type: ignore[index]


def test_t1_is_the_ratified_row_value_for_value() -> None:
    """A-4FP-3's T1 table, every cell."""
    assert T1.category is PermissionCategory.READ
    assert T1.risk is RiskLevel.LOW
    assert T1.action_type == "filesystem"
    assert T1.execution_target == "filesystem"
    assert T1.operation == "list"
    assert dict(T1.parameters) == {}
    assert T1.verification_method == "adapter_success"
    assert T1.title_template == "Review the workspace after activity in {label}"
    assert T1.detail == "NOVA noticed activity in the watched workspace and proposes listing it."
    assert T1.description_template == "Activity observed in {label}"


def test_an_entry_cannot_be_edited_at_runtime() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        T1.operation = "delete"  # type: ignore[misc]
    assert isinstance(T1.parameters, MappingProxyType)
    with pytest.raises(TypeError):
        T1.parameters["path"] = "/"  # type: ignore[index]


def test_an_input_kind_with_no_entry_yields_no_proposal() -> None:
    """A-4FP-3: never a default entry."""
    assert entry_for("perception.presence.observed") is None
    assert entry_for("") is None
    assert entry_for(WORKSPACE_OBSERVATION) is T1


def test_author_produces_the_complete_proposal() -> None:
    proposal = T1.author(label="nova")
    assert proposal == ProposedAction(
        category=PermissionCategory.READ,
        risk=RiskLevel.LOW,
        action_type="filesystem",
        execution_target="filesystem",
        operation="list",
        parameters={},
        verification_method="adapter_success",
        title="Review the workspace after activity in nova",
        detail="NOVA noticed activity in the watched workspace and proposes listing it.",
    )


def test_the_description_is_the_ratified_template() -> None:
    assert T1.describe(label="nova") == "Activity observed in nova"


def test_every_entry_authors_a_valid_eight_field_proposal() -> None:
    """Each entry must pass `ProposedAction`'s own validation -- `operation`'s
    exact form and `parameters` without `"operation"` included."""
    for entry in AUTHORING_TABLE.values():
        proposal = entry.author(label="nova")
        assert isinstance(proposal, ProposedAction)
        assert proposal.operation == entry.operation
        assert "operation" not in proposal.parameters


# --- Rule 2: no observation-derived value in `parameters` (TDD 4F.P FP-9, NP-13) --------


def test_author_takes_the_label_and_nothing_else() -> None:
    """Structural: there is no argument through which a path, an `object_id` or
    any other observation field could reach a proposal."""
    parameters = inspect.signature(AuthoringEntry.author).parameters
    assert [name for name in parameters if name != "self"] == ["label"]
    assert parameters["label"].kind is inspect.Parameter.KEYWORD_ONLY


def test_the_label_reaches_the_title_and_never_the_parameters() -> None:
    proposal = T1.author(label=A_PATH_LIKE_LABEL)
    assert proposal.parameters == {}
    fields = proposal.model_dump(mode="json")
    carrying = sorted(name for name, value in fields.items() if A_PATH_LIKE_LABEL in str(value))
    assert carrying == ["title"]


def _strings(value: JsonValue) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for key, item in value.items() for s in [key, *_strings(item)]]
    if isinstance(value, list):
        return [s for item in value for s in _strings(item)]
    return []


def test_no_entry_carries_an_absolute_path_or_a_template_in_its_parameters() -> None:
    for kind, entry in AUTHORING_TABLE.items():
        for text in _strings(dict(entry.parameters)):
            assert not text.startswith(("/", "\\", "~")), (kind, text)
            assert not (len(text) > 1 and text[1] == ":"), (kind, text)
            assert "{" not in text, (kind, text)


def test_each_authored_proposal_has_its_own_parameters() -> None:
    """Mutating one proposal's `parameters` cannot reach the table or another
    proposal."""
    first = T1.author(label="a")
    first.parameters["path"] = "/"
    assert dict(T1.parameters) == {}
    assert T1.author(label="b").parameters == {}
