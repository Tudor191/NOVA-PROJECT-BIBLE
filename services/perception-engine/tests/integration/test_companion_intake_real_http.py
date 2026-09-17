"""**S-2, joined: a real OS event becomes a real HTTP request this engine serves.**

Finding F-3 was that S-2 existed as two halves that never met — the Rust client
proven against a stub server, the Python route proven through `TestClient`'s
in-process ASGI transport. Neither half is evidence that the *pipeline* works,
because the thing that breaks a pipeline is the seam.

Everything on the path here is the shipped article:

| Segment | What runs |
|---|---|
| The event | A real write to a real temp directory |
| Detection | The real `notify` watcher, in the real `nova-companion` binary |
| The process | The real `main()` → `run()` loop, spawned, configured by environment only |
| Transport | Real HTTP over a real TCP socket to a real uvicorn server |
| The server | This engine's own `uvicorn[standard]` dependency, not a test stack |
| The engine | The real `create_app`, real lifespan, real sensor registry, real route,
  real `domain/workspace.py` |

**The repository is the one fake, deliberately.** This file's claim is about
transport and intake; persistence is S-3's claim and is proven against real
Postgres in `test_workspace_real_postgres_e2e.py`, over this same harness. Using
a fake here keeps the evidence captured *at the Python intake boundary*, which
is where S-2 is decided, and keeps this file runnable without Docker.

Marked `real_infra` because it needs a real toolchain and spawns real processes,
so it belongs in the staged tier rather than in `turbo run test` — not because
it needs a container. It deliberately uses no container fixture.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
from nova_perception_engine.config import Settings
from nova_perception_engine.domain.workspace import label_for_path, object_id_for_path
from nova_perception_engine.main import create_app

from tests.fakes.ai_model_port import FakeAIModelOrchestrationPort
from tests.fakes.repository import FakePerceptionRepository
from tests.integration.companion_harness import (
    SETTLE_SECONDS,
    RunningCompanion,
    RunningEngine,
    build_companion,
    serve,
    start_companion,
    stop_companion,
    wait_until,
)

pytestmark = pytest.mark.real_infra

_PRIMARY_USER_ID = uuid4()
_ENCRYPTION_KEY = "3ktMjuHsQ9TNWhEiReuORzkawsz4KEYq2zDMZByQhHo="  # test-only Fernet key

#: Directory names with real identifying shape, so "the path did not leak" is a
#: meaningful assertion rather than one a short name satisfies by accident.
PROJECT_DIR = "analytical-engine"
NESTED_DIR = "design"
FILE_NAME = "notes.md"
SEGMENTS = (PROJECT_DIR, NESTED_DIR)


@pytest.fixture(scope="session")
def companion_binary() -> Path:
    return build_companion()


@pytest.fixture
def repository() -> FakePerceptionRepository:
    return FakePerceptionRepository()


@pytest.fixture
async def engine(
    repository: FakePerceptionRepository, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[RunningEngine]:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(
        Settings(primary_user_id=_PRIMARY_USER_ID, template_encryption_key=_ENCRYPTION_KEY),
        repository=repository,
        ai_model_port=FakeAIModelOrchestrationPort(),
    )
    async for running in serve(app):
        yield running


@pytest.fixture
def watch_root(tmp_path: Path) -> Path:
    root = tmp_path / "home" / "ada" / "projects"
    (root / PROJECT_DIR / NESTED_DIR).mkdir(parents=True)
    return root


@pytest.fixture
def companion(
    companion_binary: Path, watch_root: Path, engine: RunningEngine
) -> AsyncIterator[RunningCompanion]:
    running = start_companion(
        companion_binary, watch_root=watch_root, base_url=engine.base_url
    )
    try:
        yield running
    finally:
        stop_companion(running)


def _rows(repository: FakePerceptionRepository) -> list:
    return list(repository.outbox.values())


async def test_s2_a_real_file_write_reaches_this_engine_over_real_http(
    companion: RunningCompanion,
    repository: FakePerceptionRepository,
    watch_root: Path,
) -> None:
    """**S-2, in one assertion.**

    Nothing in this test touches the engine directly: it writes a file, and the
    only thing that can turn that into an outbox event is the companion process
    detecting it and posting it over the socket.
    """
    target = watch_root / PROJECT_DIR / NESTED_DIR / FILE_NAME
    target.write_text("real content written by the test")

    arrived = await wait_until(lambda: _rows(repository))

    assert arrived, (
        f"no observation reached the engine. Companion output:\n{companion.raw_output()}"
    )
    assert arrived[0].subject == "perception.workspace.observed"


async def test_s2_the_engine_received_the_real_path_and_hashed_it_itself(
    companion: RunningCompanion,
    repository: FakePerceptionRepository,
    watch_root: Path,
) -> None:
    """**D-4F3-2's division of labour, observed rather than asserted about.**

    The companion sends the real path; this engine is the only thing that turns
    one into a handle. The `object_id` that lands in the outbox therefore has to
    equal this engine's own hash of the real on-disk path — which also proves
    the companion sent the genuine canonical path and not something it invented.
    """
    target = watch_root / PROJECT_DIR / NESTED_DIR / FILE_NAME
    target.write_text("content")
    resolved = target.resolve()

    rows = await wait_until(lambda: _rows(repository))
    assert rows, f"no observation reached the engine:\n{companion.raw_output()}"

    assert rows[0].payload["object_id"] == object_id_for_path(str(resolved))
    assert rows[0].payload["label"] == label_for_path(str(resolved)) == FILE_NAME


async def test_s2_the_observed_at_is_the_files_own_mtime_end_to_end(
    companion: RunningCompanion,
    repository: FakePerceptionRepository,
    watch_root: Path,
) -> None:
    """§20.1 forbids a fabricated timestamp. The one that survives the whole
    chain — mtime → Rust `SystemTime` → RFC3339 → Pydantic `datetime` → payload
    — must still be the file's own, so it is compared against the filesystem."""
    from datetime import UTC, datetime

    target = watch_root / PROJECT_DIR / FILE_NAME
    target.write_text("content")

    rows = await wait_until(lambda: _rows(repository))
    assert rows, f"no observation reached the engine:\n{companion.raw_output()}"

    on_disk = datetime.fromtimestamp(target.stat().st_mtime, tz=UTC)
    published = datetime.fromisoformat(rows[0].payload["observed_at"])
    assert abs((published - on_disk).total_seconds()) < 1.0, (
        f"observed_at {published} is not the file's own mtime {on_disk}"
    )


