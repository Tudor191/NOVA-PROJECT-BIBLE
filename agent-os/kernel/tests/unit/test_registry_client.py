"""`RegistryClient.list_packages()` -- Phase 4C milestone 4C.2a.

The subject of this file is **decision D-1's failure semantics**, established
at the layer where they originate. `GET /v1/agents` (4C.2c) must answer
`200 []` for a healthy Registry holding nothing and `503` for a Registry it
cannot reach. Both of those depend on one property of this client:

    an empty reply returns [];  a failed call raises.

A client that caught its own timeout and returned `[]` would erase the
difference before any layer above it could act on it, and
`api-gateway`'s own `domain/envelope.py` states the rule it would break --
"a degraded upstream must never look like an empty success."

The RPC's own wire behaviour is covered against a real bus in
`agent-os/registry`'s `test_events_list_packages_request.py`. What is left
here is the caller's contract, which is exercised against a fake publisher
because the property under test is *what the client does with what it gets
back*, and that is independent of any broker.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from nova_agent_os_kernel.clients.registry_client import RegistryClient
from nova_contracts import (
    AgentOsListPackagesReplyPayload,
    AgentPackageSnapshot,
    EventEnvelope,
)
from pydantic import BaseModel

_SUBJECT = "agent_os.registry.list_packages.request"


def _snapshot(category: str = "coding", version: str = "1.2.0") -> AgentPackageSnapshot:
    return AgentPackageSnapshot(
        id=uuid4(),
        category=category,
        version=version,
        manifest_json={"id": f"{category}-agent", "version": version},
        health_status="healthy",
    )


class _ReplyingPublisher:
    """Answers `request()` with a fixed reply payload and records the call."""

    def __init__(self, reply: BaseModel) -> None:
        self._reply = reply
        self.calls: list[tuple[str, BaseModel, str, UUID | None, int]] = []

    async def publish(self, envelope: EventEnvelope) -> None:  # pragma: no cover
        raise AssertionError("list_packages must not publish an event")

    async def request(
        self,
        subject: str,
        payload: BaseModel,
        *,
        source_engine: str,
        correlation_id: UUID | None = None,
        timeout_ms: int = 2000,
    ) -> EventEnvelope:
        self.calls.append((subject, payload, source_engine, correlation_id, timeout_ms))
        return EventEnvelope(
            subject=subject,
            source_engine="registry",
            correlation_id=correlation_id or uuid4(),
            payload=self._reply.model_dump(mode="json"),
        )


class _FailingPublisher:
    def __init__(self, error: BaseException) -> None:
        self._error = error

    async def publish(self, envelope: EventEnvelope) -> None:  # pragma: no cover
        raise AssertionError("list_packages must not publish an event")

    async def request(self, *args: object, **kwargs: object) -> EventEnvelope:
        raise self._error


async def test_returns_the_packages_the_reply_carried_in_order() -> None:
    reply = AgentOsListPackagesReplyPayload(
        packages=[_snapshot("architect", "0.1.0"), _snapshot("coding", "1.2.0")]
    )
    client = RegistryClient(_ReplyingPublisher(reply))

    packages = await client.list_packages()

    assert [(p.category, p.version) for p in packages] == [
        ("architect", "0.1.0"),
        ("coding", "1.2.0"),
    ]


async def test_does_not_re_sort_the_reply() -> None:
    """Ordering is the repository's guarantee. A second sort here would be a
    second place for it to drift, and would silently mask a repository that
    stopped ordering at all."""
    reply = AgentOsListPackagesReplyPayload(
        packages=[_snapshot("zeta", "9.9.9"), _snapshot("alpha", "0.0.1")]
    )
    client = RegistryClient(_ReplyingPublisher(reply))

    packages = await client.list_packages()

    assert [p.category for p in packages] == ["zeta", "alpha"]


async def test_an_empty_reply_is_a_successful_empty_list() -> None:
    """D-1's `200 []` case: healthy Registry, nothing installed."""
    client = RegistryClient(_ReplyingPublisher(AgentOsListPackagesReplyPayload()))

    assert await client.list_packages() == []


@pytest.mark.parametrize(
    "error",
    [TimeoutError("registry did not answer"), RuntimeError("broker refused")],
    ids=["timeout", "broker-error"],
)
async def test_a_failed_call_raises_rather_than_returning_an_empty_list(
    error: BaseException,
) -> None:
    """D-1's `503` case, and the single most important assertion in this file.

    If this ever returns `[]`, `GET /v1/agents` becomes incapable of telling
    an operator the difference between "no agents are installed" and "the
    Registry is down" -- and would report the first while the second is true.
    """
    client = RegistryClient(_FailingPublisher(error))

    with pytest.raises(type(error)):
        await client.list_packages()


async def test_calls_the_listing_subject_with_the_kernel_as_requester() -> None:
    publisher = _ReplyingPublisher(AgentOsListPackagesReplyPayload())
    client = RegistryClient(publisher)
    correlation_id = uuid4()

    await client.list_packages(correlation_id=correlation_id)

    subject, payload, source_engine, sent_correlation_id, timeout_ms = publisher.calls[0]
    assert subject == _SUBJECT
    assert source_engine == "kernel"
    assert sent_correlation_id == correlation_id
    assert payload.requesting_engine == "kernel"  # type: ignore[attr-defined]
    assert payload.correlation_id == correlation_id  # type: ignore[attr-defined]
    # The existing client-wide timeout, not a new one invented for this call.
    assert timeout_ms == 2000


async def test_mints_a_correlation_id_when_the_caller_supplies_none() -> None:
    publisher = _ReplyingPublisher(AgentOsListPackagesReplyPayload())
    client = RegistryClient(publisher)

    await client.list_packages()

    _subject, payload, _source, correlation_id, _timeout = publisher.calls[0]
    assert isinstance(correlation_id, UUID)
    assert payload.correlation_id == correlation_id  # type: ignore[attr-defined]


async def test_find_healthy_package_is_unchanged_by_the_addition() -> None:
    """Regression: 4C.2a adds a method to this client. The existing one must
    still call its own subject with its own payload shape."""
    from nova_contracts import AgentOsFindHealthyPackageReplyPayload

    publisher = _ReplyingPublisher(
        AgentOsFindHealthyPackageReplyPayload(package=_snapshot("coding", "1.1.0"))
    )
    client = RegistryClient(publisher)

    package = await client.find_healthy_package(category="coding")

    subject, payload, source_engine, _cid, _timeout = publisher.calls[0]
    assert subject == "agent_os.registry.find_healthy_package.request"
    assert source_engine == "kernel"
    assert payload.category == "coding"  # type: ignore[attr-defined]
    assert package is not None
    assert package.version == "1.1.0"
