"""Phase 4F.P, P8 -- guards for the real end-to-end execution evidence (TDD 4F.P
A-4FP-12; §15 V-9 and V-10; §28.4 C-12 and C-14).

`tools/e2e_real_execution.py` is the composed-stack proof, and it only runs
where Docker does -- the `e2e` job. Everything that would make that proof
**silently weaker** is a hand-maintained fact that drifts without Docker: the
stack's shape, the job's step order, the driver's own discipline, and the
values it restates from the engines. These tests make each of them cheap.

**Read as source text or AST, never imported** -- the precedent
`test_identity_confidence_ceiling_drift.py` sets: an engine's constant is
ADR-004 private, so this file checks the text the engine ships rather than
importing across the engine boundary.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE = REPO_ROOT / "infra" / "docker" / "docker-compose.local.yml"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-checks.yml"
DRIVER = REPO_ROOT / "tools" / "e2e_real_execution.py"
SERVICES = REPO_ROOT / "services"

P8_SERVICES = ("perception-engine", "perception-engine-worker", "nova-companion")


def _services() -> dict[str, dict]:
    return yaml.safe_load(COMPOSE.read_text())["services"]


def _e2e_steps() -> list[dict]:
    steps: list[dict] = yaml.safe_load(WORKFLOW.read_text())["jobs"]["e2e"]["steps"]
    return steps


def _step_index(name: str) -> int:
    names = [step.get("name") for step in _e2e_steps()]
    assert name in names, f"the e2e job has no step named {name!r}"
    return names.index(name)


def _driver() -> ast.Module:
    return ast.parse(DRIVER.read_text())


def _driver_constant(name: str) -> ast.expr:
    for node in _driver().body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return node.value
    raise AssertionError(f"the driver defines no top-level {name}")


def _uuid_literal(path: Path, name: str) -> str:
    """`NAME = UUID("...")` in a module, as the string."""
    match = re.search(rf'^{name}\s*=\s*UUID\("([0-9a-f-]+)"\)', path.read_text(), re.M)
    assert match is not None, f"{path.relative_to(REPO_ROOT)} has no {name} = UUID(...)"
    return match.group(1)


def _call_uuid_arg(node: ast.expr) -> str:
    assert isinstance(node, ast.Call) and isinstance(node.args[0], ast.Constant)
    return str(node.args[0].value)


def _workspace_mount(service: str) -> tuple[str, str]:
    volumes = _services()[service].get("volumes", [])
    mounts = [v for v in volumes if ":/workspace" in v]
    assert len(mounts) == 1, f"{service} must bind exactly one workspace, found {volumes}"
    source, target = mounts[0].split(":")[:2]
    return source, target


# --- the stack A-4FP-12 ratified -----------------------------------------------------


def test_the_companion_is_a_compose_service_watching_the_bind_mounted_workspace() -> None:
    companion = _services()["nova-companion"]
    assert companion["build"]["dockerfile"] == "companion/nova-companion/Dockerfile"
    assert companion["environment"]["NOVA_COMPANION_WATCH_ROOT"] == "/workspace"
    assert companion["environment"]["NOVA_COMPANION_PERCEPTION_BASE_URL"] == (
        "http://perception-engine:8000"
    )
    assert any(v.endswith(":/workspace:ro") for v in companion["volumes"]), (
        "the companion only observes; its workspace mount is read-only"
    )


def test_one_workspace_the_capability_sandbox_root_is_the_watched_directory() -> None:
    """**§28.4 C-12.** The same host directory, at the same path, in both."""
    capability = _services()["capability-engine"]
    assert capability["environment"]["CAPABILITY_ENGINE_SANDBOX_FILESYSTEM_ROOT"] == "/workspace"
    assert _workspace_mount("capability-engine") == _workspace_mount("nova-companion")


def _default_primary_user(engine: str) -> str:
    config = SERVICES / engine / "src" / f"nova_{engine.replace('-', '_')}" / "config.py"
    match = re.search(r'primary_user_id: UUID = UUID\("([0-9a-f-]+)"\)', config.read_text())
    assert match is not None, f"{engine} declares no default primary_user_id"
    return match.group(1)


@pytest.mark.parametrize("engine", ["cognitive-state-engine", "autonomy-engine", "action-engine"])
def test_one_user_perception_engine_resolves_every_other_engines_primary_user(engine: str) -> None:
    """**ADR-025, §28.4 C-12.** `perception-engine` defaults to no user at all
    and then publishes nothing; the stack sets it to the user the engines
    downstream of it resolve."""
    perception = _services()["perception-engine"]["environment"]
    assert perception["PERCEPTION_ENGINE_PRIMARY_USER_ID"] == _default_primary_user(engine)


def test_the_driver_restates_that_same_user() -> None:
    assert _call_uuid_arg(_driver_constant("PRIMARY_USER")) == _default_primary_user(
        "autonomy-engine"
    )


# --- the job that runs it ---------------------------------------------------------------


def test_the_workspace_exists_before_the_first_up() -> None:
    assert _step_index("Provision the shared workspace (4F.P P8)") < _step_index("Start the stack")


def test_the_p8_services_start_after_the_golden_path_not_with_it() -> None:
    """The Cognitive State panel's spec asserts an unseeded stack in which no
    sensor has reported; `perception-engine` reports as it starts. So the P8
    services join the stack after the golden path, never in the first `up`."""
    # The command, not its explanatory comments (which name these services).
    first_up = "\n".join(
        line
        for line in _e2e_steps()[_step_index("Start the stack")]["run"].splitlines()
        if not line.lstrip().startswith("#")
    )
    for service in P8_SERVICES:
        assert not re.search(rf"(?<![\w-]){re.escape(service)}(?![\w-])", first_up), (
            f"{service} is in the first `up`, so it would run during the golden path"
        )
    start = _step_index("Start the P8 services (perception-engine, its worker, nova-companion)")
    assert start > _step_index("Run the golden path")
    run = _e2e_steps()[start]["run"]
    for service in P8_SERVICES:
        assert service in run


def test_the_proof_runs_after_its_services_and_its_failure_fails_the_job() -> None:
    start = _step_index("Start the P8 services (perception-engine, its worker, nova-companion)")
    proof = _step_index("Prove real end-to-end execution (4F.P P8)")
    assert proof == start + 1
    step = _e2e_steps()[proof]
    assert "tools/e2e_real_execution.py" in step["run"]
    assert "continue-on-error" not in step
    assert step.get("if") == "${{ !cancelled() }}"


# --- V-9: the driver drives nothing ------------------------------------------------------


def test_v9_the_driver_imports_no_engine_and_no_project_package() -> None:
    allowed = {
        "__future__",
        "asyncio",
        "json",
        "os",
        "sys",
        "time",
        "collections.abc",
        "dataclasses",
        "pathlib",
        "typing",
        "uuid",
        "asyncpg",
        "httpx",
        "nats",
    }
    imported: set[str] = set()
    for node in ast.walk(_driver()):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert imported <= allowed, f"unexpected imports: {sorted(imported - allowed)}"


@pytest.mark.parametrize(
    "forbidden",
    [
        "publish",
        "request",
        "request_decision",
        "serve",
        "promote_thought",
        "decide",
        "handle_decision_request",
        "ingest_workspace_observation",
    ],
)
def test_v9_the_driver_never_publishes_requests_or_drives_a_decision(forbidden: str) -> None:
    """**V-9**: no test code on the V-1 ... V-5 path calls `promote_thought` or
    `decide()`, or publishes `autonomy.decision.requested` -- nor any other
    subject. The bus is only ever subscribed to."""
    for node in ast.walk(_driver()):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            assert name != forbidden, f"the driver calls {forbidden}() at line {node.lineno}"


def _string_literals() -> list[str]:
    literals: list[str] = []
    for node in ast.walk(_driver()):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            literals.append(node.value)
        elif isinstance(node, ast.JoinedStr):
            literals.append("".join(v.value for v in node.values if isinstance(v, ast.Constant)))
    return literals


def test_v9_every_sql_statement_the_driver_sends_is_a_select() -> None:
    """**Independent SQL, read-only.** Nothing is inserted, updated or
    deleted behind an engine's back."""
    statements = [
        text.strip()
        for text in _string_literals()
        if re.match(r"\s*(SELECT|INSERT|UPDATE|DELETE|WITH|TRUNCATE)\b", text, re.I)
    ]
    assert statements, "found no SQL in the driver; fix this parser"
    for statement in statements:
        assert statement.upper().startswith("SELECT"), statement


