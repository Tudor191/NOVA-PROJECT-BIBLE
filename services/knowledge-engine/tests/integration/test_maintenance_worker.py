from nova_graphstore_sdk.backends.in_memory import InMemoryGraphStore
from nova_knowledge_engine.domain.models import KnowledgeLayer, KnowledgeNode
from nova_knowledge_engine.workers.maintenance_worker import run_maintenance

from tests.fakes.metadata_repository import FakeKnowledgeMetadataRepository


async def test_layer_advances_when_predicate_satisfied() -> None:
    repository = FakeKnowledgeMetadataRepository()
    graph_store = InMemoryGraphStore()
    await graph_store.connect()

    node = KnowledgeNode(
        node_id="technology:postgresql",
        label="Technology",
        name="PostgreSQL",
        layer=KnowledgeLayer.PROCESSED,
        confidence=0.8,
    )
    repository.nodes[node.node_id] = node
    from nova_knowledge_engine.domain.models import SourceAttribution

    repository.sources[node.node_id] = [
        SourceAttribution(node_id=node.node_id, source_type="user")
    ]

    await run_maintenance(repository, graph_store)

    updated = repository.nodes[node.node_id]
    assert updated.layer is KnowledgeLayer.VERIFIED
    assert any(v.change_type == "layer_advanced" for v in repository.version_history)


async def test_no_advance_when_predicate_not_satisfied() -> None:
    repository = FakeKnowledgeMetadataRepository()
    graph_store = InMemoryGraphStore()
    await graph_store.connect()

    node = KnowledgeNode(
        node_id="technology:postgresql",
        label="Technology",
        name="PostgreSQL",
        layer=KnowledgeLayer.PROCESSED,
        confidence=0.2,  # below VERIFIED_MIN_CONFIDENCE
    )
    repository.nodes[node.node_id] = node

    await run_maintenance(repository, graph_store)

    assert repository.nodes[node.node_id].layer is KnowledgeLayer.PROCESSED


async def test_related_to_discovered_for_similar_embeddings() -> None:
    repository = FakeKnowledgeMetadataRepository()
    graph_store = InMemoryGraphStore()
    await graph_store.connect()

    a = KnowledgeNode(node_id="technology:a", label="Technology", name="A", embedding=[1.0, 0.0])
    b = KnowledgeNode(
        node_id="technology:b", label="Technology", name="B", embedding=[0.99, 0.01]
    )
    repository.nodes[a.node_id] = a
    repository.nodes[b.node_id] = b

    await run_maintenance(repository, graph_store)

    edge_subjects = [r.subject for r in repository.outbox.values()]
    assert "knowledge.edge.created" in edge_subjects


async def test_duplicate_detection_flags_without_deleting() -> None:
    repository = FakeKnowledgeMetadataRepository()
    graph_store = InMemoryGraphStore()
    await graph_store.connect()

    a = KnowledgeNode(
        node_id="technology:a", label="Technology", name="A", embedding=[1.0, 0.0], confidence=0.9
    )
    b = KnowledgeNode(
        node_id="technology:b", label="Technology", name="B", embedding=[1.0, 0.0], confidence=0.5
    )
    repository.nodes[a.node_id] = a
    repository.nodes[b.node_id] = b

    await run_maintenance(repository, graph_store)

    assert a.node_id in repository.nodes  # never deleted
    assert b.node_id in repository.nodes  # never deleted
    duplicate_entries = [
        v for v in repository.version_history if v.change_type == "duplicate_detected"
    ]
    assert len(duplicate_entries) == 1
    assert duplicate_entries[0].node_id == b.node_id
    assert duplicate_entries[0].new_value == {"keep_id": a.node_id}