async def test_s2_identity_is_resolved_server_side_not_supplied_by_the_companion(
    companion: RunningCompanion,
    repository: FakePerceptionRepository,
    watch_root: Path,
) -> None:
    """ADR-025 across the seam: the companion has no `user_id` to send and no
    field to send it in, so the one on the event can only have come from
    `Settings.primary_user_id`."""
    (watch_root / PROJECT_DIR / FILE_NAME).write_text("content")

    rows = await wait_until(lambda: _rows(repository))
    assert rows, f"no observation reached the engine:\n{companion.raw_output()}"
    assert rows[0].payload["user_id"] == str(_PRIMARY_USER_ID)


async def test_s2_a_burst_from_one_real_write_yields_exactly_one_event(
    companion: RunningCompanion,
    repository: FakePerceptionRepository,
    watch_root: Path,
) -> None:
    """A single write emits several real OS events (a create and one or more
    content modifications). The debouncer is what makes that one observation,
    and this is the first time it has been exercised against a genuine burst
    rather than against timestamps chosen by a test."""
    import asyncio

    (watch_root / PROJECT_DIR / FILE_NAME).write_text("content")

    assert await wait_until(lambda: _rows(repository)), companion.raw_output()
    await asyncio.sleep(SETTLE_SECONDS)

    assert len(_rows(repository)) == 1, (
        f"a single write produced {len(_rows(repository))} events: "
        f"{[row.payload for row in _rows(repository)]}"
    )


async def test_s2_a_file_outside_the_configured_root_is_never_submitted(
    companion: RunningCompanion,
    repository: FakePerceptionRepository,
    watch_root: Path,
    tmp_path: Path,
) -> None:
    """**D-4F3-3's containment, across the whole pipeline.** Writing beside the
    configured root rather than inside it must produce nothing here.

    The in-root write is the liveness control: without it this would pass simply
    because nothing had been reported yet.
    """
    import asyncio

    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "secret.md").write_text("must never be observed")
    (watch_root / PROJECT_DIR / FILE_NAME).write_text("content")

    rows = await wait_until(lambda: _rows(repository))
    assert rows, (
        f"the in-root write was not detected, so this proves nothing:\n"
        f"{companion.raw_output()}"
    )
    await asyncio.sleep(SETTLE_SECONDS)

    serialized = str([row.payload for row in _rows(repository)])
    assert "secret.md" not in serialized
    assert "elsewhere" not in serialized
    assert len(_rows(repository)) == 1


async def test_s4_no_path_segment_survives_into_the_event_payload(
    companion: RunningCompanion,
    repository: FakePerceptionRepository,
    watch_root: Path,
) -> None:
    """**S-4 at the intake boundary**, against a path that really existed on a
    real disk rather than a literal chosen to look like one.

    Checked over the whole serialized payload rather than one field: a leak into
    any field is equally bad, and checking `object_id` alone would miss it.
    """
    target = watch_root / PROJECT_DIR / NESTED_DIR / FILE_NAME
    target.write_text("content")
    resolved = str(target.resolve())

    rows = await wait_until(lambda: _rows(repository))
    assert rows, f"no observation reached the engine:\n{companion.raw_output()}"

    serialized = str(rows[0].payload)
    assert resolved not in serialized
    for segment in SEGMENTS:
        assert segment not in serialized, f"path segment {segment!r} leaked into the payload"
    # The file name is present, and is meant to be: `label` is display text.
    assert rows[0].payload["label"] == FILE_NAME


async def test_f6_the_companion_run_loop_really_ran_and_reported_each_submission(
    companion: RunningCompanion,
    repository: FakePerceptionRepository,
    watch_root: Path,
) -> None:
    """**F-6's evidence.** `run()` had no test of its own; it has one now, and
    it is this file rather than a unit test — every other assertion here is
    already proof that the loop executed, because nothing else submits.

    This one reads the loop's own structured output, which is the part not
    otherwise observable: that it logged `observation_submitted` with the
    engine's real verdict, and that its log lines carry a file name and no
    directory chain (**F-7's discipline, end to end**).
    """
    (watch_root / PROJECT_DIR / NESTED_DIR / FILE_NAME).write_text("content")
    assert await wait_until(lambda: _rows(repository)), companion.raw_output()

    stop_companion(companion)  # drain the pipe; idempotent with the fixture's own call
    logs = companion.logs()

    submitted = [line for line in logs if line.get("message") == "observation_submitted"]
    assert submitted, f"run() logged no submission; output was:\n{companion.raw_output()}"
    assert submitted[0]["published"] is True
    assert submitted[0]["file"] == FILE_NAME
    assert submitted[0]["service"] == "nova-companion"

    # F-7's rule applied to every line the daemon emitted, not just the happy
    # one: the startup line names the configured root deliberately, so it is
    # the single documented exception.
    for line in logs:
        if line.get("message") == "nova-companion starting":
            continue
        assert NESTED_DIR not in str(line), f"a directory name reached a log line: {line}"
