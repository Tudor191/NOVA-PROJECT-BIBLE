"""TDD 4F §6.2's prohibitions, asserted over this engine's own source.

`cognitive-state-engine` **proposes and never acts**. §6.2 names eight things it
must not do, and control 11 of §16 requires them enforced by property rather
than by convention. 4F.1 builds the domain and persistence, so the subset
checkable now is checked now -- the rest arrive with the code they constrain
(4F.6 for the trigger, 4F.7 for the panel).

**Comments and docstrings are stripped before every source scan.** This module's
own prose names `action.execute` and `action-engine` repeatedly, and a
substring check that could not tell a citation from a call would force the code
to stop explaining itself. That is Phase 4D's recorded precision failure,
avoided here by construction rather than rediscovered.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from nova_cognitive_state_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_cognitive_state_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS

SRC = Path(__file__).resolve().parents[2] / "src" / "nova_cognitive_state_engine"


def _modules() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def _code_only(path: Path) -> str:
    """The module with every docstring removed, unparsed back to source.

    AST-based rather than regex: it removes exactly the string expressions
    Python treats as docstrings and nothing else, so prose cannot trip a
    control and a real call cannot hide inside a string that looks like prose.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        body = node.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def test_there_is_source_to_scan() -> None:
    """Anti-vacuity: every check below passes trivially against an empty tree."""
    modules = _modules()
    assert len(modules) >= 8, f"expected a populated package, found {len(modules)} modules"


def test_control_11_this_engine_publishes_the_trigger_and_nothing_else() -> None:
    """**Retargeted by Phase 4F.6, not retired** -- TDD 4F D-4F-9 (4F.6 §14),
    replacement property from TDD 4F.6 §3.1: *publishes
    `autonomy.decision.requested` and nothing else.*

    The structural half of §6.2's *must not publish `action.execute`* is
    preserved exactly: `BoundEventBus` checks this set on `publish()` and
    `request()`, and `action.execute` is not in it, so there is still no subject
    at which an execution request could be emitted. Asserted explicitly below
    rather than left implied by the equality.

    *(This test was `test_control_11_this_engine_publishes_nothing`, asserting
    `frozenset() == PUBLISHABLE_SUBJECTS`, with the docstring: "D-4F-6: no
    cognitive-state Event Bus subject, in 4F.1 or later. An empty publish
    allow-list is also the structural half of §6.2's *must not publish
    `action.execute`*: there is no subject at which one could be emitted."
    D-4F-6 still holds -- the trigger publishes no cognitive state. Preserved
    per protocol §0.3.4.)*"""
    assert frozenset({"autonomy.decision.requested"}) == PUBLISHABLE_SUBJECTS
    assert "action.execute" not in PUBLISHABLE_SUBJECTS


def test_the_subscribe_allow_list_is_exactly_the_two_ratified_subjects() -> None:
    """**Retargeted again by Phase 4F.P, not retired** -- TDD 4F.P §30.2
    **A-4FP-1** (4F.7's P-11): the allow-list is exactly
    `{perception.sensor.health_changed, perception.workspace.observed}`. The
    second is an existing, **internal** subject, consumed by
    `make_workspace_observation_handler` for thought ingestion -- so the
    subject still arrives with its handler. Exact equality stays, so a third
    subject fails as loudly as before, and still no `autonomy.*` subject is
    subscribable.

    *(Until 4F.P this test was
    `test_the_subscribe_allow_list_is_exactly_the_sensor_health_subject`,
    asserting `frozenset({"perception.sensor.health_changed"}) ==
    SUBSCRIBABLE_SUBJECTS`, with the docstring below. Its "nothing here is a
    thought-ingestion input (that is 4F.P's, RS-2b)" is superseded by
    A-4FP-1. Preserved per protocol §0.3.4.)*

    **Retargeted by Phase 4F.7, not retired** -- TDD 4F §24.4 **RS-3a**: this
    engine's subscribe allow-list changes *"from empty to exactly this existing
    subject"*. The subject arrives with its handler (`events/handlers.py`), so
    the original property -- no subscription without a consumer -- still holds.

    Exact equality, so a second subject fails as loudly as the empty set now
    would. No `autonomy.*` subject is subscribable, and nothing here is a
    thought-ingestion input (that is 4F.P's, RS-2b).

    *(This test was `test_the_subscribe_allow_list_is_empty_until_a_handler_exists`,
    asserting `frozenset() == SUBSCRIBABLE_SUBJECTS`, with the docstring: "A
    subscription without a consumer is the dead topic `ws-gateway`'s own
    docstring warns about. Subjects arrive in 4F.6 with their handlers." 4F.6
    added none. Preserved per protocol §0.3.4.)*"""
    assert (
        frozenset({"perception.sensor.health_changed", "perception.workspace.observed"})
        == SUBSCRIBABLE_SUBJECTS
    )
    assert not any(subject.startswith("autonomy.") for subject in SUBSCRIBABLE_SUBJECTS)


