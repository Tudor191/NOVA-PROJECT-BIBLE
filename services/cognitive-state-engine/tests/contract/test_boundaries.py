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


def test_control_11_this_engine_publishes_nothing() -> None:
    """D-4F-6: no cognitive-state Event Bus subject, in 4F.1 or later. An empty
    publish allow-list is also the structural half of §6.2's *must not publish
    `action.execute`*: there is no subject at which one could be emitted."""
    assert frozenset() == PUBLISHABLE_SUBJECTS


def test_the_subscribe_allow_list_is_empty_until_a_handler_exists() -> None:
    """A subscription without a consumer is the dead topic `ws-gateway`'s own
    docstring warns about. Subjects arrive in 4F.6 with their handlers."""
    assert frozenset() == SUBSCRIBABLE_SUBJECTS


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


def test_control_11_the_only_repository_this_engine_writes_is_its_own() -> None:
    """§10: cognitive state reads other engines' facts over the bus and owns
    none of them. No module may name another engine's schema."""
    for path in _modules():
        code = _code_only(path)
        for schema in ("autonomy.", "action.", "memory.", "digital_twin.", "perception."):
            assert f'"{schema}' not in code, (
                f"{path.name} names the {schema} schema in executable code"
            )


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
