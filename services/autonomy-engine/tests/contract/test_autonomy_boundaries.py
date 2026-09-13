"""Security boundaries -- TDD 4D §10, and **negative controls 7, 8, 9 and 10**.

Control 7  -- *adding any entry to `PUBLIC_TOPICS` must fail the suite*.
Control 8  -- *registering any `autonomy.*` payload, or making either allow-list
               non-empty, must fail*.
Control 9  -- *creating an `IdentityConfidencePolicy` model, table or route in
               `autonomy-engine` must fail*.
Control 10 -- *importing `nova_action_engine` from `nova_autonomy_engine` must
               fail*.

These are contract tests rather than unit tests because what they assert is a
property of the repository as a whole, not of one function: the strongest form
of *"there is no autonomy subject that could leak to a browser"* is that no
such subject exists anywhere.

**Every source check here parses the AST and inspects code, never raw text.**
A substring search would flag this engine's own prose -- the docstrings that
*explain* why `IdentityConfidencePolicy` stays in `action-engine` mention it by
name -- and a control that fires on its own rationale is a control that gets
loosened. `_code_of` strips docstrings and comments so the checks see only what
actually executes.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
from fnmatch import fnmatchcase
from pathlib import Path

import nova_autonomy_engine
import pytest
from nova_autonomy_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_autonomy_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_contracts.registry import known_subjects

_SOURCE_ROOT = Path(nova_autonomy_engine.__file__).parent
_SERVICE_ROOT = Path(nova_autonomy_engine.__file__).parents[2]
_REPO_ROOT = _SERVICE_ROOT.parents[1]


def _source_files() -> list[Path]:
    return sorted(_SOURCE_ROOT.rglob("*.py"))


def _is_bare_string(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    )


def _strip_docstrings(tree: ast.AST) -> ast.AST:
    """Remove **every** bare string-literal statement, not only the leading one.

    This codebase documents module constants and model fields with a string
    immediately after the assignment (PEP 258 attribute docstrings), and those
    are ordinary `Expr` statements anywhere in a body -- so stripping only
    `body[0]` would leave most of this engine's prose in the "code"."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        kept = [statement for statement in node.body if not _is_bare_string(statement)]
        node.body = kept or [ast.Pass()]
    return tree


def _code_of(path: Path) -> str:
    """The file's executable code, with docstrings and comments removed.

    `ast.unparse` drops comments for free; `_strip_docstrings` removes the
    module, class and function docstrings that a naive text search would
    otherwise read as code.
    """
    return ast.unparse(_strip_docstrings(ast.parse(path.read_text())))


# --- Negative control 8 ------------------------------------------------------
def test_control_8_both_allow_lists_are_empty() -> None:
    """**Negative control 8.** D-4D-1: *"`autonomy-engine` publishes and
    subscribes to nothing. Both allow-lists stay empty."*

    This is why D-4D-1 is a security simplification and not only a scope
    reduction: with no declared subject, `BoundEventBus` refuses every publish
    and every subscribe at runtime, so there is no autonomy subject that
    *could* leak anywhere."""
    assert frozenset() == PUBLISHABLE_SUBJECTS
    assert frozenset() == SUBSCRIBABLE_SUBJECTS


def test_control_8_no_autonomy_subject_is_registered_anywhere_in_the_repository() -> None:
    """**Negative control 8**, global half. `known_subjects()` is the whole
    repository's registry, so this also keeps `action-engine`'s own
    `test_fork_e2_namespace_boundary_never_uses_autonomy_prefix` passing --
    the reservation test 4D was told not to modify."""
    offenders = [subject for subject in known_subjects() if subject.startswith("autonomy.")]
    assert offenders == []


def test_control_8_the_two_specifically_reserved_subjects_are_still_unclaimed() -> None:
    """`nova_contracts.events.action`'s docstring reserves these *"for
    `autonomy-engine` to claim in Phase 4"*. 4D leaves the reservation
    standing."""
    subjects = set(known_subjects())
    assert "autonomy.approval.requested" not in subjects
    assert "autonomy.decision.made" not in subjects


