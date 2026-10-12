"""This engine's real `WorkerSettings`, read through arq's own scheduling code.

`tools/tests/test_perception_dispatch_cadence.py` pins the source text. This
file asks arq what that text means: which instants the cron fires at, and what
`max_jobs` a worker built from these settings receives. D-4F-1 was reopened for
this engine's dispatch interval only (TDD 4F.8 §30).
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta

from arq.worker import get_kwargs
from nova_perception_engine.workers import WorkerSettings
from nova_perception_engine.workers.outbox_worker import arq_run_outbox_dispatch


def _next_runs(start: datetime, count: int) -> list[datetime]:
    """arq's own `CronJob.calculate_next`, on a copy so the shared settings
    object's `next_run` is never moved by a test."""
    (job,) = WorkerSettings.cron_jobs
    job = copy.copy(job)
    runs = []
    moment = start
    for _ in range(count):
        job.calculate_next(moment)
        assert job.next_run is not None
        runs.append(job.next_run)
        moment = job.next_run
    return runs


def test_the_only_cron_job_is_the_outbox_dispatch() -> None:
    (job,) = WorkerSettings.cron_jobs
    assert job.coroutine is arq_run_outbox_dispatch
    assert job.name == "cron:perception-engine:arq_run_outbox_dispatch"
    assert not job.run_at_startup


def test_arq_fires_the_dispatch_every_second_across_a_minute_boundary() -> None:
    """arq offsets every cron tick by its default `microsecond=123_456`."""
    start = datetime(2026, 10, 11, 12, 0, 57, 400_000, tzinfo=UTC)
    runs = _next_runs(start, 6)

    assert runs[0] == datetime(2026, 10, 11, 12, 0, 58, 123_456, tzinfo=UTC)
    assert [later - earlier for earlier, later in zip(runs, runs[1:], strict=False)] == [
        timedelta(seconds=1)
    ] * 5
    assert datetime(2026, 10, 11, 12, 1, 0, 123_456, tzinfo=UTC) in runs


def test_the_worker_arq_builds_from_these_settings_runs_one_job_at_a_time() -> None:
    """`arq.worker.create_worker` is `Worker(**get_kwargs(settings), ...)`, so
    this is the `max_jobs` the deployed worker receives."""
    kwargs = get_kwargs(WorkerSettings)
    assert kwargs["max_jobs"] == 1
    assert kwargs["queue_name"] == "arq:queue:perception-engine"