def test_v9_the_driver_calls_only_the_configuration_and_observation_routes() -> None:
    """Configuration goes through production routes; no route that could
    execute anything (an approval decision, a capability install) is called."""
    routes = {
        text
        for text in _string_literals()
        if text.startswith("/v1/") or text.startswith("/internal/")
    }
    assert routes == {
        "/internal/readiness",
        "/internal/metrics/",
        "/v1/autonomy/level",
        "/v1/autonomy/permissions",
        "/v1/autonomy/policies",
        "/v1/action/identity-confidence-policy",
    }


def test_v9_the_only_tapped_subjects_are_the_path_and_the_replies() -> None:
    tapped = _driver_constant("TAPPED_SUBJECTS")
    assert isinstance(tapped, ast.Tuple)
    subjects = {e.value for e in tapped.elts if isinstance(e, ast.Constant)}
    assert subjects == {
        "perception.workspace.observed",
        "autonomy.decision.requested",
        "action.execute",
        "capability.resolve.request",
        "capability.invoke.request",
        "world_model.context.request",
        "_INBOX.>",
    }


# --- what the driver restates, against the engines that own it ---------------------------


def test_the_trigger_namespace_is_autonomy_engines() -> None:
    owned = _uuid_literal(
        SERVICES / "autonomy-engine/src/nova_autonomy_engine/decision_orchestration.py",
        "_DECISION_TRIGGER_NAMESPACE",
    )
    assert _call_uuid_arg(_driver_constant("TRIGGER_NAMESPACE")) == owned


