from nova_knowledge_engine.domain.discovery import discover_related_to
from nova_knowledge_engine.domain.models import KnowledgeNode


def _node(node_id: str, *, embedding: list[float] | None) -> KnowledgeNode:
    return KnowledgeNode(node_id=node_id, label="Concept", name=node_id, embedding=embedding)


def test_no_relationships_without_embedding() -> None:
    candidate = _node("a", embedding=None)
    others = [_node("b", embedding=[1.0, 0.0])]
    assert discover_related_to(candidate, others) == []


def test_discovers_related_pair_above_threshold() -> None:
    candidate = _node("a", embedding=[1.0, 0.0])
    others = [_node("b", embedding=[0.99, 0.01]), _node("c", embedding=[0.0, 1.0])]
    discovered = discover_related_to(candidate, others, threshold=0.9)
    assert len(discovered) == 1
    assert discovered[0].from_id == "a"
    assert discovered[0].to_id == "b"
    assert discovered[0].relationship_type == "RELATED_TO"


def test_already_connected_pairs_are_skipped() -> None:
    candidate = _node("a", embedding=[1.0, 0.0])
    others = [_node("b", embedding=[0.99, 0.01])]
    discovered = discover_related_to(candidate, others, already_connected=frozenset({"b"}))
    assert discovered == []


def test_self_is_never_proposed() -> None:
    candidate = _node("a", embedding=[1.0, 0.0])
    discovered = discover_related_to(candidate, [candidate])
    assert discovered == []
