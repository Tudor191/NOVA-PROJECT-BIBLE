"""Phase 4F.7's boundary controls, asserted over the served surface and the
source -- TDD 4F.7 §16 (P-1, P-9, P-13, P-14) and §7.4.

* **P-1** -- exactly three operations under `/v1/cognitive-state`, all `GET`, none
  with a parameter or a body. Asserted against the **served OpenAPI document**:
  what a caller can reach is what the document says, not what a decorator was
  meant to say (4E's control 7).
* **P-9** -- no response model carries a status, outcome, decision, `subject_id`,
  triggered or executed field (RS-4b, RS-4c, RS-6a).
* **P-13** -- no new Event Bus subject; `PUBLIC_TOPICS` unchanged at 18; the one
  internal subject this engine requests stays out of the browser's reach.
* **P-14** -- 4F.7 is read-only: nothing on the served path can create a thought,
  move one, or promote one (RS-1b). F-6 -- *no production caller of
  `promote_thought`* -- stays true.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from nova_cognitive_state_engine.config import Settings
from nova_cognitive_state_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_cognitive_state_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_cognitive_state_engine.main import create_app
from nova_contracts.registry import known_subjects

SRC = Path(__file__).resolve().parents[2] / "src" / "nova_cognitive_state_engine"
_REPO_ROOT = Path(__file__).resolve().parents[4]
_WS_GATEWAY_PROTOCOL = (
    _REPO_ROOT / "services" / "ws-gateway" / "src" / "nova_ws_gateway" / "domain" / "protocol.py"
)

THE_THREE = {
    "/v1/cognitive-state/thoughts",
    "/v1/cognitive-state/focus",
    "/v1/cognitive-state/sensors",
}


@pytest.fixture(scope="module")
def openapi() -> dict:  # type: ignore[type-arg]
    import os

    previous = os.environ.get("EVENT_BUS_BACKEND")
    os.environ["EVENT_BUS_BACKEND"] = "in_memory"
    try:
        with TestClient(create_app(Settings())) as client:
            return client.get("/openapi.json").json()  # type: ignore[no-any-return]
    finally:
        if previous is None:
            del os.environ["EVENT_BUS_BACKEND"]
        else:
            os.environ["EVENT_BUS_BACKEND"] = previous


# --- P-1 ---------------------------------------------------------------------------


def test_p1_exactly_three_get_operations_under_the_prefix(openapi: dict) -> None:  # type: ignore[type-arg]
    published = {path for path in openapi["paths"] if path.startswith("/v1/")}
    assert published == THE_THREE
    for path in THE_THREE:
        assert set(openapi["paths"][path]) == {"get"}, f"{path} exposes a non-GET method"


def test_p1_no_operation_takes_a_parameter_or_a_body(openapi: dict) -> None:  # type: ignore[type-arg]
    """No `user_id` parameter anywhere -- identity is resolved server-side -- and
    no request body, so there is nothing a caller could write with."""
    for path in THE_THREE:
        operation = openapi["paths"][path]["get"]
        assert operation.get("parameters", []) == [], f"{path} declares parameters"
        assert "requestBody" not in operation


def test_no_perception_or_autonomy_route_is_served(openapi: dict) -> None:  # type: ignore[type-arg]
    for path in openapi["paths"]:
        assert not path.startswith("/v1/perception"), path
        assert "autonomy" not in path and "decision" not in path, path


def test_the_internal_surface_is_only_health_and_readiness(openapi: dict) -> None:
    internal = {path for path in openapi["paths"] if path.startswith("/internal/")}
    assert internal == {"/internal/health", "/internal/readiness"}


# --- P-9 ---------------------------------------------------------------------------

_FORBIDDEN_FIELDS = {
    "status",
    "outcome",
    "decision",
    "decided",
    "subject_id",
    "triggered",
    "trigger",
    "executed",
    "executing",
    "execution",
    "user_id",
    "approved",
}


def test_p9_no_response_model_carries_a_decision_or_trigger_field(openapi: dict) -> None:  # type: ignore[type-arg]
    schemas = openapi["components"]["schemas"]
    ours = [
        name
        for name in schemas
        if name.endswith("Response") and name not in {"HealthResponse", "ReadinessResponse"}
    ]
    assert set(ours) >= {
        "ThoughtListResponse",
        "ThoughtResponse",
        "ProposedActionResponse",
        "FocusResponse",
        "FocusEntryResponse",
        "SensorStateListResponse",
        "SensorStateResponse",
    }
    for name in ours:
        fields = set(schemas[name].get("properties", {}))
        assert not fields & _FORBIDDEN_FIELDS, f"{name} carries {fields & _FORBIDDEN_FIELDS}"


def test_p9_the_sensor_state_enum_is_the_six_lifecycle_values(openapi: dict) -> None:  # type: ignore[type-arg]
    state = openapi["components"]["schemas"]["SensorStateResponse"]["properties"]["state"]
    assert state["enum"] == [
        "uninitialized",
        "initialized",
        "running",
        "paused",
        "stopped",
        "failed",
    ]


# --- P-13 --------------------------------------------------------------------------


def _public_topics() -> frozenset[str]:
    """Parsed, not imported -- this engine's tests must not depend on
    `ws-gateway`'s package (the `autonomy-engine` precedent)."""
    tree = ast.parse(_WS_GATEWAY_PROTOCOL.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign | ast.Assign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id == "PUBLIC_TOPICS" for t in targets):
                call = node.value
                assert isinstance(call, ast.Call)
                return frozenset(ast.literal_eval(call.args[0]))
    raise AssertionError("PUBLIC_TOPICS not found; fix this parser, do not delete it")


