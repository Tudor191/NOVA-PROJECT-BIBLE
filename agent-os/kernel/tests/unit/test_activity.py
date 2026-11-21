"""`domain/activity.py` and the append-only repository contract -- Phase 4C
milestone 4C.2b.

Split by what each part can be tested against: the kind vocabulary, the
cursor codec and the page shape are pure and are tested directly; the
ordering and paging *behaviour* is tested through the in-memory repository
here and again against real Postgres in
`tests/integration/test_repository_real_postgres.py`, because a fake agreeing
with a Python `sorted()` proves nothing about an `ORDER BY`.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from nova_agent_os_kernel.domain.activity import (
    ActivityPage,
    AgentActivity,
    AgentActivityKind,
    InvalidCursorError,
    decode_cursor,
    encode_cursor,
    new_activity,
)
from nova_agent_os_kernel.domain.models import AgentInstance
from nova_agent_os_kernel.domain.ports import KernelRepository
from pydantic import ValidationError

from tests.fakes.repository import FakeForeignKeyViolation, FakeKernelRepository

_BASE = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)


def _instance(**overrides: object) -> AgentInstance:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "agent_package_id": uuid4(),
        "category": "coding",
        "execution_backend": "inprocess",
        "status": "running",
        "started_at": _BASE,
        "health_status": "unknown",
    }
    defaults.update(overrides)
    return AgentInstance(**defaults)  # type: ignore[arg-type]


def _activity(instance_id: UUID, **overrides: object) -> AgentActivity:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "agent_instance_id": instance_id,
        "occurred_at": _BASE,
        "kind": AgentActivityKind.DISPATCHED,
        "detail": {},
    }
    defaults.update(overrides)
    return AgentActivity(**defaults)  # type: ignore[arg-type]


async def _repo_with_instance() -> tuple[FakeKernelRepository, AgentInstance]:
    repository = FakeKernelRepository()
    instance = _instance()
    await repository.insert(instance)
    return repository, instance


# --- the closed kind vocabulary ---------------------------------------------


def test_the_kind_vocabulary_is_exactly_the_six_approved_values() -> None:
    """Closed, and closed at this exact set. A seventh member added without a
    code path that produces it -- or a migration altering the table's CHECK --
    fails here first."""
    assert [kind.value for kind in AgentActivityKind] == [
        "dispatched",
        "completed",
        "failed",
        "restart_planned",
        "interrupted",
        "peer_review",
    ]


@pytest.mark.parametrize("kind", list(AgentActivityKind), ids=lambda k: k.value)
def test_every_allowed_kind_is_accepted(kind: AgentActivityKind) -> None:
    activity = _activity(uuid4(), kind=kind)
    assert activity.kind is kind
    assert AgentActivity.model_validate(activity.model_dump(mode="json")).kind is kind


@pytest.mark.parametrize(
    "invalid",
    ["", "dispatch", "DISPATCHED", "peer-review", "unknown", "started", None, 1],
    ids=repr,
)
def test_an_invalid_kind_is_rejected(invalid: object) -> None:
    with pytest.raises(ValidationError):
        _activity(uuid4(), kind=invalid)


def test_the_migration_check_constraint_lists_exactly_the_domain_kinds() -> None:
    """The migration spells the vocabulary out rather than importing the enum,
    so that an applied migration never changes retroactively when the enum
    gains a member. This is what keeps the two copies honest: a seventh kind
    added to the enum without a migration altering the CHECK fails here.

    Parsed with `ast` rather than matched textually, so reformatting the
    migration cannot break the test and a commented-out entry cannot satisfy
    it.
    """
    import ast
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "0002_agent_activity.py"
    )
    tree = ast.parse(migration.read_text())
    declared: list[str] | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_KINDS" for t in node.targets
        ):
            declared = [ast.literal_eval(element) for element in node.value.elts]  # type: ignore[attr-defined]
    assert declared is not None, "the migration declares no _KINDS tuple"
    assert declared == [kind.value for kind in AgentActivityKind]


# --- new_activity stamps Python time ----------------------------------------


def test_new_activity_stamps_an_aware_utc_timestamp_and_a_fresh_id() -> None:
    before = datetime.now(UTC)
    activity = new_activity(agent_instance_id=uuid4(), kind=AgentActivityKind.COMPLETED)
    after = datetime.now(UTC)

    assert activity.occurred_at.tzinfo is not None
    assert activity.occurred_at.utcoffset() == timedelta(0)
    assert before <= activity.occurred_at <= after
    assert isinstance(activity.id, UUID)
    assert activity.detail == {}


# --- correlation_id: first-class, nullable, never fabricated ----------------


def test_correlation_id_defaults_to_none_and_is_never_generated() -> None:
    """`None` truthfully means "no correlation is known". Minting one here
    would manufacture provenance that links nothing, and no reader could tell
    the difference between real and invented lineage."""
    minted = new_activity(agent_instance_id=uuid4(), kind=AgentActivityKind.FAILED)
    assert minted.correlation_id is None
    assert _activity(uuid4()).correlation_id is None


def test_correlation_id_is_carried_when_supplied() -> None:
    correlation_id = uuid4()
    activity = new_activity(
        agent_instance_id=uuid4(),
        kind=AgentActivityKind.PEER_REVIEW,
        correlation_id=correlation_id,
    )
    assert activity.correlation_id == correlation_id


def test_correlation_id_round_trips_and_is_typed() -> None:
    """Typed rather than a key in `detail`: a string that is not a UUID is
    rejected, which is exactly the enforcement JSON could not give."""
    correlation_id = uuid4()
    activity = _activity(uuid4(), correlation_id=correlation_id)
    restored = AgentActivity.model_validate(activity.model_dump(mode="json"))
    assert restored.correlation_id == correlation_id

    with pytest.raises(ValidationError):
        _activity(uuid4(), correlation_id="not-a-uuid")


def test_correlation_id_is_not_inside_detail() -> None:
    """A guard against the change this correction exists to prevent: moving
    provenance back into the JSON blob, where it is unqueryable and untyped."""
    activity = _activity(uuid4(), correlation_id=uuid4())
    assert "correlation_id" not in activity.detail


def test_the_orm_column_is_nullable_with_no_default() -> None:
    from nova_agent_os_kernel.repository.models import AgentActivityORM

    column = AgentActivityORM.__table__.c.correlation_id
    assert column.nullable is True
    assert column.default is None
    assert column.server_default is None


def test_new_activity_gives_each_call_a_distinct_id() -> None:
    instance_id = uuid4()
    ids = {
        new_activity(agent_instance_id=instance_id, kind=AgentActivityKind.FAILED).id
        for _ in range(100)
    }
    assert len(ids) == 100


def test_the_orm_model_declares_no_database_default_for_occurred_at() -> None:
    """Postgres `now()` is transaction-start time, so a server default would
    give every row written in one transaction the same timestamp -- the exact
    tie the ordering key exists to break."""
    from nova_agent_os_kernel.repository.models import AgentActivityORM

    column = AgentActivityORM.__table__.c.occurred_at
    assert column.server_default is None
    assert column.default is None


# --- cursor codec ------------------------------------------------------------


def test_cursor_round_trips_the_ordering_key() -> None:
    activity_id = uuid4()
    assert decode_cursor(encode_cursor(_BASE, activity_id)) == (_BASE, activity_id)


def test_cursor_encoding_is_deterministic() -> None:
    """The same key must always produce the same string, or paging is not
    reproducible and every ordering assertion becomes flaky."""
    activity_id = uuid4()
    assert encode_cursor(_BASE, activity_id) == encode_cursor(_BASE, activity_id)


def test_cursor_round_trips_microsecond_precision() -> None:
    precise = _BASE.replace(microsecond=123456)
    activity_id = uuid4()
    assert decode_cursor(encode_cursor(precise, activity_id)) == (precise, activity_id)


def test_cursor_is_url_safe_and_unpadded() -> None:
    """It travels as a query parameter in 4C.2c, so it must need no escaping."""
    cursor = encode_cursor(_BASE.replace(microsecond=999999), uuid4())
    assert "=" not in cursor
    assert "+" not in cursor
    assert "/" not in cursor


def test_cursor_is_opaque_rather_than_the_raw_key() -> None:
    activity_id = uuid4()
    cursor = encode_cursor(_BASE, activity_id)
    assert str(activity_id) not in cursor
    assert _BASE.isoformat() not in cursor


def test_a_non_utc_cursor_decodes_to_the_same_instant_in_utc() -> None:
    from datetime import timezone

    other = _BASE.astimezone(timezone(timedelta(hours=2)))
    activity_id = uuid4()
    decoded_at, decoded_id = decode_cursor(encode_cursor(other, activity_id))
    assert decoded_at == _BASE
    assert decoded_at.utcoffset() == timedelta(0)
    assert decoded_id == activity_id


@pytest.mark.parametrize(
    ("cursor", "reason"),
    [
        ("", "empty"),
        ("!!!not-base64!!!", "not base64"),
        ("bm8tc2VwYXJhdG9y", "no separator"),  # "no-separator"
        ("bm90LWEtZGF0ZXwzOGE4M2M4Ni0wMDAwLTAwMDAtMDAwMC0wMDAwMDAwMDAwMDA", "bad datetime"),
        ("MjAyNi0wOS0wOFQxMjowMDowMCswMDowMHxub3QtYS11dWlk", "bad uuid"),
        ("MjAyNi0wOS0wOFQxMjowMDowMHwzOGE4M2M4Ni0wMDAwLTAwMDAtMDAwMC0wMDAwMDAwMDAwMDA", "naive"),
    ],
)
def test_an_invalid_cursor_is_rejected(cursor: str, reason: str) -> None:
    """Rejected, never silently treated as "start from the beginning" -- a
    caller who asked for a specific page would otherwise be handed rows they
    have already seen, and told it succeeded."""
    with pytest.raises(InvalidCursorError):
        decode_cursor(cursor)


def test_the_invalid_cursor_cases_are_genuinely_invalid_for_distinct_reasons() -> None:
    """A control for the table above: if one of those strings were malformed
    in an unintended way, it would still raise and the case it was meant to
    cover would go untested. This decodes each to show what it really is."""
    import base64

    def raw(value: str) -> str:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode()

    naive_case = "MjAyNi0wOS0wOFQxMjowMDowMHwzOGE4M2M4Ni0wMDAwLTAwMDAtMDAwMC0wMDAwMDAwMDAwMDA"
    assert raw("bm8tc2VwYXJhdG9y") == "no-separator"
    assert raw(naive_case).startswith("2026-09-08T12:00:00|"), (
        "the 'naive' case must be a valid datetime that merely lacks an offset, "
        "or it would be rejected for the wrong reason"
    )


# --- ActivityPage ------------------------------------------------------------


def test_an_empty_page_has_no_cursor() -> None:
    page = ActivityPage()
    assert page.items == []
    assert page.next_cursor is None


# --- append-only surface -----------------------------------------------------


def test_the_repository_port_exposes_no_activity_mutation() -> None:
    """The append-only guarantee, asserted against the port rather than
    described in a docstring. `append_activity` and `list_activity` are the
    whole activity surface; a method to update or delete one must not appear.
    """
    activity_methods = {
        name
        for name in dir(KernelRepository)
        if not name.startswith("_") and "activity" in name.lower()
    }
    assert activity_methods == {"append_activity", "list_activity"}

    forbidden = {"update_activity", "delete_activity", "remove_activity", "purge_activity"}
    assert not forbidden & set(dir(KernelRepository))


def test_the_postgres_repository_issues_no_activity_update_or_delete() -> None:
    """A source-level control on the implementation, not just the Protocol.

    The port could stay clean while the class grew a mutation method, or an
    existing method started issuing `UPDATE agent_activity`. Both would show
    up here.
    """
    from nova_agent_os_kernel.repository import postgres_kernel_repository

    source = inspect.getsource(postgres_kernel_repository)
    assert "AgentActivityORM" in source, "the parser is looking at the wrong module"
    for forbidden in ("delete(AgentActivityORM", "update(AgentActivityORM"):
        assert forbidden not in source, f"{forbidden!r} mutates an append-only table"


def test_the_postgres_repository_does_not_use_offset_pagination() -> None:
    """Keyset only. `.offset(` walks rows the database has already discarded
    and shifts under concurrent inserts -- on an append-only table that grows
    at the head, it would silently repeat rows between pages.
    """
    from nova_agent_os_kernel.repository import postgres_kernel_repository

    source = inspect.getsource(postgres_kernel_repository)
    assert ".offset(" not in source
    assert "tuple_(" in source, "the keyset predicate is gone"


# --- ordering and paging, through the fake ----------------------------------


async def test_activity_lists_newest_first() -> None:
    repository, instance = await _repo_with_instance()
    for minutes in (0, 5, 10):
        await repository.append_activity(
            _activity(instance.id, occurred_at=_BASE + timedelta(minutes=minutes))
        )

    page = await repository.list_activity(instance.id)

    assert [a.occurred_at for a in page.items] == [
        _BASE + timedelta(minutes=10),
        _BASE + timedelta(minutes=5),
        _BASE,
    ]


async def test_identical_timestamps_are_ordered_by_id_descending() -> None:
    """The tie the composite key exists for. Every row shares `occurred_at`,
    exactly as they would if written in one transaction against a
    `server_default` timestamp."""
    repository, instance = await _repo_with_instance()
    ids = sorted(uuid4() for _ in range(5))
    for activity_id in ids:
        await repository.append_activity(_activity(instance.id, id=activity_id))

    page = await repository.list_activity(instance.id)

    assert [a.id for a in page.items] == list(reversed(ids))


async def test_paging_walks_every_row_exactly_once_across_a_tie() -> None:
    """The property that actually matters: no row skipped, none repeated,
    with every timestamp identical so the tie-break is doing all the work."""
    repository, instance = await _repo_with_instance()
    ids = {uuid4() for _ in range(7)}
    for activity_id in ids:
        await repository.append_activity(_activity(instance.id, id=activity_id))

    seen: list[UUID] = []
    cursor: str | None = None
    for _ in range(10):  # bounded, so a broken cursor cannot loop forever
        page = await repository.list_activity(instance.id, limit=2, cursor=cursor)
        seen.extend(a.id for a in page.items)
        cursor = page.next_cursor
        if cursor is None:
            break

    assert cursor is None, "paging did not terminate"
    assert len(seen) == len(ids)
    assert set(seen) == ids
    assert len(set(seen)) == len(seen), "a row was returned on two pages"


async def test_the_last_page_has_no_next_cursor() -> None:
    repository, instance = await _repo_with_instance()
    await repository.append_activity(_activity(instance.id))

    page = await repository.list_activity(instance.id, limit=50)

    assert len(page.items) == 1
    assert page.next_cursor is None


async def test_a_full_page_with_no_further_rows_still_has_no_cursor() -> None:
    """`limit + 1` is fetched precisely so this case is distinguishable: a
    page that happens to be exactly full is not evidence of a next page."""
    repository, instance = await _repo_with_instance()
    for _ in range(3):
        await repository.append_activity(_activity(instance.id))

    page = await repository.list_activity(instance.id, limit=3)

    assert len(page.items) == 3
    assert page.next_cursor is None


async def test_an_instance_with_no_activity_returns_an_empty_page() -> None:
    repository, instance = await _repo_with_instance()

    page = await repository.list_activity(instance.id)

    assert page.items == []
    assert page.next_cursor is None


async def test_a_cursor_past_the_last_row_returns_an_empty_page() -> None:
    repository, instance = await _repo_with_instance()
    await repository.append_activity(_activity(instance.id))

    # Older than every row, so nothing sorts after it.
    beyond = encode_cursor(_BASE - timedelta(days=1), UUID(int=0))
    page = await repository.list_activity(instance.id, cursor=beyond)

    assert page.items == []
    assert page.next_cursor is None


async def test_an_invalid_cursor_raises_rather_than_restarting() -> None:
    repository, instance = await _repo_with_instance()
    await repository.append_activity(_activity(instance.id))

    with pytest.raises(InvalidCursorError):
        await repository.list_activity(instance.id, cursor="not-a-cursor!!")


async def test_ordering_ignores_correlation_id_entirely() -> None:
    """`correlation_id` is a join key, not an ordering key.

    Rows are written with correlation ids in the *opposite* order to their
    timestamps, so an implementation that sorted by provenance -- or used it
    as a tie-break -- would produce a visibly different sequence.
    """
    repository, instance = await _repo_with_instance()
    correlation_ids = sorted((uuid4() for _ in range(3)), reverse=True)
    for offset, correlation_id in enumerate(correlation_ids):
        await repository.append_activity(
            _activity(
                instance.id,
                occurred_at=_BASE + timedelta(minutes=offset),
                correlation_id=correlation_id,
            )
        )

    page = await repository.list_activity(instance.id)

    # Newest first, i.e. correlation ids ascending -- the reverse of their own
    # sort order, which is only possible if they play no part in ordering.
    assert [a.occurred_at for a in page.items] == [
        _BASE + timedelta(minutes=2),
        _BASE + timedelta(minutes=1),
        _BASE,
    ]
    assert [a.correlation_id for a in page.items] == list(reversed(correlation_ids))


async def test_a_null_correlation_id_does_not_disturb_ordering() -> None:
    """A mix of set and unset provenance must order purely by time. A NULL
    that sorted first or last would reveal the column leaking into ORDER BY."""
    repository, instance = await _repo_with_instance()
    await repository.append_activity(
        _activity(instance.id, occurred_at=_BASE, correlation_id=uuid4())
    )
    await repository.append_activity(
        _activity(instance.id, occurred_at=_BASE + timedelta(minutes=1), correlation_id=None)
    )
    await repository.append_activity(
        _activity(instance.id, occurred_at=_BASE + timedelta(minutes=2), correlation_id=uuid4())
    )

    page = await repository.list_activity(instance.id)

    assert [a.correlation_id is None for a in page.items] == [False, True, False]


def test_the_cursor_encodes_only_occurred_at_and_id() -> None:
    """The cursor is the ordering key. If `correlation_id` ever entered it,
    two rows with the same time and id but different provenance would page
    differently -- and an existing cursor would stop decoding."""
    correlation_id = uuid4()
    activity_id = uuid4()
    cursor = encode_cursor(_BASE, activity_id)

    assert str(correlation_id) not in cursor
    # And the codec's whole surface is the two-part key, nothing more.
    assert decode_cursor(cursor) == (_BASE, activity_id)
    assert len(inspect.signature(encode_cursor).parameters) == 2


async def test_paging_is_unaffected_by_correlation_id() -> None:
    """End-to-end: every row shares a timestamp so the tie-break does the
    work, and each carries a distinct correlation id that must not interfere.
    No row skipped, none repeated."""
    repository, instance = await _repo_with_instance()
    ids = {uuid4() for _ in range(6)}
    for activity_id in ids:
        await repository.append_activity(
            _activity(instance.id, id=activity_id, correlation_id=uuid4())
        )

    seen: list[UUID] = []
    cursor: str | None = None
    for _ in range(10):
        page = await repository.list_activity(instance.id, limit=2, cursor=cursor)
        seen.extend(a.id for a in page.items)
        cursor = page.next_cursor
        if cursor is None:
            break

    assert cursor is None
    assert set(seen) == ids
    assert len(set(seen)) == len(seen)


async def test_activity_is_scoped_to_its_own_instance() -> None:
    repository, instance = await _repo_with_instance()
    other = _instance()
    await repository.insert(other)
    await repository.append_activity(_activity(instance.id))
    await repository.append_activity(_activity(other.id))
    await repository.append_activity(_activity(other.id))

    assert len((await repository.list_activity(instance.id)).items) == 1
    assert len((await repository.list_activity(other.id)).items) == 2


# --- foreign key and transactional participation ----------------------------


async def test_activity_for_an_unknown_instance_is_refused() -> None:
    repository = FakeKernelRepository()

    with pytest.raises(FakeForeignKeyViolation):
        await repository.append_activity(_activity(uuid4()))


async def test_insert_writes_the_instance_and_its_activity_together() -> None:
    repository = FakeKernelRepository()
    instance = _instance()

    await repository.insert(
        instance, activity=_activity(instance.id, kind=AgentActivityKind.DISPATCHED)
    )

    assert await repository.find_by_id(instance.id) is not None
    page = await repository.list_activity(instance.id)
    assert [a.kind for a in page.items] == [AgentActivityKind.DISPATCHED]


async def test_update_status_writes_the_transition_and_its_activity_together() -> None:
    repository, instance = await _repo_with_instance()

    await repository.update_status(
        instance.id,
        status="completed",
        health_status="healthy",
        activity=_activity(instance.id, kind=AgentActivityKind.COMPLETED),
    )

    updated = await repository.find_by_id(instance.id)
    assert updated is not None
    assert updated.status == "completed"
    assert [a.kind for a in (await repository.list_activity(instance.id)).items] == [
        AgentActivityKind.COMPLETED
    ]


async def test_update_status_on_an_unknown_instance_writes_no_activity() -> None:
    """A no-op transition must not leave a record claiming a transition
    happened -- on an instance that does not even exist."""
    repository = FakeKernelRepository()
    unknown = uuid4()

    await repository.update_status(
        unknown, status="completed", activity=_activity(unknown, kind=AgentActivityKind.COMPLETED)
    )

    assert (await repository.list_activity(unknown)).items == []


# --- regression: agent_instance persistence is unchanged --------------------


async def test_insert_without_activity_behaves_exactly_as_before() -> None:
    repository = FakeKernelRepository()
    instance = _instance()

    returned = await repository.insert(instance)

    assert returned == instance
    assert await repository.find_by_id(instance.id) == instance
    assert (await repository.list_activity(instance.id)).items == []


async def test_update_status_without_activity_behaves_exactly_as_before() -> None:
    repository, instance = await _repo_with_instance()

    await repository.update_status(instance.id, status="failed", health_status="unhealthy")

    updated = await repository.find_by_id(instance.id)
    assert updated is not None
    assert updated.status == "failed"
    assert updated.health_status == "unhealthy"
    assert (await repository.list_activity(instance.id)).items == []


async def test_duplicate_instance_insert_still_raises() -> None:
    from nova_agent_os_kernel.domain.ports import AgentInstanceAlreadyExistsError

    repository, instance = await _repo_with_instance()

    with pytest.raises(AgentInstanceAlreadyExistsError):
        await repository.insert(instance)


async def test_list_by_status_is_unaffected_by_activity_rows() -> None:
    repository, instance = await _repo_with_instance()
    await repository.append_activity(_activity(instance.id))

    running = await repository.list_by_status("running")

    assert [row.id for row in running] == [instance.id]
