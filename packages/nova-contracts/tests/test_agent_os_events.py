from uuid import uuid4

from nova_contracts import AgentMessage, AgentMessageType, known_subjects


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