def test_control_11_no_module_names_action_execute_in_executable_code() -> None:
    for path in _modules():
        assert "action.execute" not in _code_only(path), (
            f"{path.name} references action.execute in executable code; TDD 4F §6.2 "
            "forbids this engine from publishing it"
        )


@pytest.mark.parametrize(
    "forbidden",
    ["nova_action_engine", "nova_autonomy_engine", "nova_perception_engine", "nova_memory_engine"],
)
def test_control_7_no_cross_engine_import(forbidden: str) -> None:
    """ADR-004 plus import-linter's own contracts. Asserted here too so the
    failure names the boundary rather than a contract number."""
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden), f"{path.name} imports {forbidden}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(forbidden), f"{path.name} imports {forbidden}"


def test_control_7_no_http_client_reaches_another_engine() -> None:
    """ADR-004: *"never a raw HTTP call from one engine's code straight into
    another engine's module"*. This engine has no HTTP client at all."""
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                root = name.split(".")[0]
                assert root not in {"httpx", "aiohttp", "requests", "urllib3"}, (
                    f"{path.name} imports {root}; 4F adds no engine-to-engine HTTP"
                )


_FOREIGN_SCHEMAS = ("autonomy.", "action.", "memory.", "digital_twin.", "perception.")

_SCHEMA_REFERENCE = re.compile(
    r"(?<![\w.-])(?:autonomy|action|memory|digital_twin|perception)(?:\.[A-Za-z_][A-Za-z0-9_]*)+"
)
"""A **schema reference** (A-4F7-6 (a): *"scope it to schema references"*): a
dotted name that begins with another engine's schema, anywhere in a string
literal -- alone (`"autonomy.decision_log"`), or inside SQL or a message
(`"SELECT … FROM action.action"`). Not preceded by a word character, a dot or a
hyphen, so `nova_contracts.events.autonomy` and `autonomy-engine` are not
references."""

_RATIFIED_SUBJECT_STRINGS = frozenset(
    {
        "autonomy.decision.requested",  # published (TDD 4F.6)
        "perception.sensor.health_changed",  # subscribed (RS-3a)
        "perception.workspace.observed",  # subscribed (A-4FP-1)
    }
)
"""**Exactly** the three schema references this engine's code may contain -- TDD
4F.P §30.2 A-4FP-10, adopting A-4F7-6 (a)'s repair. Each is an Event Bus subject
this engine's allow-lists name, never a table."""


def _string_constants(source: str) -> list[str]:
    """Every string literal in the module's executable code. **Prose is
    excluded**: every bare string statement -- a module, class or function
    docstring, and an attribute docstring after an assignment -- is never
    evaluated as a value, so a citation of a schema there cannot trip the
    control."""
    tree = ast.parse(source)
    prose = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in prose
    ]


def _schema_references(source: str) -> set[str]:
    return {
        reference
        for value in _string_constants(source)
        for reference in _SCHEMA_REFERENCE.findall(value)
    }


