"""Guards for the subset of the local stack the golden-path E2E job starts.

`pr-checks.yml`'s `e2e` job names its services explicitly rather than
starting the whole compose file, and that list is where Phase 4A's first
real Playwright run went wrong twice over:

* `nova-core` was absent, so nothing published `nova.heartbeat` and the
  System Pulse honestly reported `unknown` forever;
* `communication-engine-worker` was absent, so the engine's outbox was
  never drained and neither `communication.turn.received` nor
  `communication.intent.delivered` reached the bus -- while the engine's
  own logs showed a 202, a reasoning RPC and a delivered reply, because
  the RPC legs are synchronous and bypass the outbox entirely.

Both failures presented identically: an assertion timing out against a
stack whose every container was healthy. Neither is visible without
running Docker, and Docker is the expensive, CI-only path. These tests make
both cheap, and make the *next* one of this shape cheap too.

The property is deliberately scoped to what a browser can observe. An
engine whose outbox subjects never appear in `ws-gateway`'s
`PUBLIC_TOPICS` is not required to have a worker here -- `world-model`,
`reasoning` and `ai-model-orchestration` all have undeployed workers in
compose, and closing that gap everywhere is out of scope (see
`perception-engine-worker`'s comment in the compose file). This file states
that boundary rather than leaving it implicit.

**Phase 4E widened "browser-observable" from one hop to two, and this file
had to learn the difference.** The rule above asks whether an engine's own
outbox subject is a `PUBLIC_TOPIC` -- a realtime question, and the only
shape that existed through 4D. 4E introduced the first case where a
**non-public** subject is nonetheless browser-visible, one engine removed:

    memory-engine  --memory.long_term.created (never public, and per TDD 4E
                     §8.3 never will be)-->  digital-twin-engine
                     --/v1/digital-twin, fronted by api-gateway-->  browser

`memory-engine` sat in the exemption list below for exactly the reason the
paragraph above gives, and it was right until 4E. The consequence was found
by CI rather than here: all three AC-6 Playwright specs failed on a `404`,
because `memory-engine-worker` did not exist in compose, so no `memory.*`
subject had **ever** been published in this stack -- the
`communication-engine-worker` defect again, one hop further out.

So `_needs_a_worker` now answers a two-part question, and both parts are
structural rather than a list of names:

1. **Directly** -- an outbox subject in `PUBLIC_TOPICS` (the original rule).
2. **Transitively** -- an outbox subject that a *browser-observable* engine
   subscribes to, where "browser-observable" means it publishes a public
   topic **or** `api-gateway`'s route table fronts it. Both authorities are
   read from source, so adding a gateway prefix or a subscription is what
   moves an engine in or out, not an edit here.

**Subjects are taken from `OutboxEvent(subject=…)` call sites, not from
`PUBLISHABLE_SUBJECTS`.** That set also contains `*.request` RPC subjects,
which travel through `bus.request()` and never touch the outbox -- counting
them made this rule demand a worker for `digital-twin-engine` on the
strength of `communication.intent.deliver.request`, which no worker has ever
dispatched. Only what an outbox actually carries can be stranded by a
missing one.

**Phase 4C adds one property that is not about the browser** (see
`test_every_agent_os_component_is_started_by_the_e2e_job`): AC-4's first
clause is literally *"`agent-os` runs as containers under `docker compose
up`"*, and this job is the only place in the repository where the stack is
ever brought up. A `build-and-scan.yml` matrix entry proves an image builds,
not that it starts. So for these three components the e2e job's service list
*is* the acceptance evidence, and it earns a guard here for the same reason
everything else in this file does: it is a hand-maintained list whose drift is
invisible without Docker.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE = REPO_ROOT / "infra" / "docker" / "docker-compose.local.yml"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-checks.yml"
WS_GATEWAY_PROTOCOL = (
    REPO_ROOT / "services" / "ws-gateway" / "src" / "nova_ws_gateway" / "domain" / "protocol.py"
)
API_GATEWAY_ROUTING = (
    REPO_ROOT / "services" / "api-gateway" / "src" / "nova_api_gateway" / "domain" / "routing.py"
)

#: The subjects the golden path's own assertions depend on, and the assertion
#: each one backs. Not every public topic: `perception.*` and the unrendered
#: `communication.session.*` events have no assertion, so their publishers are
#: not required to be running.
GOLDEN_PATH_SUBJECTS = {
    # "the user's own turn appears" -- `toHaveCount(1)` on the transcript.
    "communication.turn.received",
    # "NOVA answers" -- the `[data-author="nova"]` entry, and with it the
    # correlation tag and confidence tier badge.
    "communication.intent.delivered",
    # "the shell reports real telemetry" -- the System Pulse's `data-status`.
    "nova.heartbeat",
}


def _compose_services() -> dict[str, dict]:
    return yaml.safe_load(COMPOSE.read_text())["services"]


def _started_services() -> list[str]:
    """The service names the `e2e` job passes to `docker compose up`."""
    text = WORKFLOW.read_text()
    match = re.search(
        r"docker compose -f infra/docker/docker-compose\.local\.yml up -d --build\s*\\\n(.*?)\n\n",
        text,
        re.S,
    )
    assert match is not None, (
        "could not find the e2e job's `docker compose up` invocation in "
        "pr-checks.yml; fix this parser, do not delete it"
    )
    names = re.findall(r"[a-z0-9][a-z0-9-]*", match.group(1).replace("\\", " "))
    assert names, "the e2e job's service list parsed as empty; fix this parser"
    return names


def _public_topics() -> frozenset[str]:
    block = re.search(
        r"PUBLIC_TOPICS: frozenset\[str\] = frozenset\(\n\s*\{(.*?)\}\s*\)",
        WS_GATEWAY_PROTOCOL.read_text(),
        re.S,
    )
    assert block is not None, "could not find PUBLIC_TOPICS in ws-gateway's protocol.py"
    topics = frozenset(re.findall(r'"([^"]+)"', block.group(1)))
    assert topics, "PUBLIC_TOPICS parsed as empty; fix this parser, do not delete it"
    return topics


def _service_package(service: str) -> Path | None:
    """`services/<name>/src/<package>/`, or None when the name is not an engine."""
    src = REPO_ROOT / "services" / service / "src"
    if not src.is_dir():
        return None
    packages = [child for child in src.iterdir() if (child / "__init__.py").is_file()]
    return packages[0] if len(packages) == 1 else None


def _allow_list(path: Path, name: str) -> frozenset[str]:
    if not path.is_file():
        return frozenset()
    block = re.search(
        rf"{name}: frozenset\[str\] = frozenset\(\n\s*\{{(.*?)\}}\s*\)", path.read_text(), re.S
    )
    if block is None:
        return frozenset()
    return frozenset(re.findall(r'"([^"]+)"', block.group(1)))


def _publishable_subjects(package: Path) -> frozenset[str]:
    return _allow_list(package / "events" / "published.py", "PUBLISHABLE_SUBJECTS")


def _subscribable_subjects(package: Path) -> frozenset[str]:
    return _allow_list(package / "events" / "subscribed.py", "SUBSCRIBABLE_SUBJECTS")


def _outbox_subjects(package: Path) -> frozenset[str]:
    """The subjects this engine actually enqueues onto its outbox.

    Read from `OutboxEvent(subject=…)` call sites rather than from
    `PUBLISHABLE_SUBJECTS`, because the allow-list also contains `*.request`
    RPC subjects that go out through `bus.request()` and never touch the outbox
    -- see the module docstring. An engine that constructs no `OutboxEvent`
    correctly yields the empty set, which is the honest answer for
    `digital-twin-engine`: it has the dispatcher and the worker wired from day
    one, and no production call site enqueues anything yet.
    """
    subjects: set[str] = set()
    for source in package.rglob("*.py"):
        if "__pycache__" in source.parts:
            continue
        subjects.update(re.findall(r'OutboxEvent\(\s*subject="([^"]+)"', source.read_text()))
    return frozenset(subjects)


def _gateway_fronted_services() -> frozenset[str]:
    """Every upstream `api-gateway` forwards to -- the REST half of
    "browser-observable", read from the route table itself (D-6).

    `upstream_name` is the compose service name by construction, so this needs
    no translation table; adding a prefix to `build_route_table` is what puts an
    engine on the browser's path, and this reads that decision rather than
    restating it."""
    names = frozenset(re.findall(r'upstream_name="([^"]+)"', API_GATEWAY_ROUTING.read_text()))
    assert names, (
        "could not parse any upstream_name from api-gateway's routing.py; fix "
        "this parser, do not delete it"
    )
    return names


def _browser_observable_services() -> frozenset[str]:
    """Services whose data a browser can reach at all: over the realtime bridge
    (an outbox subject in `PUBLIC_TOPICS`) or over REST (fronted by
    `api-gateway`)."""
    public = _public_topics()
    observable = set(_gateway_fronted_services())
    for service in _compose_services():
        package = _service_package(service)
        if package is not None and _outbox_subjects(package) & public:
            observable.add(service)
    return frozenset(observable)


def _needs_a_worker(service: str) -> frozenset[str]:
    """The subjects this service can only deliver via its outbox worker, and
    that something a browser can see depends on.

    An engine publishes a domain event by writing an outbox row; the only
    caller of `dispatch_ready_events` is the Arq cron in `workers/`. So an
    engine with an outbox that feeds a browser is inert without its worker
    deployed, however healthy its API looks.

    "Feeds a browser" has two shapes, and Phase 4E added the second:

    * **Directly** -- the subject is a `PUBLIC_TOPIC`, so `ws-gateway` bridges
      it. This is the whole rule through 4D.
    * **Transitively** -- a browser-observable engine *subscribes* to the
      subject and renders what it derives from it. `memory-engine` reaches the
      Digital Twin panel this way, through a subject that is not public and
      never will be (TDD 4E §8.3).

    Both hops are computed from source, so this stays a property rather than a
    list of engine names.
    """
    package = _service_package(service)
    if package is None:
        return frozenset()
    if not (package / "repository" / "outbox_dispatcher.py").is_file():
        return frozenset()
    if not (package / "workers" / "__init__.py").is_file():
        return frozenset()

    carried = _outbox_subjects(package)
    if not carried:
        return frozenset()

    needed = carried & _public_topics()
    for consumer in _browser_observable_services():
        if consumer == service:
            continue
        consumer_package = _service_package(consumer)
        if consumer_package is None:
            continue
        needed |= carried & _subscribable_subjects(consumer_package)
    return needed


# --- the job's list names things that exist ---------------------------------


@pytest.mark.parametrize("service", _started_services())
def test_every_started_service_is_defined_in_compose(service: str) -> None:
    assert service in _compose_services(), (
        f"the e2e job starts {service!r}, which docker-compose.local.yml does not define"
    )


# --- the job can actually observe what it asserts on -------------------------


@pytest.mark.parametrize("subject", sorted(GOLDEN_PATH_SUBJECTS))
def test_every_subject_the_golden_path_needs_has_a_running_publisher(subject: str) -> None:
    publishers = [
        service
        for service in _started_services()
        if (package := _service_package(service)) is not None
        and subject in _publishable_subjects(package)
    ]
    assert publishers, (
        f"the golden path asserts on {subject!r}, but no service the e2e job "
        f"starts declares it publishable. The assertion cannot pass; it will "
        f"time out reporting only the empty state it observed."
    )


@pytest.mark.parametrize("subject", sorted(GOLDEN_PATH_SUBJECTS))
def test_every_subject_the_golden_path_needs_is_bridgeable_to_a_browser(subject: str) -> None:
    assert subject in _public_topics(), (
        f"the golden path asserts on {subject!r}, which is not in ws-gateway's "
        f"PUBLIC_TOPICS, so the browser may not subscribe to it at all"
    )


@pytest.mark.parametrize("service", _started_services())
def test_an_outbox_engine_on_the_public_path_has_its_worker_started(service: str) -> None:
    """The defect that made AC-1 unreachable, stated as a property.

    `communication-engine` was started; `communication-engine-worker` was
    not. The engine accepted turns, ran the whole conversation, wrote both
    events to its outbox, and published neither.
    """
    topics = _needs_a_worker(service)
    if not topics:
        return
    worker = f"{service}-worker"
    started = _started_services()
    assert worker in _compose_services(), (
        f"{service} publishes {sorted(topics)} through its outbox, which only "
        f"its Arq worker dispatches, but compose defines no {worker!r}"
    )
    assert worker in started, (
        f"the e2e job starts {service} but not {worker!r}. Its outbox will "
        f"never be dispatched, so {sorted(topics)} never reach the bus and "
        f"the browser sees nothing -- with every container reporting healthy."
    )


@pytest.mark.parametrize("service", _started_services())
def test_a_started_worker_actually_runs_its_engines_worker_settings(service: str) -> None:
    """A `-worker` service that runs the API image's default command is the
    same defect wearing the right name: two API processes, no dispatcher."""
    if not service.endswith("-worker"):
        return
    engine = service.removesuffix("-worker")
    package = _service_package(engine)
    if package is None:
        return
    command = _compose_services()[service].get("command")
    assert command, f"{service} defines no command, so it runs the API image's entrypoint"
    joined = " ".join(command) if isinstance(command, list) else str(command)
    assert joined.startswith("arq "), f"{service}'s command is not an arq worker: {joined!r}"
    assert f"{package.name}.workers.WorkerSettings" in joined, (
        f"{service} runs {joined!r}, not {package.name}'s own WorkerSettings"
    )


# --- controls: these parsers must fail loudly, never silently pass -----------


def _agent_os_compose_services() -> dict[str, str]:
    """Compose service -> its Dockerfile path, for services built from `agent-os/`.

    Read from the compose file's own `build.dockerfile` rather than matched by
    name prefix, so renaming a service cannot quietly drop it from this rule.
    """
    found = {}
    for name, cfg in _compose_services().items():
        build = cfg.get("build")
        dockerfile = build.get("dockerfile") if isinstance(build, dict) else None
        if isinstance(dockerfile, str) and dockerfile.startswith("agent-os/"):
            found[name] = dockerfile
    return found


def test_every_agent_os_component_is_started_by_the_e2e_job() -> None:
    """AC-4's first clause, asserted rather than assumed.

    *"`agent-os` runs as containers under `docker compose up`"* is an
    acceptance criterion, and the e2e job is the only place the stack is ever
    started. A component that has a Dockerfile and a compose service but is
    absent from the job's list is scanned, built, and never once run -- which
    is exactly the state Phase 3E's condition C-3 recorded and Phase 4C's D-5
    exists to discharge.
    """
    agent_os = _agent_os_compose_services()
    assert agent_os, (
        "no compose service builds from `agent-os/`. Either D-5 was reverted "
        "or this parser broke; fix it, do not delete it."
    )
    started = set(_started_services())
    missing = sorted(name for name in agent_os if name not in started)
    assert not missing, (
        f"compose defines {missing} from agent-os Dockerfiles, but the e2e job "
        f"does not start them. AC-4 requires agent-os to run under `docker "
        f"compose up`; an image that builds is not an image that starts."
    )


def test_the_agent_os_library_has_no_container() -> None:
    """`agent-os/sdk/python` is a library, and master scope §10 says so.

    §4C's prose said "all four `agent-os` components", which reads as four
    containers. Three is correct -- the SDK ships like everything under
    `packages/`, with no Dockerfile and no compose service. Asserted here so
    the looser wording cannot turn into a fourth image later.
    """
    assert not (REPO_ROOT / "agent-os" / "sdk" / "python" / "Dockerfile").exists(), (
        "agent-os/sdk/python is a library (master scope §10) and must not have "
        "a Dockerfile"
    )
    for name, dockerfile in _agent_os_compose_services().items():
        assert "sdk" not in dockerfile, (
            f"compose service {name!r} builds from {dockerfile!r}; the SDK is "
            "not a deployable component"
        )


def test_the_started_service_list_is_not_empty_and_holds_the_known_stack() -> None:
    started = set(_started_services())
    # Not the whole list -- just enough that a parser returning junk cannot
    # make every parametrised test above vacuous.
    for expected in ("postgres", "nats", "migrations", "communication-engine", "ws-gateway"):
        assert expected in started, f"the parsed e2e service list is missing {expected!r}"


def test_the_worker_requirement_actually_fires_for_communication_engine() -> None:
    """A negative control for `_needs_a_worker`.

    If this ever returns empty, the parametrised test above passes for every
    service by doing nothing at all.
    """
    assert _needs_a_worker("communication-engine") >= {
        "communication.turn.received",
        "communication.intent.delivered",
    }


def test_the_worker_requirement_does_not_fire_for_engines_off_the_public_path() -> None:
    """The scope boundary, asserted rather than described.

    These have outboxes and undeployed workers. Their subjects reach no
    browser by either hop, so the rule above must not demand workers for them
    -- if it did, this file would be quietly widening a scope decision the
    compose file makes explicitly.

    `reasoning-engine` and `ai-model-orchestration-engine` were on this list
    until Phase 4B put `reasoning.process.*` and `ai_model.model.*` on
    `PUBLIC_TOPICS`. That is the rule working: making a subject
    browser-reachable is what obliges the stack to actually dispatch it, and
    both gained a compose worker in the same change.

    **`memory-engine` left this list in Phase 4E, for the same reason by a
    different route.** Nothing about `memory.*` became public -- TDD 4E §8.3
    keeps `PUBLIC_TOPICS` byte-identical at eighteen strings. What changed is
    that `digital-twin-engine` began deriving Bible Part 16's domains from
    `memory.long_term.created` and rendering them in a panel `api-gateway`
    fronts, making a non-public subject browser-visible one engine removed. It
    gained a compose worker in the same change, exactly as 4B's two did.

    `knowledge-engine` stays: it also consumes `memory.long_term.created`, but
    nothing it publishes reaches a browser by either hop, and its own handler
    for that subject is a documented no-op.
    """
    for service in ("world-model-engine", "knowledge-engine"):
        assert _needs_a_worker(service) == frozenset(), (
            f"{service} now feeds a browser through its outbox, directly or via "
            f"a browser-observable consumer; it needs its worker started, and "
            f"this control needs updating"
        )


def test_the_two_hop_rule_fires_for_memory_engine_through_the_digital_twin() -> None:
    """**Phase 4E's own precedent, pinned.**

    The positive half of the control above, and the regression guard on the
    defect CI found: `memory-engine` must need a worker, and must need it
    *because* a browser-observable engine consumes what its outbox carries --
    not because anything became public.

    Asserted as the full chain rather than as a boolean, so a future change
    that breaks any link fails here with the link named.
    """
    memory = _service_package("memory-engine")
    twin = _service_package("digital-twin-engine")
    assert memory is not None and twin is not None

    subject = "memory.long_term.created"
    assert subject in _outbox_subjects(memory), (
        "memory-engine no longer enqueues this subject onto its outbox; the "
        "Digital Twin's evidence source has moved and this rule needs revisiting"
    )
    assert subject in _subscribable_subjects(twin), (
        "digital-twin-engine no longer subscribes to this subject; AC-6's "
        "derivation has changed shape"
    )
    assert "digital-twin-engine" in _browser_observable_services(), (
        "digital-twin-engine is no longer browser-observable -- api-gateway "
        "stopped fronting /v1/digital-twin, which would make the panel dead"
    )
    assert subject not in _public_topics(), (
        "memory.long_term.created reached PUBLIC_TOPICS. TDD 4E §8.3 keeps that "
        "set byte-identical; if this is deliberate, the two-hop rule is no "
        "longer what makes memory-engine need a worker and this test should say so"
    )
    assert subject in _needs_a_worker("memory-engine")


def test_the_outbox_subject_parser_reads_real_call_sites() -> None:
    """Anti-vacuity control for `_outbox_subjects`.

    Returning empty for everything would make the whole rule inert -- every
    engine would need no worker and every parametrised case would pass by
    doing nothing. Two engines with known, stable outbox call sites pin it.
    """
    memory = _service_package("memory-engine")
    communication = _service_package("communication-engine")
    assert memory is not None and communication is not None
    assert _outbox_subjects(memory) >= {"memory.long_term.created", "memory.decision.recorded"}
    assert _outbox_subjects(communication) >= {"communication.turn.received"}


def test_the_outbox_parser_excludes_rpc_request_subjects() -> None:
    """The distinction that keeps the rule from over-firing, asserted directly.

    `digital-twin-engine` declares `communication.intent.deliver.request`
    publishable and sends it through `bus.request()`. Counting allow-list
    entries instead of outbox call sites made the rule demand a worker for it
    on that basis -- a subject no outbox has ever carried.
    """
    twin = _service_package("digital-twin-engine")
    assert twin is not None
    assert "communication.intent.deliver.request" in _publishable_subjects(twin)
    assert "communication.intent.deliver.request" not in _outbox_subjects(twin)
    assert _needs_a_worker("digital-twin-engine") == frozenset()


def test_the_gateway_fronted_parser_returns_the_real_route_table() -> None:
    """Anti-vacuity control for `_gateway_fronted_services`. An empty result
    would silently collapse the two-hop half to nothing."""
    fronted = _gateway_fronted_services()
    assert len(fronted) >= 6
    for expected in ("communication-engine", "autonomy-engine", "digital-twin-engine"):
        assert expected in fronted, f"api-gateway no longer fronts {expected!r}"


@pytest.mark.parametrize(
    ("service", "subject"),
    [
        ("reasoning-engine", "reasoning.process.completed"),
        ("ai-model-orchestration-engine", "ai_model.model.health_changed"),
    ],
)
def test_the_4b_panels_put_these_engines_on_the_public_path(
    service: str, subject: str
) -> None:
    """The positive half of the control above.

    If `_needs_a_worker` stopped returning these, the parametrised rule
    would pass for them by doing nothing -- and the Reasoning Trace and
    Health panels would silently go back to receiving no events.
    """
    assert subject in _needs_a_worker(service)
