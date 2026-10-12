"""Guards for 4F.8's acceptance harness and its CI steps (TDD 4F.8 D8; §17
N-1 ... N-4; §16 E-4, E-13; §29.4).

`tools/e2e_acceptance.py` produces AC-7's and AC-8's evidence, and it runs
only where Docker does: the `e2e` job. Everything that would make that
evidence **silently weaker** is checked here, cheaply, against the harness's
source and the job's steps. A mutation to the harness cannot be caught by the
harness itself, so these are structural (§17):

- **N-1**: the harness never references the dispatch schedule, and never
  computes a phase from the clock;
- **N-2**: each sample is measured once, by one call site, and every result is
  kept;
- **N-3**: no fake clock, and `observed_at` is compared with the file's own OS
  time;
- **N-4 / E-13**: no publish, request, `promote_thought` or `decide`, and no
  engine import;
- **E-4**: between a write and its observation the harness only reads;
- **the ratified figures**: a 5.0 s budget, at least 10 samples, a 30 s
  deadline, polling at no more than 100 ms, and a 25 s E-6 watch;
- **the restated path hash** equals `perception-engine`'s;
- **the steps** run in §29.4.1's order, each reports whatever the previous one
  did, and the browser specs never run inside the golden path.

Read as source text or AST, never imported, as `test_e2e_real_execution.py`
does.
"""

from __future__ import annotations

import ast
import functools
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS = REPO_ROOT / "tools" / "e2e_acceptance.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-checks.yml"
WORKSPACE_DOMAIN = (
    REPO_ROOT / "services/perception-engine/src/nova_perception_engine/domain/workspace.py"
)
SPECS = REPO_ROOT / "apps" / "web-client" / "tests" / "e2e"

STEPS = (
    "Declare the AC-7 known project (4F.8 D3)",
    "Start the P8 services (perception-engine, its worker, nova-companion)",
    "Prove real end-to-end execution (4F.P P8)",
    "AC-8 acceptance (4F.8 D6)",
    "P-AC8-1 in a browser (4F.8 D7)",
    "AC-7 latency (4F.8 D5)",
    "P-AC7-1 in a browser, with the genuine revocation (4F.8 D7)",
    "AC-7 revocation evidence (4F.8 E-5, E-6, E-18)",
)
ACCEPTANCE_STEPS = STEPS[3:]


@functools.cache
def _tree() -> ast.Module:
    """Parsed once, so nodes found by different checks can be compared by
    identity."""
    return ast.parse(HARNESS.read_text())


def _function(name: str) -> ast.AsyncFunctionDef | ast.FunctionDef:
    for node in _tree().body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
            return node
    raise AssertionError(f"the harness defines no {name}()")


def _constant(name: str) -> object:
    for node in _tree().body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
            and isinstance(node.value, ast.Constant)
        ):
            return node.value.value
    raise AssertionError(f"the harness defines no top-level constant {name}")


def _calls(node: ast.AST) -> list[str]:
    names = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            names.append(func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", ""))
    return names


def _code_strings(node: ast.AST) -> list[str]:
    """String literals that are code, not documentation: every bare string
    statement (a docstring, or the string documenting a constant) is left out."""
    documentation = {
        id(child.value)
        for child in ast.walk(node)
        if isinstance(child, ast.Expr)
        and isinstance(child.value, ast.Constant)
        and isinstance(child.value.value, str)
    }
    literals = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            if id(child) not in documentation:
                literals.append(child.value)
        elif isinstance(child, ast.JoinedStr):
            literals.append("".join(v.value for v in child.values if isinstance(v, ast.Constant)))
    return literals


def _steps() -> list[dict]:
    steps: list[dict] = yaml.safe_load(WORKFLOW.read_text())["jobs"]["e2e"]["steps"]
    return steps


def _step(name: str) -> dict:
    (step,) = [s for s in _steps() if s.get("name") == name]
    return step


# --- N-4 / E-13: the harness drives nothing ---------------------------------------


def test_e13_the_harness_imports_no_engine() -> None:
    allowed = {
        "__future__",
        "asyncio",
        "hashlib",
        "json",
        "os",
        "random",
        "subprocess",
        "sys",
        "time",
        "traceback",
        "dataclasses",
        "datetime",
        "pathlib",
        "typing",
        "uuid",
        "asyncpg",
        "httpx",
        "e2e_real_execution",
    }
    imported: set[str] = set()
    for node in ast.walk(_tree()):
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
        "subscribe",
    ],
)
def test_e13_the_harness_never_publishes_or_drives_a_decision(forbidden: str) -> None:
    """E-13, N-4: the trigger is the production one. The bus is observed only
    through P8's passive `Tap`, whose own guard pins its subjects."""
    assert forbidden not in _calls(_tree()), f"the harness calls {forbidden}()"


def test_every_sql_statement_is_a_select() -> None:
    statements = [
        text.strip()
        for text in _code_strings(_tree())
        if re.match(r"\s*(SELECT|INSERT|UPDATE|DELETE|WITH|TRUNCATE)\b", text, re.I)
    ]
    assert len(statements) >= 8, "found too little SQL in the harness; fix this parser"
    for statement in statements:
        assert statement.upper().startswith("SELECT"), statement


