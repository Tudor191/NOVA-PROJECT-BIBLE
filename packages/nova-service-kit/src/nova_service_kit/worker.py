"""Per-service arq identity -- the queue an engine's worker owns, and the name
its scheduled jobs are enqueued under.

**The invariant this module exists to hold:** *each engine's arq worker is the
sole enqueuer and sole consumer of its own scheduled jobs.* A cron tick
belonging to engine A must never be consumed by engine B, and a job belonging
to engine A must never be silently discarded by engine B.

Nothing in arq gives that for free, and losing it is silent. Two independent
mechanisms have to be defeated, which is why this module derives **two** names
rather than one:

1. **Enqueue collision.** `arq.cron.cron()` names a job
   ``'cron:' + coroutine.__qualname__`` when no ``name=`` is given
   (`arq/cron.py`), and `Worker.run_cron` builds the job id as
   ``f'{name}:{to_unix_ms(next_run)}'`` (`arq/worker.py`). Every engine in
   this repository schedules a coroutine called ``arq_run_outbox_dispatch``,
   so every engine derived the *identical* id for the same tick. The Redis key
   that guards a duplicate enqueue is ``arq:job:<job_id>`` -- **not namespaced
   by queue** -- and `ArqRedis.enqueue_job` returns ``None`` rather than
   raising when it already exists (`arq/connections.py`). So *one* job existed
   per tick where there should have been one per engine, and the other engines'
   enqueues vanished without a log line. Isolating the queue alone does not fix
   this; the name has to differ.

2. **Consume theft.** All workers share one Redis, and arq's default queue is
   the single global ``arq:queue``. Whichever worker polled first claimed that
   one job and ran *its own* coroutine of that name -- draining its own outbox
   and no one else's. When the function genuinely was not registered (one
   engine's `arq_run_health_checks` landing on another engine's worker),
   `Worker.run_job` logs ``function ... not found`` and calls ``job_failed``:
   the job is finished and **never re-enqueued**. Isolating the name alone does
   not fix this; the queue has to differ.

Both were latent for as long as the local stack ran a single worker. The
Phase 4B E2E stack runs four, and `communication-engine`'s outbox was then
dispatched on roughly one tick in four -- see the Phase 4B Gate Review's G-8.

Per ADR-034 this module carries **zero engine-specific knowledge**: the service
name is always the caller's own, passed in, never looked up or branched on
here. It imports `arq` and nothing else.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from arq import cron

if TYPE_CHECKING:
    from arq.cron import CronJob
    from arq.typing import WorkerCoroutine

QUEUE_NAME_PREFIX = "arq:queue:"
"""Deliberately a prefix *extension* of arq's own default ``arq:queue``, so a
queue this module derives is recognisable as an arq queue by anything reading
Redis directly, while never being equal to the shared default."""

CRON_NAME_PREFIX = "cron:"
"""Matches arq's own convention (`arq/cron.py` derives ``'cron:' +
__qualname__``), so the derived names read the same way in arq's logs -- with
the service segment added between the prefix and the coroutine."""


def worker_queue_name(service: str) -> str:
    """The arq queue owned exclusively by `service`'s worker.

    Pass the engine's own name -- the same string it already gives
    `bind_event_bus` -- so one identity spans the bus and the job queue rather
    than two that can drift apart.

        >>> worker_queue_name("communication-engine")
        'arq:queue:communication-engine'
    """
    return f"{QUEUE_NAME_PREFIX}{_require_service(service)}"


def service_cron(service: str, coroutine: WorkerCoroutine, **schedule: Any) -> CronJob:
    """`arq.cron()`, with the job named for the service that owns it.

    Every keyword `arq.cron()` accepts is forwarded untouched -- this changes
    the job's *identity*, never its schedule or its execution semantics.
    ``name`` is the one exception and is rejected rather than forwarded: a
    caller-supplied name would reintroduce exactly the collision this function
    exists to prevent, and doing so silently is how the defect survived.

        >>> service_cron("memory-engine", arq_run_embedding_pass, second={5, 35}).name
        'cron:memory-engine:arq_run_embedding_pass'
    """
    if "name" in schedule:
        raise TypeError(
            "service_cron() derives the job name from `service` and `coroutine`; "
            "passing `name=` would defeat the per-service isolation it exists to "
            "provide. Use arq.cron() directly if a hand-written name is genuinely "
            "wanted."
        )
    return cron(coroutine, name=cron_job_name(service, coroutine), **schedule)


def cron_job_name(service: str, coroutine: WorkerCoroutine) -> str:
    """The name `service_cron` gives a job. Exported because tests and
    diagnostics need to name a job without building one."""
    return f"{CRON_NAME_PREFIX}{_require_service(service)}:{coroutine.__qualname__}"


def _require_service(service: str) -> str:
    """An empty or whitespace service name would derive ``arq:queue:`` -- a
    distinct-looking string that is nonetheless shared by every caller that
    made the same mistake. Refused at the point it is made."""
    if not service or not service.strip():
        raise ValueError("service must be a non-empty engine name, e.g. 'memory-engine'.")
    return service
