from uuid import uuid4

from nova_contracts import (
    AgentMessage,
    AgentMessageType,
    AgentOsTaskCompletedPayload,
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
