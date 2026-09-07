"""The worker-isolation invariant, against a real Redis and real arq workers.

*Each engine's arq worker is the sole enqueuer and sole consumer of its own
scheduled jobs.* The unit tests next door prove the derivation; these prove the
two things the derivation is for, at the only layer where they are decidable --
Redis keyspace behaviour and arq's own job-claim loop.

Two synthetic services, `alpha-engine` and `beta-engine`. No engine is imported
(ADR-034), and none needs to be: the defect was never engine-specific. It was
that every engine schedules a coroutine called `arq_run_outbox_dispatch` onto
arq's one global queue, so `_make_dispatcher` below produces two genuinely
different coroutines that share a `__qualname__` -- the exact collision the
repository had.

`@pytest.mark.real_infra`: excluded from the default `pytest`/`turbo run test`
invocation (ADR-033); requires Docker. **Not executed in the environment this
file was written in** -- no reachable Docker daemon there, as has been true
throughout Phases 3 and 4.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Any

import pytest
from arq.connections import ArqRedis, RedisSettings, create_pool
from arq.constants import default_queue_name
from arq.cron import CronJob
from arq.worker import FailedJobs, Worker
from nova_service_kit import cron_job_name, service_cron, worker_queue_name
from redis.asyncio import Redis
from testcontainers.redis import RedisContainer

pytestmark = pytest.mark.real_infra

ALPHA = "alpha-engine"
BETA = "beta-engine"

_REDIS_CONTAINER_PORT = 6379
"""Matches `nova_testkit.redis`'s own constant -- the container-internal port,
resolved to the dynamically-assigned host port below, never assumed."""

#: A fixed millisecond timestamp standing in for one cron tick. `run_cron`
#: builds a job id as `f'{name}:{to_unix_ms(next_run)}'`, so pinning the
#: timestamp is what lets the collision below be asserted rather than raced.
TICK_MS = 1788709800000


_Dispatcher = Callable[[dict], Coroutine[Any, Any, None]]


def _make_dispatcher(service: str, drained: list[str]) -> _Dispatcher:
    """A stand-in for an engine's own outbox entrypoint.

    The inner function is named `arq_run_outbox_dispatch` deliberately: two
    dispatchers built here share a `__qualname__`, so `arq.cron()` derives one
    identity for both -- which is precisely why plain `cron()` collided across
    ten engines.
    """

    async def arq_run_outbox_dispatch(ctx: dict) -> None:
        drained.append(service)

    return arq_run_outbox_dispatch


@pytest.fixture
def drained() -> list[str]:
    """Which services' dispatchers actually ran, in order."""
    return []


@pytest.fixture
async def redis_dsn(redis_container: RedisContainer, redis_client: Redis) -> AsyncIterator[str]:
    """A DSN for the throwaway container. Depends on `redis_client` purely for
    its `FLUSHDB` isolation -- arq leaves `arq:job:` and result keys behind, and
    a leaked key from a previous test would make the collision assertions read
    the wrong answer."""
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(_REDIS_CONTAINER_PORT)
    yield f"redis://{host}:{port}/0"


async def _pool(dsn: str, queue: str) -> ArqRedis:
    return await create_pool(RedisSettings.from_dsn(dsn), default_queue_name=queue)


def _worker(dsn: str, queue: str, cron_job: CronJob) -> Worker:
    return Worker(
        cron_jobs=[cron_job],
        redis_settings=RedisSettings.from_dsn(dsn),
        queue_name=queue,
        burst=True,
        poll_delay=0.05,
        # pytest owns the process's signal handlers; arq must not take them.
        handle_signals=False,
    )


# --- the invariant ----------------------------------------------------------


async def test_each_worker_drains_only_its_own_queue(redis_dsn: str, drained: list[str]) -> None:
    """Beta's job is already queued when alpha's worker runs. Alpha must
    dispatch its own outbox and leave beta's job untouched -- not claim it, not
    fail it, not discard it."""
    alpha_queue, beta_queue = worker_queue_name(ALPHA), worker_queue_name(BETA)
    alpha_dispatch = _make_dispatcher(ALPHA, drained)
    beta_dispatch = _make_dispatcher(BETA, drained)
    alpha_cron = service_cron(ALPHA, alpha_dispatch, run_at_startup=True)
    beta_cron = service_cron(BETA, beta_dispatch, run_at_startup=True)

    # Beta's tick, already waiting in beta's own queue.
    pool = await _pool(redis_dsn, beta_queue)
    queued = await pool.enqueue_job(
        beta_cron.name, _job_id=f"{beta_cron.name}:{TICK_MS}", _queue_name=beta_queue
    )
    assert queued is not None

    alpha_worker = _worker(redis_dsn, alpha_queue, alpha_cron)
    try:
        # `run_check` raises FailedJobs if anything failed -- including the
        # `function ... not found` failure a stolen job produces.
        await alpha_worker.run_check(retry_jobs=False)
    finally:
        await alpha_worker.close()

    assert drained, "alpha's own cron tick never ran"
    assert set(drained) == {ALPHA}, "alpha drained something other than its own outbox"
    assert await pool.zcard(beta_queue) == 1, "alpha consumed beta's queued job"

    beta_worker = _worker(redis_dsn, beta_queue, beta_cron)
    try:
        await beta_worker.run_check(retry_jobs=False)
    finally:
        await beta_worker.close()

    # Beta's own worker drains beta's outbox, and only beta's. It may do so
    # more than once -- it consumes the tick placed above *and* the one its own
    # `run_at_startup` cron enqueues, which is arq behaving correctly and not
    # the property under test. What must hold is that neither engine ever ran
    # the other's dispatcher, so this counts rather than pinning a sequence.
    assert BETA in drained, "beta never drained its own outbox"
    assert drained.count(ALPHA) == 1, "beta ran alpha's dispatcher"
    assert await pool.zcard(alpha_queue) == 0
    assert await pool.zcard(beta_queue) == 0
    await pool.aclose()


