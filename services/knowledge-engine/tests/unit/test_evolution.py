from nova_knowledge_engine.domain import evolution
from nova_knowledge_engine.domain.models import KnowledgeLayer, UsageSummary


def _eval(**overrides: object) -> evolution.EvolutionInput:
    defaults: dict[str, object] = {
        "layer": KnowledgeLayer.RAW,
        "confidence": 0.5,
        "source_count": 0,
        "relationship_count": 0,
        "usage": UsageSummary(),
    }
    defaults.update(overrides)
    return evolution.EvolutionInput(**defaults)  # type: ignore[arg-type]


def test_raw_never_advances_on_its_own() -> None:
    decision = evolution.next_layer("n1", _eval(layer=KnowledgeLayer.RAW))
    assert decision is None


def test_processed_to_verified_requires_confidence_and_source() -> None:
    below_threshold = _eval(layer=KnowledgeLayer.PROCESSED, confidence=0.5, source_count=1)
    assert evolution.next_layer("n1", below_threshold) is None

    no_source = _eval(layer=KnowledgeLayer.PROCESSED, confidence=0.9, source_count=0)
    assert evolution.next_layer("n1", no_source) is None

    qualifies = _eval(layer=KnowledgeLayer.PROCESSED, confidence=0.7, source_count=1)
    decision = evolution.next_layer("n1", qualifies)
    assert decision is not None
    assert decision.to_layer is KnowledgeLayer.VERIFIED


def test_verified_to_connected_requires_two_relationships() -> None:
    one_relationship = _eval(layer=KnowledgeLayer.VERIFIED, relationship_count=1)
    assert evolution.next_layer("n1", one_relationship) is None
    decision = evolution.next_layer(
        "n1", _eval(layer=KnowledgeLayer.VERIFIED, relationship_count=2)
    )
    assert decision is not None
    assert decision.to_layer is KnowledgeLayer.CONNECTED


def test_connected_to_applied_requires_any_usage() -> None:
    assert evolution.next_layer("n1", _eval(layer=KnowledgeLayer.CONNECTED)) is None
    decision = evolution.next_layer(
        "n1", _eval(layer=KnowledgeLayer.CONNECTED, usage=UsageSummary(usage_count=1))
    )
    assert decision is not None
    assert decision.to_layer is KnowledgeLayer.APPLIED


def test_applied_to_expert_requires_high_confidence_and_usage_count() -> None:
    low_usage = _eval(
        layer=KnowledgeLayer.APPLIED, confidence=0.95, usage=UsageSummary(usage_count=1)
    )
    assert evolution.next_layer("n1", low_usage) is None

    low_confidence = _eval(
        layer=KnowledgeLayer.APPLIED, confidence=0.5, usage=UsageSummary(usage_count=10)
    )
    assert evolution.next_layer("n1", low_confidence) is None

    qualifies = _eval(
        layer=KnowledgeLayer.APPLIED, confidence=0.95, usage=UsageSummary(usage_count=10)
    )
    decision = evolution.next_layer("n1", qualifies)
    assert decision is not None
    assert decision.to_layer is KnowledgeLayer.EXPERT


def test_expert_to_strategic_requires_two_distinct_projects() -> None:
    from uuid import uuid4

    one_project = _eval(
        layer=KnowledgeLayer.EXPERT, usage=UsageSummary(distinct_project_ids=[uuid4()])
    )
    assert evolution.next_layer("n1", one_project) is None

    two_projects = _eval(
        layer=KnowledgeLayer.EXPERT, usage=UsageSummary(distinct_project_ids=[uuid4(), uuid4()])
    )
    decision = evolution.next_layer("n1", two_projects)
    assert decision is not None
    assert decision.to_layer is KnowledgeLayer.STRATEGIC


def test_strategic_is_terminal() -> None:
    decision = evolution.next_layer("n1", _eval(layer=KnowledgeLayer.STRATEGIC))
    assert decision is None
