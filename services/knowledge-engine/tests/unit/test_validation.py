import pytest
from nova_knowledge_engine.domain import validation
from nova_knowledge_engine.domain.models import KnowledgeNode
from nova_knowledge_engine.domain.normalization import RawInformation, normalize

from tests.fakes.metadata_repository import FakeKnowledgeMetadataRepository


async def test_new_candidate_has_no_existing_node() -> None:
    repo = FakeKnowledgeMetadataRepository()
    candidate = normalize(RawInformation(label="Technology", name="PostgreSQL", source_type="user"))
    result = await validation.validate(candidate, repository=repo)
    assert result.existing is None
    assert result.confidence == pytest.approx(0.8)  # user source, no corroboration bonus


async def test_low_trust_source_gets_lower_base_confidence() -> None:
    repo = FakeKnowledgeMetadataRepository()
    candidate = normalize(
        RawInformation(label="Concept", name="Speculative Idea", source_type="hypothesis")
    )
    result = await validation.validate(candidate, repository=repo)
    assert result.confidence == pytest.approx(0.3)


async def test_corroboration_never_lowers_existing_confidence() -> None:
    repo = FakeKnowledgeMetadataRepository()
    candidate = normalize(RawInformation(label="Technology", name="PostgreSQL", source_type="user"))
    repo.nodes[candidate.node_id] = KnowledgeNode(
        node_id=candidate.node_id, label="Technology", name="PostgreSQL", confidence=0.95
    )

    low_trust_candidate = normalize(
        RawInformation(label="Technology", name="PostgreSQL", source_type="hypothesis")
    )
    result = await validation.validate(low_trust_candidate, repository=repo)
    assert result.confidence >= 0.95
    assert result.existing is not None
