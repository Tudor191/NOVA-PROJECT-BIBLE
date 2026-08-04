from nova_knowledge_engine.domain import contradiction, validation
from nova_knowledge_engine.domain.models import KnowledgeNode
from nova_knowledge_engine.domain.normalization import RawInformation, normalize

from tests.fakes.metadata_repository import FakeKnowledgeMetadataRepository


async def test_no_conflict_when_node_is_new_and_unique() -> None:
    repo = FakeKnowledgeMetadataRepository()
    candidate = normalize(RawInformation(label="Technology", name="PostgreSQL", source_type="user"))
    validated = await validation.validate(candidate, repository=repo)
    result = await contradiction.check_for_conflicts(validated, repository=repo)
    assert result is None


async def test_no_conflict_when_updating_existing_node() -> None:
    repo = FakeKnowledgeMetadataRepository()
    candidate = normalize(RawInformation(label="Technology", name="PostgreSQL", source_type="user"))
    repo.nodes[candidate.node_id] = KnowledgeNode(
        node_id=candidate.node_id, label="Technology", name="PostgreSQL", confidence=0.7
    )
    validated = await validation.validate(candidate, repository=repo)
    result = await contradiction.check_for_conflicts(validated, repository=repo)
    assert result is None


async def test_conflict_when_same_name_different_label_and_domain() -> None:
    repo = FakeKnowledgeMetadataRepository()
    existing = KnowledgeNode(
        node_id="company:postgres",
        label="Company",
        name="Postgres",
        domain="business",
        confidence=0.8,
    )
    repo.nodes[existing.node_id] = existing

    candidate = normalize(
        RawInformation(
            label="Technology", name="Postgres", source_type="user", domain="programming"
        )
    )
    validated = await validation.validate(candidate, repository=repo)
    result = await contradiction.check_for_conflicts(validated, repository=repo)
    assert result is not None
    assert result.node_a_id == existing.node_id
    assert result.node_b_id == candidate.node_id


async def test_no_conflict_when_both_low_confidence() -> None:
    repo = FakeKnowledgeMetadataRepository()
    existing = KnowledgeNode(
        node_id="company:postgres",
        label="Company",
        name="Postgres",
        domain="business",
        confidence=0.1,
    )
    repo.nodes[existing.node_id] = existing

    candidate = normalize(
        RawInformation(
            label="Technology", name="Postgres", source_type="hypothesis", domain="programming"
        )
    )
    validated = await validation.validate(candidate, repository=repo)
    # candidate confidence (hypothesis, 0.3) is below MIN_CONFIDENCE_FOR_CONFLICT -- accepted
    # at low confidence rather than flagged, matching contradiction.py's documented policy.
    result = await contradiction.check_for_conflicts(validated, repository=repo)
    assert result is None
