"""`nova_service_kit.worker` -- the derivation itself, and the two arq
mechanisms it exists to defeat.

The assertions that matter are the ones about *arq's* behaviour, not this
module's string formatting: a helper that derived a pretty name arq then
ignored would be worse than no helper, because it would look like isolation
while providing none. So the tests below reach into the real `CronJob` arq
returns and into arq's real job-id construction, rather than only comparing
the strings this module produces.
"""

from __future__ import annotations

import pytest
from arq import cron
from arq.cron import CronJob
from nova_service_kit import (
    CRON_NAME_PREFIX,
    QUEUE_NAME_PREFIX,
    cron_job_name,
    service_cron,
    worker_queue_name,
)


async def arq_run_outbox_dispatch(ctx: dict) -> None:
    """Deliberately named exactly as every engine's own outbox entrypoint is.
    That collision is the defect; reproducing it here is the point."""


async def arq_run_embedding_pass(ctx: dict) -> None:
    """The second real collision: `memory-engine` and `knowledge-engine` both
    schedule a coroutine of this name."""


# --- the derivation ---------------------------------------------------------


def test_queue_name_is_namespaced_by_service() -> None:
    assert worker_queue_name("memory-engine") == "arq:queue:memory-engine"


def test_queue_name_is_never_arqs_shared_default() -> None:
    # `arq:queue` is the queue every worker lands on when `queue_name` is
    # unset. A derived name must never be able to equal it, whatever the
    # service is called.
    from arq.constants import default_queue_name

    for service in ("memory-engine", "a", "arq:queue"):
        assert worker_queue_name(service) != default_queue_name
        assert worker_queue_name(service).startswith(QUEUE_NAME_PREFIX)


def test_cron_name_carries_the_service_between_prefix_and_coroutine() -> None:
    assert (
        cron_job_name("memory-engine", arq_run_embedding_pass)
        == "cron:memory-engine:arq_run_embedding_pass"
    )
    assert cron_job_name("memory-engine", arq_run_embedding_pass).startswith(CRON_NAME_PREFIX)


@pytest.mark.parametrize("service", ["", "   ", "\t"])
def test_an_empty_service_name_is_refused_rather_than_derived_from(service: str) -> None:
    # `arq:queue:` looks distinct but is shared by every caller that made the
    # same mistake -- the original defect with an extra colon.
    with pytest.raises(ValueError, match="non-empty engine name"):
        worker_queue_name(service)
    with pytest.raises(ValueError, match="non-empty engine name"):
        cron_job_name(service, arq_run_outbox_dispatch)


# --- what arq actually receives ---------------------------------------------


def test_service_cron_returns_a_real_cronjob_carrying_the_derived_name() -> None:
    job = service_cron("memory-engine", arq_run_outbox_dispatch, second={0, 30})

    assert isinstance(job, CronJob)
    assert job.name == "cron:memory-engine:arq_run_outbox_dispatch"
    assert job.coroutine is arq_run_outbox_dispatch


def test_service_cron_forwards_the_schedule_untouched() -> None:
    # Identity is the only thing this helper changes. A helper that also
    # perturbed the schedule would silently re-time every engine's outbox.
    schedule = {"second": {0, 10, 20, 30, 40, 50}}
    plain = cron(arq_run_outbox_dispatch, **schedule)
    derived = service_cron("planning-engine", arq_run_outbox_dispatch, **schedule)

    for field in ("month", "day", "weekday", "hour", "minute", "second", "microsecond"):
        assert getattr(derived, field) == getattr(plain, field), field
    assert derived.run_at_startup == plain.run_at_startup
    assert derived.unique == plain.unique
    assert derived.max_tries == plain.max_tries
    assert derived.timeout_s == plain.timeout_s


def test_a_hand_written_name_is_refused_rather_than_silently_forwarded() -> None:
    with pytest.raises(TypeError, match="defeat the per-service isolation"):
        service_cron(
            "planning-engine",
            arq_run_outbox_dispatch,
            name="cron:arq_run_outbox_dispatch",
            second={0},
        )


# --- the defect, reproduced -------------------------------------------------


def test_plain_arq_cron_gives_two_engines_the_same_job_name() -> None:
    """The bug, stated as a test. Two engines, two distinct coroutines that
    happen to share a name, one arq identity -- so `Worker.run_cron` derives
    the same `f'{name}:{timestamp}'` job id for both, and the second
    `enqueue_job` is a silent no-op against the un-namespaced `arq:job:` key."""

    # arq names a job after the coroutine alone. `memory-engine` and
    # `knowledge-engine` each define their own `arq_run_embedding_pass`; both
    # arrive at this one identity.
    assert cron(arq_run_embedding_pass).name == "cron:arq_run_embedding_pass"
    assert cron(arq_run_outbox_dispatch).name == "cron:arq_run_outbox_dispatch"


def test_the_derivation_separates_what_plain_cron_collided() -> None:
    memory = service_cron("memory-engine", arq_run_embedding_pass, second={5, 35})
    knowledge = service_cron("knowledge-engine", arq_run_embedding_pass, second={5, 35})

    assert cron(arq_run_embedding_pass).name == cron(arq_run_embedding_pass).name
    assert memory.name != knowledge.name
    assert worker_queue_name("memory-engine") != worker_queue_name("knowledge-engine")
