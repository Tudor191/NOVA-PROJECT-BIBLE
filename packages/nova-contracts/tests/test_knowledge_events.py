from uuid import uuid4

import pytest
from nova_contracts import (
    ContradictionPayload,
    KnowledgeEdgeCreatedPayload,
    KnowledgeLayer,
    KnowledgeNodeChangedPayload,
    KnowledgeRetrieveRequestPayload,
    KnowledgeScope,
    KnowledgeSearchResultPayload,
    KnowledgeTraverseRequestPayload,
    LayerAdvancedPayload,
    known_subjects,
    validate_payload,
)
from pydantic import ValidationError


def test_all_knowledge_subjects_are_registered() -> None:
    subjects = known_subjects()
    for subject in (
        "knowledge.node.created",
        "knowledge.node.updated",
        "knowledge.edge.created",
        "knowledge.contradiction.detected",
        "knowledge.contradiction.resolved",
        "knowledge.layer.advanced",
        "knowledge.link.request",
        "knowledge.traverse.request",
        "knowledge.retrieve.request",
    ):
        assert subject in subjects


def test_node_created_and_updated_share_one_payload_model() -> None:
    from nova_contracts.registry import payload_model_for

    assert payload_model_for("knowledge.node.created") is KnowledgeNodeChangedPayload
    assert payload_model_for("knowledge.node.updated") is KnowledgeNodeChangedPayload


def test_knowledge_node_changed_validates_against_registry() -> None:
    validated = validate_payload(
        "knowledge.node.created",
        {
            "node_id": "concept-postgres",
            "label": "Technology",
            "name": "PostgreSQL",
            "scope": "global",
            "confidence": 0.6,
            "layer": "raw",
            "version": 1,
        },
    )
    assert isinstance(validated, KnowledgeNodeChangedPayload)
    assert validated.scope is KnowledgeScope.GLOBAL
    assert validated.layer is KnowledgeLayer.RAW


def test_confidence_must_be_in_unit_interval() -> None:
    with pytest.raises(ValidationError):
        KnowledgeNodeChangedPayload(
            node_id="concept-x",
            label="Concept",
            name="X",
            scope=KnowledgeScope.GLOBAL,
            confidence=1.5,
            layer=KnowledgeLayer.RAW,
            version=1,
        )


def test_contradiction_payload_shared_by_detected_and_resolved() -> None:
    from nova_contracts.registry import payload_model_for

    assert payload_model_for("knowledge.contradiction.detected") is ContradictionPayload
    assert payload_model_for("knowledge.contradiction.resolved") is ContradictionPayload

    payload = ContradictionPayload(
        contradiction_id=uuid4(),
        node_a_id="concept-a",
        node_b_id="concept-b",
        description="conflicting definitions",
        status="open",
    )
    assert payload.resolution is None


def test_layer_advanced_payload_round_trips() -> None:
    payload = LayerAdvancedPayload(
        node_id="concept-postgres",
        previous_layer=KnowledgeLayer.VERIFIED,
        new_layer=KnowledgeLayer.CONNECTED,
        reason=">=2 graph relationships exist",
    )
    assert payload.previous_layer is KnowledgeLayer.VERIFIED
    assert payload.new_layer is KnowledgeLayer.CONNECTED


def test_knowledge_edge_created_carries_confidence() -> None:
    edge = KnowledgeEdgeCreatedPayload(
        from_node_id="concept-fastapi",
        to_node_id="concept-python",
        relationship_type="DEPENDS_ON",
        confidence=0.9,
    )
    assert edge.relationship_type == "DEPENDS_ON"


def test_knowledge_traverse_request_max_hops_bounds() -> None:
    with pytest.raises(ValidationError):
        KnowledgeTraverseRequestPayload(seed_node_id="concept-a", max_hops=10)

    request = KnowledgeTraverseRequestPayload(seed_node_id="concept-a")
    assert request.max_hops == 2


def test_knowledge_retrieve_request_limit_bounds() -> None:
    with pytest.raises(ValidationError):
        KnowledgeRetrieveRequestPayload(limit=1000)

    request = KnowledgeRetrieveRequestPayload(query_text="what do we know about postgres")
    assert request.limit == 10
    assert request.max_hops == 2


def test_knowledge_search_result_carries_relationship_context() -> None:
    result = KnowledgeSearchResultPayload(
        node_id="concept-postgres",
        label="Technology",
        name="PostgreSQL",
        score=0.87,
        similarity=0.8,
        confidence=0.75,
        layer=KnowledgeLayer.CONNECTED,
        related_node_ids=["concept-pgvector", "concept-sql"],
    )
    assert result.layer is KnowledgeLayer.CONNECTED
    assert len(result.related_node_ids) == 2
