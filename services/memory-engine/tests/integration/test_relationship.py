"""`domain/relationship.py` -- the thin client into Knowledge Engine, exercised
against `FakeEventPublisher` since Knowledge Engine doesn't exist yet (docs/design/
phase-1/04-cross-engine-integration.md)."""

from uuid import uuid4

from nova_contracts import KnowledgeLinkReplyPayload, KnowledgeTraverseReplyPayload
from nova_memory_engine.domain import relationship

from tests.fakes.event_publisher import FakeEventPublisher


async def test_link_returns_knowledge_node_id_when_served() -> None:
    publisher = FakeEventPublisher()
    publisher.register(
        "knowledge.link.request",
        lambda _payload: KnowledgeLinkReplyPayload(knowledge_node_id="concept-python"),
    )

    node_id = await relationship.link(
        publisher, memory_id=uuid4(), concept_name="Python", correlation_id=uuid4()
    )

    assert node_id == "concept-python"


async def test_link_returns_none_when_knowledge_engine_unavailable() -> None:
    publisher = FakeEventPublisher()  # nothing registered -- times out

    node_id = await relationship.link(
        publisher, memory_id=uuid4(), concept_name="Python", correlation_id=uuid4()
    )

    assert node_id is None


async def test_traverse_returns_connected_nodes_when_served() -> None:
    publisher = FakeEventPublisher()
    publisher.register(
        "knowledge.traverse.request",
        lambda _payload: KnowledgeTraverseReplyPayload(
            connected_node_ids=["concept-rust", "concept-systems-programming"]
        ),
    )

    connected = await relationship.traverse(
        publisher, seed_node_id="concept-python", correlation_id=uuid4()
    )

    assert connected == ["concept-rust", "concept-systems-programming"]


async def test_traverse_returns_empty_list_when_knowledge_engine_unavailable() -> None:
    publisher = FakeEventPublisher()

    connected = await relationship.traverse(
        publisher, seed_node_id="concept-python", correlation_id=uuid4()
    )

    assert connected == []


async def test_link_request_carries_correct_payload() -> None:
    publisher = FakeEventPublisher()
    publisher.register(
        "knowledge.link.request", lambda _payload: KnowledgeLinkReplyPayload(knowledge_node_id="x")
    )
    memory_id = uuid4()

    await relationship.link(
        publisher, memory_id=memory_id, concept_name="Rust", correlation_id=uuid4()
    )

    [(subject, payload)] = publisher.calls
    assert subject == "knowledge.link.request"
    assert payload.memory_id == memory_id  # type: ignore[attr-defined]
    assert payload.concept_name == "Rust"  # type: ignore[attr-defined]
