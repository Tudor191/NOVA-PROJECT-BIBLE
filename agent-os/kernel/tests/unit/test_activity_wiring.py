"""Phase 4C milestone 4C.2d -- `agent_activity` wired into the real Kernel
lifecycle (`domain/scheduler.py`, `domain/reconciliation.py`).

4C.2b built the append-only table and the transactional repository surface;
4C.2c exposed it read-only. Neither wrote a row from a real transition. These
tests assert that the six `AgentActivityKind` members are produced by the
lifecycle paths that already existed -- and, as importantly, that **nothing
produces one when the transition did not happen**.

**Why the transaction assertions look the way they do.** Whether a coupled
write is atomic is `PostgresKernelRepository`'s property, already proven
against real Postgres in 4C.2b (`test_insert_commits_the_instance_and_its
_activity_together`, `test_a_failed_insert_rolls_back_its_activity_too`).
What 4C.2d can get wrong is different and is what is checked here: passing the
activity to a *separate* `append_activity` call instead of to the mutation
itself, which would compile, pass a naive "was a row written" test, and
silently reintroduce the two-transaction split. `_RecordingRepository` records
the shape of every call, so a regression to two calls fails a test rather than
going unnoticed. `tests/integration/test_repository_real_postgres.py` closes
the loop against a real database.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid4

import pytest
from nova_agent_os_kernel.domain.activity import AgentActivity, AgentActivityKind
from nova_agent_os_kernel.domain.models import AgentInstance, AgentInstanceHandle
from nova_agent_os_kernel.domain.reconciliation import reconcile_running_instances
from nova_agent_os_kernel.domain.scheduler import dispatch_task_node
from nova_contracts import (
    AgentMessage,
    AgentMessageType,
    AgentPackageSnapshot,
    AgentResult,
    TaskNodeSnapshot,
    ValidationOutcome,
)

from tests.fakes.event_publisher import FakeEventPublisher
from tests.fakes.ports import FakeAgentExecutionBackend, FakeRegistryPort, FakeSupervisorPort
from tests.fakes.repository import FakeKernelRepository

# --- harness --------------------------------------------------------------


class _RecordingRepository(FakeKernelRepository):
    """`FakeKernelRepository` plus a log of how each activity arrived.

    `coupled` holds `(method, kind)` for an activity passed to a state
    mutation; `standalone` holds the kinds that came through
    `append_activity`. A kind appearing in the wrong list is the regression
    these tests exist to catch.

    `fail_activity_kind` makes the activity write raise where the real
    repository's `_append` would hit a constraint, so the caller's error
    handling can be exercised without a database.
    """

    def __init__(self, *, fail_activity_kind: AgentActivityKind | None = None) -> None:
        super().__init__()
        self.coupled: list[tuple[str, AgentActivityKind]] = []
        self.standalone: list[AgentActivityKind] = []
        self.mutation_calls: list[str] = []
        self._fail_activity_kind = fail_activity_kind

    async def insert(
        self, instance: AgentInstance, *, activity: AgentActivity | None = None
    ) -> AgentInstance:
        self.mutation_calls.append("insert")
        if activity is not None:
            self.coupled.append(("insert", activity.kind))
        return await super().insert(instance, activity=activity)

    async def update_status(
        self,
        instance_id: UUID,
        *,
        status: str,
        health_status: str | None = None,
        activity: AgentActivity | None = None,
    ) -> None:
        self.mutation_calls.append("update_status")
        if activity is not None:
            self.coupled.append(("update_status", activity.kind))
        await super().update_status(
            instance_id, status=status, health_status=health_status, activity=activity
        )

    async def append_activity(self, activity: AgentActivity) -> None:
        self.standalone.append(activity.kind)
        await super().append_activity(activity)

    def _append(self, activity: AgentActivity) -> None:
        if activity.kind is self._fail_activity_kind:
            raise RuntimeError(f"activity persistence failed for {activity.kind.value}")
        super()._append(activity)

    # --- assertions helpers ---

    async def activities(self, instance_id: UUID) -> list[AgentActivity]:
        """Oldest first -- the lifecycle order, which reads better in a test
        than the newest-first order the API pages in."""
        page = await self.list_activity(instance_id, limit=100)
        return list(reversed(page.items))

    async def kinds(self, instance_id: UUID) -> list[AgentActivityKind]:
        return [activity.kind for activity in await self.activities(instance_id)]

    def all_activity(self) -> list[AgentActivity]:
        return list(self._activity.values())


def _node(**overrides: object) -> TaskNodeSnapshot:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "objective": "Research rate limiting approaches",
        "depends_on": [],
        "assigned_agent_category": "research",
        "effort_hours": 1.0,
        "confidence": 0.7,
        "risk": "low",
        "status": "ready",
    }
    defaults.update(overrides)
    return TaskNodeSnapshot(**defaults)


def _package(**overrides: object) -> AgentPackageSnapshot:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "category": "research",
        "version": "0.1.0",
        "manifest_json": {"id": "research-agent", "version": "0.1.0"},
        "health_status": "healthy",
    }
    defaults.update(overrides)
    return AgentPackageSnapshot(**defaults)


def _reviewable_package() -> AgentPackageSnapshot:
    return _package(
        category="coding",
        manifest_json={
            "id": "coding-agent",
            "version": "0.1.0",
            "peer_reviewer_category": "architect",
        },
    )


def _result(*, task_node_id: UUID, correlation_id: UUID, status: str) -> AgentResult:
    return AgentResult(
        agent_instance_id=uuid4(),
        task_node_id=task_node_id,
        status=status,
        output={"finding": "token-bucket rate limiting"},
        confidence=0.9 if status == "success" else None,
        self_validation_passed=status == "success",
        correlation_id=correlation_id,
    )


def _handle(
    *, task_node_id: UUID, correlation_id: UUID, status: str = "success", review: bool = False
) -> AgentInstanceHandle:
    result = _result(task_node_id=task_node_id, correlation_id=correlation_id, status=status)
    return AgentInstanceHandle(
        instance_id=result.agent_instance_id,
        result=result,
        validation=ValidationOutcome(
            passed=status == "success", requires_peer_review=review
        ),
    )


def _crashed_handle() -> AgentInstanceHandle:
    """The backend itself raised -- `result`/`validation` are both `None`,
    which is the only case that carries exception text."""
    return AgentInstanceHandle(instance_id=uuid4(), error="on_load raised RuntimeError")


def _review_reply(*, status: str, correlation_id: UUID) -> AgentMessage:
    reviewer_result = AgentResult(
        agent_instance_id=uuid4(),
        task_node_id=uuid4(),
        status=status,
        output={"verdict": status},
        confidence=0.8,
        self_validation_passed=status == "success",
        correlation_id=correlation_id,
    )
    return AgentMessage(
        message_type=AgentMessageType.PEER_REVIEW_RESULT,
        from_instance_id=uuid4(),
        to_instance_id=uuid4(),
        payload=reviewer_result.model_dump(mode="json"),
        correlation_id=correlation_id,
    )


async def _dispatch(
    *,
    repository: _RecordingRepository,
    handles: list[AgentInstanceHandle],
    node: TaskNodeSnapshot | None = None,
    package: AgentPackageSnapshot | None = None,
    correlation_id: UUID | None = None,
    restart_instance_ids: list[UUID] | None = None,
    peer_validation: Literal["approved", "rejected", "timed_out", "not_required"] = (
        "not_required"
    ),
    review_replies: list[AgentMessage | None] | None = None,
    reviewer_package: AgentPackageSnapshot | None = None,
) -> tuple[UUID | None, UUID, FakeSupervisorPort]:
    """One `dispatch_task_node` run. Returns `(dispatched_id, correlation_id,
    supervisor_port)`."""
    node = node if node is not None else _node()
    correlation_id = correlation_id if correlation_id is not None else uuid4()
    primary_package = package if package is not None else _package()
    supervisor_port = FakeSupervisorPort(
        restart_instance_ids=restart_instance_ids, peer_validation=peer_validation
    )
    # `find_healthy_package` answers both the primary lookup and the reviewer
    # lookup; a reviewer-specific package is supplied only where a test needs
    # the two to differ.
    registry_port = FakeRegistryPort(
        package=reviewer_package if reviewer_package is not None else primary_package
    )
    dispatched = await dispatch_task_node(
        node,
        repository=repository,
        registry_port=registry_port,
        supervisor_port=supervisor_port,
        execution_backend=FakeAgentExecutionBackend(
            handles=handles, review_replies=review_replies
        ),
        event_publisher=FakeEventPublisher(),
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )
    return dispatched, correlation_id, supervisor_port


# --- 1. dispatched --------------------------------------------------------


async def test_a_dispatch_writes_exactly_one_dispatched_activity() -> None:
    repository = _RecordingRepository()
    node = _node()
    handle = _handle(task_node_id=node.id, correlation_id=uuid4())

    instance_id, _correlation_id, _sup = await _dispatch(
        repository=repository, handles=[handle], node=node
    )

    assert instance_id is not None
    kinds = await repository.kinds(instance_id)
    assert kinds.count(AgentActivityKind.DISPATCHED) == 1
    assert kinds[0] is AgentActivityKind.DISPATCHED, "dispatch is recorded before the outcome"


async def test_dispatched_activity_carries_its_own_instance_id() -> None:
    repository = _RecordingRepository()
    node = _node()

    instance_id, _c, _s = await _dispatch(
        repository=repository,
        handles=[_handle(task_node_id=node.id, correlation_id=uuid4())],
        node=node,
    )

    assert instance_id is not None
    for activity in await repository.activities(instance_id):
        assert activity.agent_instance_id == instance_id


async def test_dispatched_detail_holds_exactly_the_intended_fields() -> None:
    repository = _RecordingRepository()
    node = _node()
    package = _package()

    instance_id, _c, _s = await _dispatch(
        repository=repository,
        handles=[_handle(task_node_id=node.id, correlation_id=uuid4())],
        node=node,
        package=package,
    )

    assert instance_id is not None
    dispatched = (await repository.activities(instance_id))[0]
    assert dispatched.detail == {
        "task_node_id": str(node.id),
        "category": "research",
        "agent_package_id": str(package.id),
        "execution_backend": "inprocess",
    }


# --- 2/3. completed and failed -------------------------------------------


async def test_a_successful_run_writes_exactly_one_completed_activity() -> None:
    repository = _RecordingRepository()
    node = _node()

    instance_id, _c, _s = await _dispatch(
        repository=repository,
        handles=[_handle(task_node_id=node.id, correlation_id=uuid4())],
        node=node,
    )

    assert instance_id is not None
    kinds = await repository.kinds(instance_id)
    assert kinds == [AgentActivityKind.DISPATCHED, AgentActivityKind.COMPLETED]
    completed = (await repository.activities(instance_id))[1]
    assert completed.detail == {"task_node_id": str(node.id), "outcome": "success"}


async def test_a_failed_run_writes_exactly_one_failed_activity() -> None:
    repository = _RecordingRepository()
    node = _node()

    instance_id, _c, _s = await _dispatch(
        repository=repository,
        handles=[_handle(task_node_id=node.id, correlation_id=uuid4(), status="failure")],
        node=node,
    )

    assert instance_id is not None
    kinds = await repository.kinds(instance_id)
    assert kinds == [AgentActivityKind.DISPATCHED, AgentActivityKind.FAILED]
    failed = (await repository.activities(instance_id))[1]
    assert failed.detail == {"task_node_id": str(node.id), "outcome": "failure"}
    assert "error" not in failed.detail, (
        "a status='failure' AgentResult is a successfully-produced failure and "
        "carries no exception text"
    )


async def test_a_crashed_run_records_the_exception_text() -> None:
    repository = _RecordingRepository()
    node = _node()

    instance_id, _c, _s = await _dispatch(
        repository=repository, handles=[_crashed_handle()], node=node
    )

    assert instance_id is not None
    failed = (await repository.activities(instance_id))[1]
    assert failed.kind is AgentActivityKind.FAILED
    assert failed.detail == {
        "task_node_id": str(node.id),
        "outcome": "failure",
        "error": "on_load raised RuntimeError",
    }


# --- 4/5. restart_planned -------------------------------------------------


async def test_a_planned_restart_writes_exactly_one_restart_planned_activity() -> None:
    repository = _RecordingRepository()
    node = _node()
    first = _handle(task_node_id=node.id, correlation_id=uuid4(), status="failure")
    retry = _handle(task_node_id=node.id, correlation_id=uuid4())

    retry_id, _c, supervisor = await _dispatch(
        repository=repository,
        handles=[first, retry],
        node=node,
        restart_instance_ids=[first.instance_id],
    )

    assert supervisor.calls, "the Supervisor really was consulted"
    failed_kinds = await repository.kinds(first.instance_id)
    assert failed_kinds == [
        AgentActivityKind.DISPATCHED,
        AgentActivityKind.FAILED,
        AgentActivityKind.RESTART_PLANNED,
    ]
    restart = (await repository.activities(first.instance_id))[2]
    assert restart.detail == {"category": "research", "planned_by": "supervisor"}

    # The retry is a second instance with its own pair -- not a duplicate of
    # the first instance's rows.
    assert retry_id == retry.instance_id
    assert await repository.kinds(retry.instance_id) == [
        AgentActivityKind.DISPATCHED,
        AgentActivityKind.COMPLETED,
    ]


async def test_a_declined_restart_writes_no_restart_planned_activity() -> None:
    """The Supervisor was asked and returned an empty plan."""
    repository = _RecordingRepository()
    node = _node()
    handle = _handle(task_node_id=node.id, correlation_id=uuid4(), status="failure")

    instance_id, _c, supervisor = await _dispatch(
        repository=repository, handles=[handle], node=node, restart_instance_ids=[]
    )

    assert supervisor.calls, "the Supervisor was consulted; it declined"
    assert instance_id is not None
    assert await repository.kinds(instance_id) == [
        AgentActivityKind.DISPATCHED,
        AgentActivityKind.FAILED,
    ]
    assert AgentActivityKind.RESTART_PLANNED not in repository.standalone


async def test_a_restart_plan_for_a_different_instance_writes_nothing() -> None:
    """`restart_ids` is checked for *this* instance, not merely for being
    non-empty."""
    repository = _RecordingRepository()
    node = _node()

    instance_id, _c, _s = await _dispatch(
        repository=repository,
        handles=[_handle(task_node_id=node.id, correlation_id=uuid4(), status="failure")],
        node=node,
        restart_instance_ids=[uuid4()],
    )

    assert instance_id is not None
    assert AgentActivityKind.RESTART_PLANNED not in await repository.kinds(instance_id)


# --- 6/7/8. peer_review ---------------------------------------------------


@pytest.mark.parametrize(
    ("verdict", "reviewer_replies", "reviewer_available"),
    [
        ("approved", [None], False),
        ("rejected", [None], False),
        ("timed_out", [None], False),
        ("not_required", [None], False),
    ],
)
async def test_every_peer_review_verdict_is_recorded(
    verdict: Literal["approved", "rejected", "timed_out", "not_required"],
    reviewer_replies: list[AgentMessage | None],
    reviewer_available: bool,
) -> None:
    """All four verdicts produce a row -- `not_required` and `timed_out`
    included. Suppressing them would hide "nobody reviewed this" behind a
    task that still finalized successfully."""
    repository = _RecordingRepository()
    node = _node(assigned_agent_category="coding")

    instance_id, _c, supervisor = await _dispatch(
        repository=repository,
        handles=[_handle(task_node_id=node.id, correlation_id=uuid4(), review=True)],
        node=node,
        package=_reviewable_package(),
        peer_validation=verdict,
        review_replies=reviewer_replies,
    )

    assert supervisor.peer_review_calls, "a real round ran"
    assert instance_id is not None
    kinds = await repository.kinds(instance_id)
    assert kinds.count(AgentActivityKind.PEER_REVIEW) == 1
    review = next(
        a
        for a in await repository.activities(instance_id)
        if a.kind is AgentActivityKind.PEER_REVIEW
    )
    assert review.detail == {
        "reviewer_category": "architect",
        "peer_validation": verdict,
        "reviewer_available": reviewer_available,
    }


async def test_a_round_with_a_real_reviewer_records_reviewer_available() -> None:
    repository = _RecordingRepository()
    node = _node(assigned_agent_category="coding")
    correlation_id = uuid4()

    instance_id, _c, _s = await _dispatch(
        repository=repository,
        handles=[_handle(task_node_id=node.id, correlation_id=correlation_id, review=True)],
        node=node,
        package=_reviewable_package(),
        peer_validation="approved",
        review_replies=[_review_reply(status="success", correlation_id=correlation_id)],
        correlation_id=correlation_id,
    )

    assert instance_id is not None
    review = next(
        a
        for a in await repository.activities(instance_id)
        if a.kind is AgentActivityKind.PEER_REVIEW
    )
    assert review.detail["reviewer_available"] is True
    assert review.detail["peer_validation"] == "approved"


async def test_a_package_declaring_no_reviewer_produces_no_peer_review_activity() -> None:
    """`_run_peer_review` is never invoked, so nothing may be recorded."""
    repository = _RecordingRepository()
    node = _node()

    instance_id, _c, supervisor = await _dispatch(
        repository=repository,
        handles=[_handle(task_node_id=node.id, correlation_id=uuid4())],
        node=node,
        package=_package(),
    )

    assert supervisor.peer_review_calls == [], "no round ran"
    assert instance_id is not None
    assert AgentActivityKind.PEER_REVIEW not in await repository.kinds(instance_id)


async def test_a_failed_run_never_reaches_peer_review() -> None:
    """A non-success outcome skips the round entirely, even for a package
    that declares a reviewer."""
    repository = _RecordingRepository()
    node = _node(assigned_agent_category="coding")

    instance_id, _c, supervisor = await _dispatch(
        repository=repository,
        handles=[_handle(task_node_id=node.id, correlation_id=uuid4(), status="failure")],
        node=node,
        package=_reviewable_package(),
        restart_instance_ids=[],
    )

    assert supervisor.peer_review_calls == []
    assert instance_id is not None
    assert AgentActivityKind.PEER_REVIEW not in await repository.kinds(instance_id)


async def test_one_round_writes_one_row_not_one_per_call_site() -> None:
    """`_finalize_outcome` is reached from three call sites in
    `dispatch_task_node`; only the one that ran the round may write."""
    repository = _RecordingRepository()
    node = _node(assigned_agent_category="coding")

    instance_id, _c, _s = await _dispatch(
        repository=repository,
        handles=[_handle(task_node_id=node.id, correlation_id=uuid4(), review=True)],
        node=node,
        package=_reviewable_package(),
        peer_validation="approved",
        review_replies=[None],
    )

    assert instance_id is not None
    assert repository.standalone.count(AgentActivityKind.PEER_REVIEW) == 1
    assert len(repository.all_activity()) == 3  # dispatched, completed, peer_review


# --- 9/10/11. interrupted -------------------------------------------------


def _running(*, task_node_id: UUID | None) -> AgentInstance:
    from datetime import UTC, datetime

    return AgentInstance(
        id=uuid4(),
        agent_package_id=uuid4(),
        category="research",
        execution_backend="inprocess",
        status="running",
        assigned_task_node_id=task_node_id,
        started_at=datetime.now(UTC),
        health_status="unknown",
    )


async def test_reconciliation_writes_exactly_one_interrupted_activity() -> None:
    repository = _RecordingRepository()
    node_id = uuid4()
    orphan = _running(task_node_id=node_id)
    await repository.insert(orphan)
    publisher = FakeEventPublisher()

    reconciled = await reconcile_running_instances(repository, publisher)

    assert reconciled == [orphan.id]
    assert await repository.kinds(orphan.id) == [AgentActivityKind.INTERRUPTED]
    activity = (await repository.activities(orphan.id))[0]
    assert activity.detail == {"reason": "kernel_restart", "task_node_id": str(node_id)}


async def test_interrupted_reuses_the_published_events_correlation_id() -> None:
    """Decision B2: the row and the `agent_os.task.completed` it accompanies
    are joinable on one id -- not two independently minted ones."""
    repository = _RecordingRepository()
    orphan = _running(task_node_id=uuid4())
    await repository.insert(orphan)
    publisher = FakeEventPublisher()

    await reconcile_running_instances(repository, publisher)

    assert len(publisher.published) == 1
    published = publisher.published[0]
    activity = (await repository.activities(orphan.id))[0]
    assert activity.correlation_id is not None
    assert activity.correlation_id == published.correlation_id
    assert str(activity.correlation_id) == published.payload["correlation_id"]


async def test_interrupted_correlation_id_is_null_without_a_task_node() -> None:
    """No task node means no published event, so there is no correlation id
    to carry -- and none is minted to avoid a null."""
    repository = _RecordingRepository()
    orphan = _running(task_node_id=None)
    await repository.insert(orphan)
    publisher = FakeEventPublisher()

    await reconcile_running_instances(repository, publisher)

    assert publisher.published == []
    activity = (await repository.activities(orphan.id))[0]
    assert activity.kind is AgentActivityKind.INTERRUPTED
    assert activity.correlation_id is None
    assert activity.detail == {"reason": "kernel_restart"}


async def test_each_orphan_gets_its_own_row_and_its_own_correlation_id() -> None:
    repository = _RecordingRepository()
    first = _running(task_node_id=uuid4())
    second = _running(task_node_id=uuid4())
    await repository.insert(first)
    await repository.insert(second)
    publisher = FakeEventPublisher()

    await reconcile_running_instances(repository, publisher)

    first_activity = (await repository.activities(first.id))[0]
    second_activity = (await repository.activities(second.id))[0]
    assert first_activity.correlation_id != second_activity.correlation_id
    assert len(repository.all_activity()) == 2


async def test_reconciliation_still_marks_the_row_failed_and_publishes() -> None:
    """Existing behaviour, unchanged by the activity write."""
    repository = _RecordingRepository()
    orphan = _running(task_node_id=uuid4())
    await repository.insert(orphan)
    publisher = FakeEventPublisher()

    await reconcile_running_instances(repository, publisher)

    row = await repository.find_by_id(orphan.id)
    assert row is not None
    assert row.status == "failed"
    assert len(publisher.published) == 1
    assert publisher.published[0].subject == "agent_os.task.completed"
    assert publisher.published[0].payload["outcome"] == "interrupted"


# --- 12. correlation propagation on the scheduler paths -------------------


async def test_every_scheduler_activity_carries_the_inbound_correlation_id() -> None:
    """The id that arrived on `planning.task_graph.created`, unchanged, on
    all four scheduler-produced kinds."""
    repository = _RecordingRepository()
    node = _node(assigned_agent_category="coding")
    correlation_id = uuid4()
    first = _handle(task_node_id=node.id, correlation_id=correlation_id, status="failure")
    retry = _handle(task_node_id=node.id, correlation_id=correlation_id, review=True)

    await _dispatch(
        repository=repository,
        handles=[first, retry],
        node=node,
        package=_reviewable_package(),
        correlation_id=correlation_id,
        restart_instance_ids=[first.instance_id],
        peer_validation="approved",
        review_replies=[None],
    )

    produced = repository.all_activity()
    assert {a.kind for a in produced} == {
        AgentActivityKind.DISPATCHED,
        AgentActivityKind.FAILED,
        AgentActivityKind.RESTART_PLANNED,
        AgentActivityKind.COMPLETED,
        AgentActivityKind.PEER_REVIEW,
    }
    assert all(a.correlation_id == correlation_id for a in produced)


async def test_correlation_id_is_never_in_detail() -> None:
    repository = _RecordingRepository()
    node = _node()

    await _dispatch(
        repository=repository,
        handles=[_handle(task_node_id=node.id, correlation_id=uuid4())],
        node=node,
    )

    for activity in repository.all_activity():
        assert "correlation_id" not in activity.detail
        assert "agent_instance_id" not in activity.detail
        assert "kind" not in activity.detail
        assert "occurred_at" not in activity.detail


# --- 13/14. transaction boundary ------------------------------------------


async def test_dispatched_and_terminal_activity_ride_their_own_mutations() -> None:
    """The transactional half of 4C.2d: both kinds arrive **inside** the
    state mutation, never as a second `append_activity` call."""
    repository = _RecordingRepository()
    node = _node()

    await _dispatch(
        repository=repository,
        handles=[_handle(task_node_id=node.id, correlation_id=uuid4())],
        node=node,
    )

    assert repository.coupled == [
        ("insert", AgentActivityKind.DISPATCHED),
        ("update_status", AgentActivityKind.COMPLETED),
    ]
    assert repository.standalone == []


async def test_interrupted_rides_the_failed_transition() -> None:
    repository = _RecordingRepository()
    await repository.insert(_running(task_node_id=uuid4()))
    repository.coupled.clear()

    await reconcile_running_instances(repository, FakeEventPublisher())

    assert repository.coupled == [("update_status", AgentActivityKind.INTERRUPTED)]
    assert repository.standalone == []


async def test_restart_planned_and_peer_review_are_standalone_by_design() -> None:
    """Neither accompanies an `agent_instance` transition, so neither may
    invent one to ride on."""
    repository = _RecordingRepository()
    node = _node(assigned_agent_category="coding")
    first = _handle(task_node_id=node.id, correlation_id=uuid4(), status="failure")
    retry = _handle(task_node_id=node.id, correlation_id=uuid4(), review=True)

    mutations_before = len(repository.mutation_calls)
    await _dispatch(
        repository=repository,
        handles=[first, retry],
        node=node,
        package=_reviewable_package(),
        restart_instance_ids=[first.instance_id],
        peer_validation="approved",
        review_replies=[None],
    )

    assert repository.standalone == [
        AgentActivityKind.RESTART_PLANNED,
        AgentActivityKind.PEER_REVIEW,
    ]
    # Two instances x (insert + update_status). No extra mutation was
    # introduced to carry the standalone activities.
    assert len(repository.mutation_calls) - mutations_before == 4


@pytest.mark.parametrize(
    ("failing_kind", "handles_status"),
    [(AgentActivityKind.DISPATCHED, "success"), (AgentActivityKind.COMPLETED, "success")],
)
async def test_an_activity_write_failure_propagates_and_is_not_swallowed(
    failing_kind: AgentActivityKind, handles_status: str
) -> None:
    """Existing error semantics preserved: the exception leaves
    `dispatch_task_node` rather than being caught into a partial success.
    (`dispatch_ready_nodes`' `gather(return_exceptions=True)` is what decides
    what a failed node means -- unchanged by 4C.2d.)"""
    repository = _RecordingRepository(fail_activity_kind=failing_kind)
    node = _node()

    with pytest.raises(RuntimeError, match="activity persistence failed"):
        await _dispatch(
            repository=repository,
            handles=[
                _handle(task_node_id=node.id, correlation_id=uuid4(), status=handles_status)
            ],
            node=node,
        )


async def test_a_reconciliation_activity_failure_propagates() -> None:
    repository = _RecordingRepository(fail_activity_kind=AgentActivityKind.INTERRUPTED)
    await repository.insert(_running(task_node_id=uuid4()))
    publisher = FakeEventPublisher()

    with pytest.raises(RuntimeError, match="activity persistence failed"):
        await reconcile_running_instances(repository, publisher)

    assert publisher.published == [], (
        "the event must not be published when the transition it describes did not commit"
    )


# --- negative controls ----------------------------------------------------


async def test_no_activity_is_written_when_no_category_is_assigned() -> None:
    repository = _RecordingRepository()

    dispatched, _c, _s = await _dispatch(
        repository=repository, handles=[], node=_node(assigned_agent_category=None)
    )

    assert dispatched is None
    assert repository.all_activity() == []


async def test_no_activity_is_written_when_no_healthy_package_exists() -> None:
    repository = _RecordingRepository()
    node = _node()
    registry_port = FakeRegistryPort(package=None)

    dispatched = await dispatch_task_node(
        node,
        repository=repository,
        registry_port=registry_port,
        supervisor_port=FakeSupervisorPort(),
        execution_backend=FakeAgentExecutionBackend(handles=[]),
        event_publisher=FakeEventPublisher(),
        primary_user_id=uuid4(),
        correlation_id=uuid4(),
    )

    assert dispatched is None
    assert repository.all_activity() == []


async def test_reads_write_no_activity() -> None:
    """The read surface 4C.2c exposes must never manufacture history."""
    repository = _RecordingRepository()
    node = _node()
    instance_id, _c, _s = await _dispatch(
        repository=repository,
        handles=[_handle(task_node_id=node.id, correlation_id=uuid4())],
        node=node,
    )
    assert instance_id is not None
    before = len(repository.all_activity())

    await repository.find_by_id(instance_id)
    await repository.find_by_id(uuid4())
    await repository.list_instances(limit=10)
    await repository.list_by_status("completed")
    await repository.list_activity(instance_id, limit=10)

    assert len(repository.all_activity()) == before


async def test_reconciliation_of_an_empty_runtime_writes_nothing() -> None:
    """No orphans means no interruption happened."""
    repository = _RecordingRepository()
    publisher = FakeEventPublisher()

    assert await reconcile_running_instances(repository, publisher) == []
    assert repository.all_activity() == []
    assert publisher.published == []


async def test_the_activity_surface_stays_append_only() -> None:
    """A mutation method added to the repository would let a lifecycle path
    rewrite history; 4C.2d must not have introduced one."""
    for forbidden in ("update_activity", "delete_activity", "remove_activity"):
        assert not hasattr(_RecordingRepository(), forbidden)