def _foreign_schema_strings(source: str) -> set[str]:
    return _schema_references(source) - _RATIFIED_SUBJECT_STRINGS


def test_control_11_the_only_repository_this_engine_writes_is_its_own() -> None:
    """**Repaired by Phase 4F.P, not retired** -- TDD 4F.P §30.2 **A-4FP-10**,
    adopting A-4F7-6 (a) (F-4F7-1). The check now inspects `ast.Constant`
    strings, scoped to schema references, and permits **exactly** the three
    ratified subject strings; any other reference to another engine's schema,
    in any string literal, fails. The negative controls below prove it can
    fail.

    *(Until 4F.P this test asserted, for every module, that
    `f'"{schema}'` was not in `_code_only(path)`, with the docstring: "§10:
    cognitive state reads other engines' facts over the bus and owns none of
    them. No module may name another engine's schema." That check was vacuous:
    `ast.unparse` renders every string with single quotes, so a double-quoted
    pattern never matched (F-4F7-1). The property is unchanged. Preserved per
    protocol §0.3.4.)*"""
    for path in _modules():
        found = _foreign_schema_strings(path.read_text(encoding="utf-8"))
        assert not found, f"{path.name} names another engine's schema in code: {sorted(found)}"


def test_control_11_is_not_vacuous_it_sees_the_permitted_subjects() -> None:
    """Anti-vacuity: the three permitted strings are really in this engine's
    code, and the scanner really reads them."""
    seen = set().union(
        *(_schema_references(path.read_text(encoding="utf-8")) for path in _modules())
    )
    assert seen == _RATIFIED_SUBJECT_STRINGS


@pytest.mark.parametrize(
    "literal",
    [
        "perception.sensor_registration",  # A-4F7-6 (a)'s named control
        "autonomy.decision_log",
        "action.action",
        "memory.long_term",
        "digital_twin.snapshot",
        "perception.workspace.observed.extra",
    ],
)
def test_control_11_negative_control_a_foreign_schema_literal_fails(literal: str) -> None:
    for quoting in (
        f'X = "{literal}"',
        f"X = '{literal}'",
        f'f(table="{literal}")',
        f'X = "SELECT * FROM {literal} WHERE id = 1"',
        f'X = f"{{prefix}} {literal}"',
    ):
        assert _foreign_schema_strings(quoting) == {literal}, quoting


def test_control_11_permits_the_ratified_subjects_inside_messages() -> None:
    source = 'log("autonomy.decision.requested unavailable for thought %s")\n'
    assert _schema_references(source) == {"autonomy.decision.requested"}
    assert _foreign_schema_strings(source) == set()


def test_control_11_module_paths_and_engine_names_are_not_schema_references() -> None:
    source = (
        'A = "nova_contracts.events.autonomy"\n'
        'B = "autonomy-engine"\n'
        'C = "cognitive-state-engine.events"\n'
    )
    assert _schema_references(source) == set()


def test_control_11_negative_control_prose_is_not_code() -> None:
    source = (
        '"""Reads autonomy.decision_log? Never."""\n'
        "X = 1\n"
        '"""An attribute docstring citing memory.long_term."""\n'
        "def f():\n"
        '    """Nor action.action."""\n'
        "    return 1\n"
    )
    assert _foreign_schema_strings(source) == set()
    # ... but the same text as a value is code, and fails.
    assert _foreign_schema_strings('X = "Reads autonomy.decision_log? Never."\n') == {
        "autonomy.decision_log"
    }


def test_no_actuator_or_execution_vocabulary_in_the_domain() -> None:
    """§6.2: this engine may identify an action *type* in a proposal, but 4F.1
    has no proposal yet and therefore no execution vocabulary at all. The
    domain cannot say "do this"."""
    domain = sorted((SRC / "domain").rglob("*.py"))
    assert domain, "domain package is empty"
    for path in domain:
        code = _code_only(path).lower()
        for verb in ("execute(", "invoke(", "actuator", "subprocess", "os.system"):
            assert verb not in code, f"{path.name} contains execution vocabulary: {verb!r}"