def test_the_ingestion_namespace_is_cognitive_state_engines() -> None:
    owned = _uuid_literal(
        SERVICES / "cognitive-state-engine/src/nova_cognitive_state_engine/domain/ingestion.py",
        "_INGESTION_NAMESPACE",
    )
    assert _call_uuid_arg(_driver_constant("INGESTION_NAMESPACE")) == owned


def _dict_literal(node: ast.expr) -> dict[str, object]:
    assert isinstance(node, ast.Dict)
    return {
        k.value: (v.value if isinstance(v, ast.Constant) else v)
        for k, v in zip(node.keys, node.values, strict=True)
        if isinstance(k, ast.Constant)
    }


def test_the_outcome_table_is_p7s() -> None:
    """The driver checks the recorded outcome as a function of `action-engine`'s
    own status; its table must be the one `autonomy-engine` maps with."""
    decision = (
        SERVICES / "autonomy-engine/src/nova_autonomy_engine/domain/decision.py"
    ).read_text()
    models = (SERVICES / "autonomy-engine/src/nova_autonomy_engine/domain/models.py").read_text()
    members = dict(re.findall(r'^\s{4}([A-Z_]+) = "([a-z_]+)"', models, re.M))
    block = re.search(
        r"^ACTION_STATUS_OUTCOMES: Mapping\[str, DecisionOutcome\] = "
        r"MappingProxyType\(\s*\{(.*?)\}",
        decision,
        re.M | re.S,
    )
    assert block is not None
    owned = {
        status: members[member]
        for status, member in re.findall(r'"([a-z_]+)": DecisionOutcome\.([A-Z_]+)', block.group(1))
    }
    assert len(owned) == 8
    assert _dict_literal(_driver_constant("OUTCOME_FOR_STATUS")) == owned


def test_t1_is_the_ratified_authoring_entry() -> None:
    authoring = (
        SERVICES / "cognitive-state-engine/src/nova_cognitive_state_engine/domain/authoring.py"
    ).read_text()
    entry = re.search(r"^T1 = AuthoringEntry\((.*?)^\)", authoring, re.M | re.S)
    assert entry is not None
    text = entry.group(1)
    t1 = _dict_literal(_driver_constant("T1"))
    assert f'operation="{t1["operation"]}"' in text
    assert "parameters=MappingProxyType({})" in text
    parameters = t1["parameters"]
    assert isinstance(parameters, ast.Dict) and not parameters.keys
    for field in ("action_type", "execution_target", "verification_method"):
        assert f'{field}="{t1[field]}"' in text, field
    assert f"category=PermissionCategory.{str(t1['category']).upper()}" in text
    assert f"risk=RiskLevel.{str(t1['risk']).upper()}" in text


def test_the_twelve_stages_are_action_engines() -> None:
    pipeline = (SERVICES / "action-engine/src/nova_action_engine/domain/pipeline.py").read_text()
    block = re.search(r"class ActionStage\(StrEnum\):(.*?)\n\n", pipeline, re.S)
    assert block is not None
    owned = tuple(re.findall(r'= "([a-z_]+)"', block.group(1)))
    stages = _driver_constant("TWELVE_STAGES")
    assert isinstance(stages, ast.Tuple)
    assert tuple(e.value for e in stages.elts if isinstance(e, ast.Constant)) == owned
    assert len(owned) == 12