def test_the_harness_calls_only_its_declared_routes() -> None:
    declared = None
    for node in _tree().body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "ROUTES_USED" for t in node.targets)
            and isinstance(node.value, ast.Tuple)
        ):
            declared = {e.value for e in node.value.elts if isinstance(e, ast.Constant)}
    assert declared, "ROUTES_USED is not a literal tuple"
    used = {
        text
        for text in _code_strings(_tree())
        if text.startswith("/v1/") or text.startswith("/internal/")
    }
    assert used <= declared, f"undeclared routes: {sorted(used - declared)}"
    # Nothing that executes: no approval decision, no capability route, no
    # action-engine execution route.
    assert not any("/decide" in r or "/v1/capabilities" in r for r in declared)


# --- N-1, N-2, N-3, E-4: the measurement ------------------------------------------------


def test_n1_the_harness_never_references_the_dispatch_schedule() -> None:
    words = re.compile(r"cron|tick|second=|0, 10, 20", re.I)
    offenders = [s for s in _code_strings(_tree()) if words.search(s)]
    identifiers = [
        node.id if isinstance(node, ast.Name) else node.attr
        for node in ast.walk(_tree())
        if isinstance(node, ast.Name | ast.Attribute)
    ]
    names = [n for n in identifiers if re.search(r"cron|tick|schedule", n, re.I)]
    assert not offenders and not names, (offenders, names)


def test_n1_no_phase_is_computed_from_the_clock() -> None:
    """No modulo anywhere: aligning to a boundary needs one."""
    binary = [n for n in ast.walk(_tree()) if isinstance(n, ast.BinOp)]
    modulo = [n for n in binary if isinstance(n.op, ast.Mod)]
    assert not modulo


def test_n2_each_sample_is_measured_once_and_every_result_kept() -> None:
    sites = [
        node
        for node in ast.walk(_tree())
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "measure_sample"
    ]
    assert len(sites) == 1, "measure_sample() has more than one call site"
    latency = _function("ac7_latency")
    (loop,) = [
        n
        for n in ast.walk(latency)
        if isinstance(n, ast.For) and any(c is sites[0] for c in ast.walk(n))
    ]
    assert not [n for n in ast.walk(loop) if isinstance(n, ast.Continue | ast.Break)], (
        "a sample could be skipped or the loop cut short"
    )
    assert "append" in _calls(loop), "a sample's result is not kept"
    identifiers = {n.id.lower() for n in ast.walk(_tree()) if isinstance(n, ast.Name)} | {
        n.attr.lower() for n in ast.walk(_tree()) if isinstance(n, ast.Attribute)
    }
    assert not {i for i in identifiers if "retry" in i or "attempt" in i or "discard" in i}


def test_n3_no_fake_clock_and_observed_at_is_checked_against_the_os() -> None:
    text = HARNESS.read_text()
    for fake in ("freezegun", "time_machine", "unittest.mock", "monkeypatch"):
        assert fake not in text, fake
    checker = ast.unparse(_function("_check_samples"))
    # Either of the file's own OS times, and only those (F-4F8-18).
    assert "abs(reported - sample.os_created)" in checker
    assert "abs(reported - sample.os_written)" in checker
    assert "observed_at" in checker
    assert "st_mtime_ns" in ast.unparse(_function("measure_sample"))


def test_f4f8_18_the_interval_starts_at_the_files_creation() -> None:
    """*(F-4F8-18.)* The creation's mtime is read before the write and the
    write's after it, and `elapsed` starts at the creation, the earlier one. The
    path is created exclusively, so the OS refuses one that already exists."""
    sample = _function("measure_sample")
    source = ast.unparse(sample)
    assert "os.O_EXCL" in source
    order = [
        node
        for node in ast.walk(sample)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"fstat", "write"}
    ]
    order.sort(key=lambda node: (node.lineno, node.col_offset))
    assert [n.func.attr for n in order] == ["fstat", "write", "fstat"]
    (elapsed,) = [
        n for n in ast.walk(_tree()) if isinstance(n, ast.FunctionDef) and n.name == "elapsed"
    ]
    assert "self.first_seen - self.os_created" in ast.unparse(elapsed)


def test_e4_between_a_write_and_its_observation_the_harness_only_reads() -> None:
    calls = _calls(_function("measure_sample"))
    assert not {"post", "put", "delete", "patch", "publish", "request"} & set(calls), calls
    assert "get" in calls and "write" in calls


def test_the_ratified_figures() -> None:
    assert _constant("LATENCY_BUDGET_SECONDS") == 5.0
    assert _constant("MINIMUM_SAMPLES") == 10
    assert _constant("SAMPLE_DEADLINE_SECONDS") == 30.0
    poll = _constant("POLL_SECONDS")
    assert isinstance(poll, float) and 0 < poll <= 0.1
    watch = _constant("WATCH_SECONDS")
    assert isinstance(watch, float) and watch >= 25.0
    verdict = ast.unparse(_function("ac7_latency"))
    assert "e <= LATENCY_BUDGET_SECONDS for e in measured" in verdict
    assert "len(measured) == len(samples)" in verdict, "a sample not observed must fail AC-7"


