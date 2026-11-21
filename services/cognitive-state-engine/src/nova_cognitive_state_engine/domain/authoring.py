"""The closed `ProposedAction` authoring table -- Phase 4F.P, **A-4FP-3**
(TDD 4F.P §30.2).

**Every proposal this engine produces comes from this table, and from nowhere
else.** Nothing about a proposal is derived at runtime: every field is a
ratified constant of its entry, except `title`, which is a ratified template
filled with the observation's `label`. That is what keeps the values every
downstream gate is evaluated against -- the permission category, the risk tier,
the operation `action-engine` classifies -- out of reach of whatever an
observation happens to contain.

**Closed, and ratified entry by entry.** The table is keyed by ingestion input
kind. An input kind with no entry yields **no** proposal, and a thought without
one never triggers (A-4F6-2a rule 2). Adding an entry is a new ratification,
not a code change: `tests/unit/test_authoring.py` pins the table's exact
contents.

**Two binding rules, for every entry now and later:**

1. **Authored risk ≥ classified risk.** An entry's `risk` is never below
   `action-engine`'s own `classify_risk(action_type, operation)`, in the order
   `nova_contracts`' `RiskLevel` declares. Otherwise the policy gate could admit
   an action `action-engine` rates higher (TDD 4F.P FP-10). Enforced by
   `tests/contract/test_authoring_risk_drift.py`, which reads `action-engine`'s
   `risk.py` as text -- ADR-004 forbids importing it.
2. **No raw path, and no value from the observation in `parameters`.**
   Parameters are constants of the entry. The observation's `label` -- its final
   path segment, already public in the World Model -- may appear only in the
   `title` and in the thought's `description` (TDD 4F.P FP-9; D-4F3-2 keeps the
   raw path inside `perception-engine`). `author` takes the label and nothing
   else, so this is structural rather than a convention.

**One entry, T1**, for `perception.workspace.observed`. It proposes listing the
capability's sandbox root: read-only, authored `low`, classified `negligible` by
`action-engine`, and executable by the bootstrap-installed `filesystem`
capability. `execution_target` is that **capability's name**, the value
`action-engine` resolves at stage 5 (A-4FP-5).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from nova_contracts.events.action import ActionType
from nova_contracts.events.autonomy import PermissionCategory
from nova_contracts.events.planning import RiskLevel
from pydantic import JsonValue

from nova_cognitive_state_engine.domain.models import ProposedAction

__all__ = ["AUTHORING_TABLE", "T1", "WORKSPACE_OBSERVATION", "AuthoringEntry", "entry_for"]

WORKSPACE_OBSERVATION = "perception.workspace.observed"
"""The one ingestion input kind 4F.P admits (A-4FP-1). It is the existing,
internal Event Bus subject the observation arrives on."""


@dataclass(frozen=True)
class AuthoringEntry:
    """One ratified row of the table. Frozen, so an entry cannot be edited at
    runtime into something nobody ratified."""

    category: PermissionCategory
    risk: RiskLevel
    action_type: ActionType
    execution_target: str
    operation: str
    parameters: Mapping[str, JsonValue]
    verification_method: str
    title_template: str
    """Formatted with the observation's `label`, and nothing else."""
    detail: str
    description_template: str
    """The ingested thought's `description` (A-4FP-1), formatted with the
    `label`. Part of the entry because A-4FP-3 ratifies it alongside T1."""

    def author(self, *, label: str) -> ProposedAction:
        """The proposal for one observation. `label` reaches the `title` only;
        every other value is this entry's constant."""
        return ProposedAction(
            category=self.category,
            risk=self.risk,
            action_type=self.action_type,
            execution_target=self.execution_target,
            operation=self.operation,
            parameters=dict(self.parameters),
            verification_method=self.verification_method,
            title=self.title_template.format(label=label),
            detail=self.detail,
        )

    def describe(self, *, label: str) -> str:
        return self.description_template.format(label=label)


T1 = AuthoringEntry(
    category=PermissionCategory.READ,
    risk=RiskLevel.LOW,
    action_type="filesystem",
    execution_target="filesystem",
    operation="list",
    parameters=MappingProxyType({}),
    verification_method="adapter_success",
    title_template="Review the workspace after activity in {label}",
    detail="NOVA noticed activity in the watched workspace and proposes listing it.",
    description_template="Activity observed in {label}",
)
"""**T1** -- A-4FP-3's one ratified entry, value for value (TDD 4F.P §30.2).

`parameters={}`: the `filesystem` adapter's `list` without a `path` lists the
capability's configured sandbox root, so no path from the observation is ever
needed. `verification_method="adapter_success"` names what `action-engine`'s
stage 10 does: a successful adapter invocation is itself treated as satisfying
verification."""

AUTHORING_TABLE: Mapping[str, AuthoringEntry] = MappingProxyType({WORKSPACE_OBSERVATION: T1})
"""The closed table. Read-only at runtime."""


def entry_for(input_kind: str) -> AuthoringEntry | None:
    """The ratified entry for an input kind, or `None`. `None` means no
    proposal, and a thought without one never triggers -- never a default."""
    return AUTHORING_TABLE.get(input_kind)