async def test_distinct_cron_names_let_every_engine_enqueue_the_same_tick(
    redis_dsn: str, drained: list[str]
) -> None:
    """The half that distinct queues alone would **not** have fixed.

    `ArqRedis.enqueue_job` guards duplicates on `arq:job:<job_id>`, a key that
    carries no queue segment. Two engines deriving the same cron name therefore
    derive the same job id, and the second enqueue is a silent no-op *even
    when the two workers read different queues*.
    """
    alpha_queue, beta_queue = worker_queue_name(ALPHA), worker_queue_name(BETA)
    alpha_dispatch = _make_dispatcher(ALPHA, drained)
    beta_dispatch = _make_dispatcher(BETA, drained)

    # Both dispatchers share a `__qualname__`, so this is the one name arq
    # would have derived for both before `service_cron` existed.
    legacy_name = "cron:arq_run_outbox_dispatch"
    legacy_id = f"{legacy_name}:{TICK_MS}"

    pool = await _pool(redis_dsn, alpha_queue)
    first = await pool.enqueue_job(legacy_name, _job_id=legacy_id, _queue_name=alpha_queue)
    second = await pool.enqueue_job(legacy_name, _job_id=legacy_id, _queue_name=beta_queue)

    assert first is not None
    assert second is None, (
        "expected the un-namespaced arq:job: guard to swallow the second engine's "
        "enqueue -- if this ever passes, arq's collision behaviour changed and the "
        "cron-name half of this fix may no longer be load-bearing"
    )

    # The derived names are two ids, so both engines' ticks survive.
    alpha_id = f"{cron_job_name(ALPHA, alpha_dispatch)}:{TICK_MS}"
    beta_id = f"{cron_job_name(BETA, beta_dispatch)}:{TICK_MS}"
    assert alpha_id != beta_id

    alpha_job = await pool.enqueue_job(
        cron_job_name(ALPHA, alpha_dispatch), _job_id=alpha_id, _queue_name=alpha_queue
    )
    beta_job = await pool.enqueue_job(
        cron_job_name(BETA, beta_dispatch), _job_id=beta_id, _queue_name=beta_queue
    )

    assert alpha_job is not None
    assert beta_job is not None
    await pool.aclose()


# --- the negative control ---------------------------------------------------


async def test_sharing_arqs_default_queue_is_how_a_job_is_stolen_and_discarded(
    redis_dsn: str, drained: list[str]
) -> None:
    """The defect itself, reproduced, so the tests above cannot pass vacuously.

    On arq's shared `arq:queue`, alpha's worker claims beta's job, finds no
    function of that name, and fails it. `Worker.run_job` calls `job_failed`
    for this -- the job is finished and **never re-enqueued**, which is why the
    loss was permanent and silent apart from one WARNING line.
    """
    alpha_dispatch = _make_dispatcher(ALPHA, drained)
    beta_dispatch = _make_dispatcher(BETA, drained)
    alpha_cron = service_cron(ALPHA, alpha_dispatch, run_at_startup=True)
    beta_name = cron_job_name(BETA, beta_dispatch)

    pool = await _pool(redis_dsn, default_queue_name)
    queued = await pool.enqueue_job(
        beta_name, _job_id=f"{beta_name}:{TICK_MS}", _queue_name=default_queue_name
    )
    assert queued is not None

    # Alpha, sharing the default queue exactly as every engine did before.
    alpha_worker = _worker(redis_dsn, default_queue_name, alpha_cron)
    try:
        with pytest.raises(FailedJobs) as failure:
            await alpha_worker.run_check(retry_jobs=False)
    finally:
        await alpha_worker.close()

    assert failure.value.count == 1
    assert BETA not in drained, "beta's job ran; it should have been discarded unrun"
    assert await pool.zcard(default_queue_name) == 0, "the stolen job was not re-enqueued"
    await pool.aclose()