@pytest.mark.parametrize("phase", ["ac8", "ac7_latency", "ac7_revocation"])
def test_f4f8_19_an_unexpected_error_fails_the_phase_and_keeps_its_evidence(phase: str) -> None:
    """*(F-4F8-19.)* Any error fails the phase as a check, and the evidence is
    still printed: the handler reports, and `_finish` runs after it."""
    handlers = [
        h
        for h in ast.walk(_function(phase))
        if isinstance(h, ast.ExceptHandler)
        and isinstance(h.type, ast.Name)
        and h.type.id == "Exception"
    ]
    assert len(handlers) == 1, f"{phase} has no catch-all handler"
    assert "_unexpected" in _calls(handlers[0])
    assert "report.check(" in ast.unparse(_function("_unexpected"))
    assert ", False," in ast.unparse(_function("_unexpected"))
    assert "return _finish(" in ast.unparse(_function(phase))


def test_f4f8_19_e3_is_decided_before_the_attribution_checks() -> None:
    """*(F-4F8-19.)* The latency verdict and every figure are recorded before
    the per-sample attribution checks, which can time out."""
    source = ast.unparse(_function("ac7_latency"))
    assert source.index("E-3. AC-7's latency") < source.index("_check_samples(")


def test_f4f8_19_check_same_path_never_unpacks_a_row() -> None:
    """*(F-4F8-19.)* A Level-2 run that executes nothing is a failed check,
    never a `ValueError` that ends the phase early."""
    unpacks = [
        n
        for n in ast.walk(_function("_check_same_path"))
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Tuple) for t in n.targets)
    ]
    assert not unpacks, [ast.unparse(n) for n in unpacks]


def test_f4f8_21_e18_is_inspected_before_anything_waits() -> None:
    """*(F-4F8-21.)* E-18 is a read-only OS inspection that does not depend on
    E-5. It runs before the phase's first wait, so N-16 can make it fail even
    when the companion is never revoked and E-5's wait times out."""
    source = ast.unparse(_function("ac7_revocation"))
    e18 = source.index("E-18. the companion runs as the override's uid")
    assert e18 < source.index("wait_for(")
    assert e18 < source.index("companion_log_messages(")


def test_the_restated_path_hash_is_perception_engines() -> None:
    owned = WORKSPACE_DOMAIN.read_text()
    assert '_HASH_PREFIX = "ws"' in owned
    assert 'hashlib.sha256(PurePath(normalized).as_posix().encode("utf-8")).hexdigest()' in owned
    assert _constant("_HASH_PREFIX") == "ws"
    restated = ast.unparse(_function("object_id_for_path"))
    assert "hashlib.sha256(PurePosixPath(normalized).as_posix().encode('utf-8')).hexdigest()" in (
        restated
    )


# --- the steps ------------------------------------------------------------------------


def test_the_steps_run_in_the_acceptance_plans_order() -> None:
    names = [s.get("name") for s in _steps()]
    positions = [names.index(name) for name in STEPS]
    assert positions == sorted(positions), [names[p] for p in positions]
    assert positions[3:] == list(range(positions[3], positions[3] + len(ACCEPTANCE_STEPS)))


@pytest.mark.parametrize("name", STEPS[:1] + ACCEPTANCE_STEPS)
def test_each_acceptance_step_reports_whatever_came_before_and_its_failure_counts(
    name: str,
) -> None:
    step = _step(name)
    assert step.get("if") == "${{ !cancelled() }}"
    assert "continue-on-error" not in step


def test_the_browser_specs_run_in_their_own_invocations_without_retries() -> None:
    for name, spec in (
        ("P-AC8-1 in a browser (4F.8 D7)", "acceptance-ac8.spec.ts"),
        ("P-AC7-1 in a browser, with the genuine revocation (4F.8 D7)", "acceptance-ac7.spec.ts"),
    ):
        run = _step(name)["run"]
        assert f"playwright test tests/e2e/{spec}" in run
        assert "--reporter=" in run, "the golden path's report files would be overwritten"
        text = (SPECS / spec).read_text()
        assert "test.describe.configure({ retries: 0 })" in text
        assert "test.skip(" in text


def test_the_golden_path_run_never_receives_the_acceptance_inputs() -> None:
    """The specs skip without their inputs, so they cannot run inside the
    golden-path invocation, which comes first (F-4F8-16)."""
    env = _step("Run the golden path").get("env", {})
    assert not [k for k in env if k.startswith("NOVA_ACCEPTANCE_")], env


def test_the_known_project_is_declared_for_perception_engine_before_it_starts() -> None:
    run = _step("Declare the AC-7 known project (4F.8 D3)")["run"]
    assert "NOVA_PROJECT_FOLDER_BINDINGS=" in run
    assert 'mkdir -p "${NOVA_WORKSPACE_DIR}/${folder}"' in run
    for name in ("NOVA_ACCEPTANCE_KNOWN_PROJECT_ID", "NOVA_ACCEPTANCE_KNOWN_FOLDER"):
        assert f"{name}=" in run
