"""P-22 -- the restated vocabulary cannot drift from `perception-engine`'s
(TDD 4F.7 §28.2, §28.4).

`domain/sensor_state.py` restates `SensorState`'s six values because this engine
may not import `nova_perception_engine` (ADR-004; control 7). This test is what
makes the restatement safe: it reads `perception-engine`'s own source **as text**
and fails the moment the two lists differ in membership or order.

**Parsed, not imported** -- the same reason `autonomy-engine`'s
`tests/contract/test_autonomy_boundaries.py::_public_topics` gives for parsing
`ws-gateway`'s literal: importing would make this engine's test suite depend on
another engine's package, the very coupling the boundary forbids. The canonical
module stays the authority; there is no third artifact that could itself drift.
"""

from __future__ import annotations

import ast
from pathlib import Path

from nova_cognitive_state_engine.domain.sensor_state import SENSOR_LIFECYCLE_STATES

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PERCEPTION_SENSOR = (
    _REPO_ROOT
    / "services"
    / "perception-engine"
    / "src"
    / "nova_perception_engine"
    / "domain"
    / "sensor.py"
)


def _perception_sensor_state() -> tuple[str, ...]:
    """The string arguments of `SensorState = Literal[...]`, in source order."""
    tree = ast.parse(_PERCEPTION_SENSOR.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(t, ast.Name) and t.id == "SensorState" for t in targets):
            continue
        value = node.value
        assert isinstance(value, ast.Subscript), "SensorState is no longer a Literal[...]"
        elements = value.slice.elts if isinstance(value.slice, ast.Tuple) else [value.slice]
        return tuple(
            element.value
            for element in elements
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        )
    raise AssertionError(
        f"no `SensorState` assignment found in {_PERCEPTION_SENSOR}; if the canonical "
        "vocabulary moved, point this parser at it -- do not delete the test"
    )


def test_the_parser_actually_found_perceptions_vocabulary() -> None:
    """Anti-vacuity: an empty parse would make the equality below meaningless."""
    assert _PERCEPTION_SENSOR.is_file()
    assert len(_perception_sensor_state()) == 6


def test_the_restated_vocabulary_equals_perceptions_sensor_state_exactly() -> None:
    assert _perception_sensor_state() == SENSOR_LIFECYCLE_STATES