def test_p13_the_registry_holds_one_hundred_and_twenty_subjects() -> None:
    """4F.7 adds no subject: the count is 4F.6's 120, unchanged."""
    assert len(known_subjects()) == 120
    assert "perception.sensor.health_changed" in known_subjects()


def test_p13_public_topics_are_unchanged_at_eighteen() -> None:
    topics = _public_topics()
    assert len(topics) == 18
    # The existing public sensor-status topic stays public (RS-3a) ...
    assert "perception.sensor.health_changed" in topics
    # ... and the one internal subject this engine requests never becomes public.
    assert "autonomy.decision.requested" not in topics
    assert not any(topic.startswith("cognitive_state") for topic in topics)


def test_p13_this_engines_allow_lists_are_exactly_the_ratified_two() -> None:
    assert frozenset({"autonomy.decision.requested"}) == PUBLISHABLE_SUBJECTS
    assert frozenset({"perception.sensor.health_changed"}) == SUBSCRIBABLE_SUBJECTS


# --- P-14 --------------------------------------------------------------------------


def _code_only(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def _names_used(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.name for alias in node.names)
            if node.module:
                names.add(node.module.rsplit(".", 1)[-1])
    return names


@pytest.mark.parametrize(
    "module", ["api/cognitive_state.py", "api/health.py", "main.py", "events/handlers.py"]
)
def test_p14_nothing_on_the_served_path_writes_a_thought_or_promotes(module: str) -> None:
    used = _names_used(SRC / module)
    for forbidden in (
        "promote_thought",
        "promotion_orchestration",
        "upsert_thought",
        "move_layer",
        "request_decision",
    ):
        assert forbidden not in used, f"{module} reaches {forbidden}; 4F.7 is read-only (RS-1b)"


def test_p14_promote_thought_still_has_no_production_caller() -> None:
    """F-6 stays true: the only occurrence is the definition itself."""
    callers = [
        path.relative_to(SRC).as_posix()
        for path in SRC.rglob("*.py")
        if "promote_thought(" in _code_only(path) and path.name != "promotion_orchestration.py"
    ]
    assert callers == []


def test_the_api_declares_only_get_routes_in_source() -> None:
    source = _code_only(SRC / "api" / "cognitive_state.py")
    for method in ("post", "put", "patch", "delete"):
        assert f"@router.{method}(" not in source
