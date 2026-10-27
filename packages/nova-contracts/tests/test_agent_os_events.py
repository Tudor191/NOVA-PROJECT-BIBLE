from uuid import uuid4

from nova_contracts import (
    AgentMessage,
    AgentMessageType,
    AgentOsListPackagesReplyPayload,
    AgentOsListPackagesRequestPayload,
    AgentOsTaskCompletedPayload,
    AgentPackageSnapshot,
    known_subjects,
)


def test_agent_message_type_matches_doc_12_10_verbatim() -> None:
    assert [member.value for member in AgentMessageType] == [
        "assign",
        "pause",
        "resume",
        "peer_review_request",
        "peer_review_result",
        "conflict_escalation",
        "delegation",
        "health_ping",
    ]


def test_agent_message_round_trips() -> None:
    message = AgentMessage(
        message_type=AgentMessageType.PEER_REVIEW_REQUEST,
        from_instance_id=uuid4(),
        to_instance_id=uuid4(),
        payload={"task_node_id": str(uuid4())},
        correlation_id=uuid4(),
    )
    round_tripped = AgentMessage.model_validate(message.model_dump(mode="json"))
    assert round_tripped == message
    assert round_tripped.schema_version == 1


def test_agent_message_from_instance_id_defaults_to_none_for_kernel_originated() -> None:
    message = AgentMessage(
        message_type=AgentMessageType.ASSIGN,
        to_instance_id=uuid4(),
        payload={},
        correlation_id=uuid4(),
    )
    assert message.from_instance_id is None


def test_agent_message_subject_is_registered() -> None:
    assert "agent_os.instance.inbox" in known_subjects()


def test_agent_os_task_completed_subject_is_registered() -> None:
    assert "agent_os.task.completed" in known_subjects()


def test_agent_os_task_completed_round_trips() -> None:
    payload = AgentOsTaskCompletedPayload(
        task_node_id=uuid4(),
        agent_instance_id=uuid4(),
        outcome="success",
        result={"summary": "done"},
        correlation_id=uuid4(),
    )
    round_tripped = AgentOsTaskCompletedPayload.model_validate(payload.model_dump(mode="json"))
    assert round_tripped == payload
    assert round_tripped.schema_version == 1


def test_agent_os_task_completed_interrupted_outcome_has_no_result() -> None:
    payload = AgentOsTaskCompletedPayload(
        task_node_id=uuid4(),
        agent_instance_id=uuid4(),
        outcome="interrupted",
        correlation_id=uuid4(),
    )
    assert payload.result is None


# --- agent_os.registry.list_packages, Phase 4C milestone 4C.2a ---------------


def _snapshot(**overrides: object) -> AgentPackageSnapshot:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "category": "coding",
        "version": "1.2.0",
        "manifest_json": {"id": "coding-agent", "version": "1.2.0"},
        "health_status": "healthy",
    }
    defaults.update(overrides)
    return AgentPackageSnapshot(**defaults)  # type: ignore[arg-type]


def test_list_packages_subjects_are_registered() -> None:
    assert "agent_os.registry.list_packages.request" in known_subjects()
    assert "agent_os.registry.list_packages.reply" in known_subjects()


def test_list_packages_request_round_trips() -> None:
    payload = AgentOsListPackagesRequestPayload(
        requesting_engine="kernel", correlation_id=uuid4()
    )
    round_tripped = AgentOsListPackagesRequestPayload.model_validate(
        payload.model_dump(mode="json")
    )
    assert round_tripped == payload
    assert round_tripped.schema_version == 1


def test_list_packages_reply_round_trips_with_every_snapshot_field() -> None:
    payload = AgentOsListPackagesReplyPayload(packages=[_snapshot(), _snapshot(category="qa")])
    round_tripped = AgentOsListPackagesReplyPayload.model_validate(
        payload.model_dump(mode="json")
    )
    assert round_tripped == payload
    assert round_tripped.schema_version == 1
    assert [package.category for package in round_tripped.packages] == ["coding", "qa"]


def test_list_packages_reply_defaults_to_an_empty_list() -> None:
    """`packages=[]` is a real answer -- "Registry is healthy and holds
    nothing" -- and must be constructible without ceremony. It is never how
    an unreachable Registry is reported: that raises at the caller
    (`RegistryClient`), which is what keeps decision D-1's 200-vs-503
    distinction representable."""
    assert AgentOsListPackagesReplyPayload().packages == []


def test_list_packages_reply_reuses_the_dispatch_rpc_snapshot_type() -> None:
    """One wire shape for one entity.

    If this ever fails, a second `agent_package` representation has appeared
    and the two can drift -- the exact problem `AgentPackageSnapshot` exists
    to prevent."""
    reply = AgentOsListPackagesReplyPayload(packages=[_snapshot()])
    assert isinstance(reply.packages[0], AgentPackageSnapshot)