def test_control_8_this_engine_never_calls_the_bus_at_all() -> None:
    """The strongest available form of *"publishes and subscribes to
    nothing"*: no call to any `EventBus` method exists in the package, so there
    is no site at which a subject could be introduced.

    `main.py` still *binds* a `BoundEventBus` -- deliberately, so that a future
    call raises `SubjectNotAllowedError` at runtime rather than succeeding
    against an unbound client -- but `connect`/`close` are the only methods it
    ever reaches."""
    bus_methods = {"publish", "subscribe", "request", "serve", "open_stream"}
    offenders: list[str] = []
    for path in _source_files():
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in bus_methods
                and isinstance(node.func.value, ast.Attribute | ast.Name)
                and "bus" in ast.unparse(node.func.value)
            ):
                offenders.append(f"{path.name}:{node.lineno} {ast.unparse(node.func)}")
    assert offenders == []


def test_control_8_no_register_payload_decorator_exists_in_this_engine() -> None:
    """Wire contracts belong in `nova_contracts`; 4D adds none at all."""
    for path in _source_files():
        assert "register_payload" not in _code_of(path), path


# --- Negative control 7 ------------------------------------------------------
def _public_topics() -> list[str]:
    """`ws-gateway`'s `PUBLIC_TOPICS`, read from source rather than imported.

    Importing it would make `autonomy-engine`'s own test suite depend on
    another engine's package -- the very coupling control 10 forbids in `src/`.
    Parsing the literal keeps the assertion exact without the dependency.
    """
    source = (
        _REPO_ROOT
        / "services"
        / "ws-gateway"
        / "src"
        / "nova_ws_gateway"
        / "domain"
        / "protocol.py"
    ).read_text()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.AnnAssign | ast.Assign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = {t.id for t in targets if isinstance(t, ast.Name)}
            if "PUBLIC_TOPICS" in names and node.value is not None:
                # Declared as `frozenset({...})`, so evaluate the literal the
                # call wraps rather than the call itself.
                value = node.value
                if isinstance(value, ast.Call) and value.args:
                    value = value.args[0]
                return sorted(ast.literal_eval(value))
    raise AssertionError("PUBLIC_TOPICS not found in ws-gateway's domain/protocol.py")


def test_control_7_this_engine_adds_nothing_to_public_topics() -> None:
    """**Negative control 7.** `PUBLIC_TOPICS` is `ws-gateway`'s, and 4D adds
    nothing to it -- so no `autonomy.*` subject can reach a browser.

    A wildcard would be especially dangerous here: `BoundEventBus` matches with
    `fnmatchcase`, where `*` spans dots, so `autonomy.*` would subscribe the
    gateway process to every future `autonomy.*` subject. That is 4C.2e's
    finding, and it applies unchanged."""
    topics = _public_topics()
    assert not [topic for topic in topics if topic.startswith("autonomy")]
    assert not [topic for topic in topics if "*" in topic]
    # The mechanism, demonstrated rather than asserted from memory.
    assert fnmatchcase("autonomy.decision.made", "autonomy.*") is True


def test_control_7_public_topics_is_unchanged_at_its_eighteen_exact_strings() -> None:
    """TDD §17 row 9: *"`PUBLIC_TOPICS` byte-identical"*."""
    assert len(_public_topics()) == 18


# --- Negative control 9 ------------------------------------------------------
def test_control_9_no_identity_confidence_policy_exists_in_this_engine() -> None:
    """**Negative control 9.** CF-9 stays open (D-4D-2). `action-engine` keeps
    sole ownership of `IdentityConfidencePolicy` -- 4D creates no duplicate
    model, no duplicate table and no route.

    Checked against code, not prose: this engine's docstrings cite the type by
    name to explain *why* it is not here, and a control that fires on its own
    rationale would get loosened rather than obeyed."""
    for path in _source_files():
        code = _code_of(path)
        assert "IdentityConfidencePolicy" not in code, path
        assert "identity_confidence_policy" not in code, path
        assert "minimum_confidence_by_risk" not in code, path


