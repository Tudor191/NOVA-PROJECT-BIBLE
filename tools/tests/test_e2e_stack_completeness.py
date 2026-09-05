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


def _publishable_subjects(package: Path) -> frozenset[str]:
    published = package / "events" / "published.py"
    if not published.is_file():
        return frozenset()
    block = re.search(
        r"PUBLISHABLE_SUBJECTS: frozenset\[str\] = frozenset\(\n\s*\{(.*?)\}\s*\)",
        published.read_text(),
        re.S,
    )
    if block is None:
        return frozenset()
    return frozenset(re.findall(r'"([^"]+)"', block.group(1)))


def _needs_a_worker(service: str) -> frozenset[str]:
    """The public topics this service can only deliver via its outbox worker.

    An engine publishes a domain event by writing an outbox row; the only
    caller of `dispatch_ready_events` is the Arq cron in `workers/`. So an
    engine with an outbox whose publishable set reaches a browser is
    inert without its worker deployed, however healthy its API looks.
    """
    package = _service_package(service)
    if package is None:
        return frozenset()
    if not (package / "repository" / "outbox_dispatcher.py").is_file():
        return frozenset()
    if not (package / "workers" / "__init__.py").is_file():
        return frozenset()
    return _publishable_subjects(package) & _public_topics()


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

    These three have outboxes and undeployed workers too. Their subjects
    reach no browser, so the rule above must not demand workers for them --
    if it did, this file would be quietly widening a scope decision the
    compose file makes explicitly.
    """
    for service in ("world-model-engine", "reasoning-engine", "ai-model-orchestration-engine"):
        assert _needs_a_worker(service) == frozenset(), (
            f"{service} now publishes a public topic through its outbox; it "
            f"needs its worker started, and this control needs updating"
        )
