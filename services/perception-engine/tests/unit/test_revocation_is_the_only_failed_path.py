"""**N-8: the filesystem sensor reaches `failed` only through the revocation
report** (TDD 4F.8 §17, A-4F8-1 (a)).

A-4F8-1 rejected inferring failure from silence. That rule is structural, so it
is checked over the source rather than by a test of behaviour, which could only
show that one particular inference is absent:

1. the filesystem sensor's only `fail` transition sits inside `report_error`,
   guarded by `kind == "permission_revoked"`;
2. the only module that *reports* that kind is the revocation route.

Parsed, never imported, so a new call site cannot hide behind an import cycle.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "nova_perception_engine"
SENSOR = SRC / "sensors" / "filesystem_sensor.py"
ROUTE = SRC / "api" / "permission_revocations.py"
KIND = "permission_revoked"


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(), filename=str(path))


def _fail_calls(tree: ast.AST) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_transition"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "fail"
    ]


def test_the_filesystem_sensor_fails_only_inside_report_error_on_a_revocation() -> None:
    tree = _parse(SENSOR)
    (sensor_class,) = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    methods = {n.name: n for n in sensor_class.body if isinstance(n, ast.FunctionDef)}

    assert len(_fail_calls(tree)) == 1, "the filesystem sensor gained a second `fail` path"
    assert len(_fail_calls(methods["report_error"])) == 1

    guards = [
        node
        for node in ast.walk(methods["report_error"])
        if isinstance(node, ast.If) and _fail_calls(node)
    ]
    assert guards, "the `fail` transition is not guarded"
    assert any(
        isinstance(constant, ast.Constant) and constant.value == KIND
        for guard in guards
        for constant in ast.walk(guard.test)
    ), f"the `fail` transition is not guarded by kind == {KIND!r}"


def test_only_the_revocation_route_reports_a_permission_revocation() -> None:
    """`kind="permission_revoked"` passed as a keyword is a report. It is built in
    exactly one place."""
    reporters = sorted(
        str(path.relative_to(SRC))
        for path in SRC.rglob("*.py")
        for node in ast.walk(_parse(path))
        if isinstance(node, ast.keyword)
        and node.arg == "kind"
        and isinstance(node.value, ast.Constant)
        and node.value.value == KIND
    )
    assert reporters == [str(ROUTE.relative_to(SRC))], reporters
