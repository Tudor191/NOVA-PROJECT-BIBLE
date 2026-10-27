"""A-4FP-3 rule 1 -- **authored risk ≥ `action-engine`'s classification** --
Phase 4F.P (TDD 4F.P §30.2, FP-10, NP-6).

Every entry of the closed authoring table must carry a `risk` no lower than
what `action-engine`'s `classify_risk(action_type, operation)` returns, in the
order `nova_contracts`' `RiskLevel` declares. Otherwise `autonomy-engine`'s
policy gate could admit an action at a tier `action-engine` rates higher.

**Read as text, never imported.** ADR-004 and control 7 forbid this engine --
tests included -- from importing `action-engine`. So this module parses
`action-engine/domain/risk.py` with `ast` and **interprets** the classifier it
finds. It accepts exactly the structure that file has today:

* module-level `NAME = frozenset({<string literals>})`;
* `def classify_risk(*, action_type, operation)` whose first statement is
  `op = operation.strip().lower()`;
* then only `if <condition>: return RiskLevel.<MEMBER>`, where a condition is
  `op in NAME`, `op in {<string literals>}`, `action_type == "<literal>"`, or an
  `and` of those;
* and a final `return RiskLevel.<MEMBER>`.

**Anything else fails the test** ("fails if it cannot recognise that file's
structure", A-4FP-3): a classifier that grows a branch this interpreter cannot
read must be re-checked by a person, not skipped.
"""

from __future__ import annotations

import ast
import dataclasses
from collections.abc import Callable
from pathlib import Path

import pytest
from nova_cognitive_state_engine.domain.authoring import AUTHORING_TABLE, T1, AuthoringEntry
from nova_contracts.events.planning import RiskLevel

_REPO_ROOT = Path(__file__).resolve().parents[4]
_RISK_PY = (
    _REPO_ROOT / "services" / "action-engine" / "src" / "nova_action_engine" / "domain" / "risk.py"
)

Classifier = Callable[[str, str], RiskLevel]


class UnrecognisedClassifierError(AssertionError):
    """`risk.py` no longer has the structure this interpreter reads. Re-check
    rule 1 by hand and extend the parser; never delete this test."""


def _string_set(node: ast.expr, sets: dict[str, frozenset[str]]) -> frozenset[str]:
    if isinstance(node, ast.Name) and node.id in sets:
        return sets[node.id]
    if isinstance(node, ast.Set) and all(
        isinstance(element, ast.Constant) and isinstance(element.value, str)
        for element in node.elts
    ):
        return frozenset(element.value for element in node.elts)  # type: ignore[attr-defined]
    raise UnrecognisedClassifierError(f"unrecognised set expression: {ast.unparse(node)}")


def _predicate(node: ast.expr, sets: dict[str, frozenset[str]]) -> Callable[[str, str], bool]:
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
        parts = [_predicate(value, sets) for value in node.values]
        return lambda action_type, op: all(part(action_type, op) for part in parts)
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and len(node.comparators) == 1:
        left, operator, right = node.left, node.ops[0], node.comparators[0]
        if isinstance(left, ast.Name) and left.id == "op" and isinstance(operator, ast.In):
            members = _string_set(right, sets)
            return lambda action_type, op: op in members
        if (
            isinstance(left, ast.Name)
            and left.id == "action_type"
            and isinstance(operator, ast.Eq)
            and isinstance(right, ast.Constant)
            and isinstance(right.value, str)
        ):
            literal = right.value
            return lambda action_type, op: action_type == literal
    raise UnrecognisedClassifierError(f"unrecognised condition: {ast.unparse(node)}")


def _risk_member(node: ast.stmt) -> RiskLevel:
    if (
        isinstance(node, ast.Return)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "RiskLevel"
        and node.value.attr in RiskLevel.__members__
    ):
        return RiskLevel[node.value.attr]
    raise UnrecognisedClassifierError(f"unrecognised return: {ast.unparse(node)}")


def interpret_classifier(source: str) -> Classifier:
    """`classify_risk`, rebuilt from `risk.py`'s text."""
    tree = ast.parse(source)
    sets: dict[str, frozenset[str]] = {}
    function: ast.FunctionDef | None = None
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "frozenset"
            and len(node.value.args) == 1
        ):
            sets[node.targets[0].id] = _string_set(node.value.args[0], {})
        elif isinstance(node, ast.FunctionDef) and node.name == "classify_risk":
            function = node
    if function is None:
        raise UnrecognisedClassifierError("no `classify_risk` function")

    arguments = [argument.arg for argument in function.args.kwonlyargs]
    if arguments != ["action_type", "operation"] or function.args.args:
        raise UnrecognisedClassifierError(f"unexpected signature: {arguments}")

    body = list(function.body)
    if not body or ast.unparse(body[0]) != "op = operation.strip().lower()":
        raise UnrecognisedClassifierError("the first statement is not the operation normalisation")

    branches: list[tuple[Callable[[str, str], bool], RiskLevel]] = []
    for statement in body[1:-1]:
        if not (
            isinstance(statement, ast.If) and not statement.orelse and len(statement.body) == 1
        ):
            raise UnrecognisedClassifierError(f"unrecognised statement: {ast.unparse(statement)}")
        branches.append((_predicate(statement.test, sets), _risk_member(statement.body[0])))
    fallback = _risk_member(body[-1])
    if not branches:
        raise UnrecognisedClassifierError("no branches: the classifier would be vacuous")

    def classify(action_type: str, operation: str) -> RiskLevel:
        op = operation.strip().lower()
        for matches, level in branches:
            if matches(action_type, op):
                return level
        return fallback

    return classify


