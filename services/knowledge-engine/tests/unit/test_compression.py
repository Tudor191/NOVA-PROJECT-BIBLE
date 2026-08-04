from nova_knowledge_engine.domain.compression import find_duplicate_clusters
from nova_knowledge_engine.domain.models import KnowledgeNode, KnowledgeScope


def _node(
    node_id: str,
    *,
    embedding: list[float],
    scope: KnowledgeScope = KnowledgeScope.GLOBAL,
    label: str = "Concept",
    confidence: float = 0.5,
) -> KnowledgeNode:
    return KnowledgeNode(
        node_id=node_id,
        label=label,
        name=node_id,
        scope=scope,
        embedding=embedding,
        confidence=confidence,
    )


def test_near_duplicate_embeddings_cluster_together() -> None:
    nodes = [
        _node("a", embedding=[1.0, 0.0, 0.0], confidence=0.9),
        _node("b", embedding=[0.99, 0.01, 0.0], confidence=0.5),
        _node("c", embedding=[0.0, 1.0, 0.0], confidence=0.5),
    ]
    decisions = find_duplicate_clusters(nodes, threshold=0.9)
    assert len(decisions) == 1
    assert decisions[0].keep_id == "a"  # higher confidence anchor kept
    assert decisions[0].superseded_ids == ("b",)


def test_never_merges_across_scope() -> None:
    from uuid import uuid4

    project_id = uuid4()
    nodes = [
        _node("a", embedding=[1.0, 0.0], scope=KnowledgeScope.GLOBAL),
        _node("b", embedding=[1.0, 0.0], scope=KnowledgeScope.PROJECT),
    ]
    nodes[1] = nodes[1].model_copy(update={"project_id": project_id})
    decisions = find_duplicate_clusters(nodes, threshold=0.9)
    assert decisions == []


def test_never_merges_across_label() -> None:
    nodes = [
        _node("a", embedding=[1.0, 0.0], label="Concept"),
        _node("b", embedding=[1.0, 0.0], label="Technology"),
    ]
    decisions = find_duplicate_clusters(nodes, threshold=0.9)
    assert decisions == []


def test_nodes_without_embedding_are_ignored() -> None:
    nodes = [
        KnowledgeNode(node_id="a", label="Concept", name="a", embedding=None),
        KnowledgeNode(node_id="b", label="Concept", name="b", embedding=None),
    ]
    assert find_duplicate_clusters(nodes) == []