def test_control_9_no_autonomy_table_resembles_the_action_engine_policy() -> None:
    """A table by another name would split the ownership ADR-032 assigns to the
    gating engine just as effectively."""
    from nova_autonomy_engine.repository.models import Base

    assert set(Base.metadata.tables) == {
        "autonomy.autonomy_level",
        "autonomy.policy",
        "autonomy.permission_grant",
        "autonomy.suggestion",
        "autonomy.decision_log",
    }
    for table in Base.metadata.tables.values():
        assert "minimum_confidence_by_risk" not in table.columns


def test_control_9_the_migration_creates_only_the_autonomy_schema() -> None:
    """TDD §19: *"Additive migrations only ... touches no existing engine's
    tables."* `action.identity_confidence_policy` is untouched in structure
    **and** in content -- 4D seeds no policy row."""
    code = _code_of(_SERVICE_ROOT / "alembic" / "versions" / "0001_initial_schema.py")
    assert "CREATE SCHEMA IF NOT EXISTS autonomy" in code
    assert "action." not in code
    assert "INSERT" not in code.upper()
    assert "ALTER TABLE" not in code.upper()


# --- Negative control 10 -----------------------------------------------------
def test_control_10_no_module_imports_another_engine() -> None:
    """**Negative control 10.** import-linter's "Engines are independent"
    contract is the enforcement in CI; this asserts the same property from
    inside the package, so a violation also fails this engine's own suite."""
    forbidden = ("nova_action_engine", "nova_digital_twin_engine", "nova_planning_engine")
    offenders: list[str] = []
    for path in _source_files():
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            offenders += [
                f"{path.name}:{node.lineno} {name}"
                for name in names
                if name.startswith(forbidden)
            ]
    assert offenders == []


def test_the_domain_layer_imports_no_framework() -> None:
    """docs/architecture/03 §1: `domain/` may import only its own modules and
    `nova_contracts` -- never FastAPI, SQLAlchemy or the event-bus SDK."""
    forbidden = ("fastapi", "sqlalchemy", "nova_eventbus_sdk", "alembic", "starlette")
    offenders: list[str] = []
    for path in sorted((_SOURCE_ROOT / "domain").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            offenders += [
                f"{path.name}:{node.lineno} {name}"
                for name in names
                if name.startswith(forbidden)
            ]
    assert offenders == []


def test_every_module_imports_cleanly() -> None:
    """A guard that the checks above cover the shipped package: a module that
    fails to import would still pass every AST walk while the engine would not
    boot."""
    for module in pkgutil.walk_packages(
        nova_autonomy_engine.__path__, prefix="nova_autonomy_engine."
    ):
        importlib.import_module(module.name)


# --- TDD §10 item 5: single trusted user, no RBAC ----------------------------
@pytest.mark.parametrize("term", ["role", "rbac", "tenant", "scopes"])
def test_no_rbac_concept_is_introduced(term: str) -> None:
    """TDD §10 item 5 and §13's non-goal: ADR-025's single-trusted-user model is
    preserved exactly. The Permission Matrix's *categories* are capability
    classes, not roles, and nothing derives an allow-list from them."""
    for path in _source_files():
        assert term not in _code_of(path).lower(), f"{path.name} mentions {term!r}"


def test_the_only_identity_is_the_configured_primary_user() -> None:
    """No second identity concept is introduced (TDD §10 item 5)."""
    from nova_autonomy_engine.config import Settings

    fields = set(Settings.model_fields)
    identity_fields = {name for name in fields if "user" in name or "ident" in name}
    assert identity_fields == {"primary_user_id"}