def _order(level: RiskLevel) -> int:
    return list(RiskLevel).index(level)


def violations(table: dict[str, AuthoringEntry], classify: Classifier) -> list[str]:
    return [
        f"{kind}: authored {entry.risk.value} < classified "
        f"{classify(entry.action_type, entry.operation).value}"
        for kind, entry in table.items()
        if _order(entry.risk) < _order(classify(entry.action_type, entry.operation))
    ]


@pytest.fixture(scope="module")
def classify() -> Classifier:
    return interpret_classifier(_RISK_PY.read_text(encoding="utf-8"))


# --- the rule ------------------------------------------------------------------------------


def test_rule_1_no_entry_is_authored_below_action_engines_classification(
    classify: Classifier,
) -> None:
    assert violations(dict(AUTHORING_TABLE), classify) == []


def test_t1_is_classified_negligible_and_authored_low(classify: Classifier) -> None:
    """The ratified reading of T1 (A-4FP-3, A-4FP-11): `list` is classified
    `negligible`, and T1 is authored one tier above it."""
    assert classify(T1.action_type, T1.operation) is RiskLevel.NEGLIGIBLE
    assert T1.risk is RiskLevel.LOW


def test_the_order_is_the_one_risk_level_declares() -> None:
    assert list(RiskLevel) == [
        RiskLevel.NEGLIGIBLE,
        RiskLevel.LOW,
        RiskLevel.MODERATE,
        RiskLevel.HIGH,
        RiskLevel.CRITICAL,
    ]


# --- anti-vacuity: the interpreter reads the real classifier -------------------------------


@pytest.mark.parametrize(
    ("action_type", "operation", "expected"),
    [
        ("filesystem", "delete", RiskLevel.CRITICAL),
        ("filesystem", " Format ", RiskLevel.CRITICAL),
        ("terminal", "execute", RiskLevel.HIGH),
        ("filesystem", "execute", RiskLevel.LOW),
        ("filesystem", "write", RiskLevel.MODERATE),
        ("filesystem", "list", RiskLevel.NEGLIGIBLE),
        ("git", "status", RiskLevel.NEGLIGIBLE),
        ("filesystem", "frobnicate", RiskLevel.LOW),
    ],
)
def test_the_interpreted_classifier_matches_action_engines_documented_tiers(
    classify: Classifier, action_type: str, operation: str, expected: RiskLevel
) -> None:
    assert classify(action_type, operation) is expected


def test_negative_control_np6_an_entry_below_its_classification_is_caught(
    classify: Classifier,
) -> None:
    """TDD 4F.P NP-6: T1 re-authored as `write` at `low` -- classified
    `moderate` -- is a violation."""
    drifted = dataclasses.replace(T1, operation="write")
    assert violations({"drifted": drifted}, classify) == [
        "drifted: authored low < classified moderate"
    ]


@pytest.mark.parametrize(
    "mutation",
    [
        # a `match` statement instead of the `if` chain
        (
            "    if op in _CRITICAL_OPERATIONS:\n        return RiskLevel.CRITICAL\n",
            "    match op:\n        case 'delete':\n            return RiskLevel.CRITICAL\n",
        ),
        # a helper call the interpreter cannot evaluate
        ("    op = operation.strip().lower()\n", "    op = _normalise(operation)\n"),
        # an `or` condition
        (
            'if action_type == "terminal" and op in _HIGH_RISK_OPERATIONS',
            'if action_type == "terminal" or op in _HIGH_RISK_OPERATIONS',
        ),
    ],
)
def test_negative_control_an_unrecognised_structure_fails_rather_than_passing(
    mutation: tuple[str, str],
) -> None:
    """A-4FP-3: the test **fails if it cannot recognise** `risk.py`."""
    source = _RISK_PY.read_text(encoding="utf-8")
    old, new = mutation
    assert old in source, "the mutation no longer applies; update this control"
    with pytest.raises(UnrecognisedClassifierError):
        interpret_classifier(source.replace(old, new))
