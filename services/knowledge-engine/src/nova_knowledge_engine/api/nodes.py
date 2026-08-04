"""`/v1/knowledge/nodes*` and `/v1/knowledge/search` routes -- thin, delegates to
`domain/acquisition.py`, `domain/graph_operations.py`, and `domain/retrieval.py`
(docs/design/phase-1/02-knowledge-engine.md §14). Never touches SQLAlchemy, Neo4j,
or pgvector directly -- everything goes through the ports already wired onto
`request.app.state` in `main.py`.
"""

from __future__ import annotations

import time
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from nova_knowledge_engine.domain import acquisition, graph_operations, retrieval
from nova_knowledge_engine.domain.models import KnowledgeNode, KnowledgeScope, PrivacyLevel
from nova_knowledge_engine.domain.normalization import RawInformation
from nova_knowledge_engine.domain.ports import VersionConflictError

router = APIRouter(prefix="/v1/knowledge", tags=["knowledge"])


class AcquireNodeRequest(BaseModel):
    label: str
    name: str
    source_type: str
    domain: str | None = None
    scope: KnowledgeScope = KnowledgeScope.GLOBAL
    project_id: UUID | None = None
    user_id: UUID | None = None
    privacy_level: PrivacyLevel = PrivacyLevel.INTERNAL
    source_ref: str | None = None
    excerpt: str | None = None


class AcquireNodeResponse(BaseModel):
    outcome: str
    node: KnowledgeNode | None = None
    conflict_id: UUID | None = None


class UpdateNodeRequest(BaseModel):
    """`PATCH` body -- manual correction. `label`, `scope`, and `layer` are never
    editable here (layer has its own evolution-driven path, §6)."""

    name: str | None = None
    domain: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    privacy_level: PrivacyLevel | None = None


@router.post("/nodes", response_model=AcquireNodeResponse, status_code=201)
async def acquire_node(body: AcquireNodeRequest, request: Request) -> AcquireNodeResponse:
    """Mostly system/internal use -- most acquisition comes from event subscribers,
    not this endpoint directly (mirrors Memory Engine's `POST /v1/memories`)."""
    state = request.app.state
    start = time.perf_counter()
    result = await acquisition.ingest(
        state.repository,
        RawInformation(
            label=body.label,
            name=body.name,
            source_type=body.source_type,
            domain=body.domain,
            scope=body.scope,
            project_id=body.project_id,
            user_id=body.user_id,
            privacy_level=body.privacy_level,
            source_ref=body.source_ref,
            excerpt=body.excerpt,
        ),
    )
    state.metrics.acquisition_duration_seconds.record(time.perf_counter() - start)
    state.metrics.nodes_acquired_total.add(1, {"outcome": result.outcome})
    if result.outcome == "conflict":
        state.metrics.contradictions_detected_total.add(1)
    return AcquireNodeResponse(
        outcome=result.outcome,
        node=result.node,
        conflict_id=result.conflict.id if result.conflict else None,
    )


@router.get("/search", response_model=list[KnowledgeNode])
async def search_nodes(
    request: Request,
    q: Annotated[
        str | None, Query(description="Raw text, embedded and run as semantic search.")
    ] = None,
    seed_node_id: str | None = None,
    scope: KnowledgeScope | None = None,
    project_id: UUID | None = None,
    user_id: UUID | None = None,
    max_hops: Annotated[int, Query(ge=1, le=5)] = 2,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> list[KnowledgeNode]:
    """Returns the underlying `KnowledgeNode` for each ranked result -- richer
    ranking metadata (score, similarity, related node ids) is what the
    `knowledge.retrieve.request` RPC reply carries instead (§14), since this REST
    route's callers are typically UI/CLI listings, not ranking-aware agents."""
    state = request.app.state
    start = time.perf_counter()
    result = await retrieval.retrieve(
        retrieval.RetrievalQuery(
            correlation_id=uuid4(),
            query_text=q,
            seed_node_id=seed_node_id,
            scope=scope,
            project_id=project_id,
            user_id=user_id,
            max_hops=max_hops,
            limit=limit,
        ),
        repository=state.repository,
        vector_index=state.vector_index,
        embedding_provider=state.embedding_provider,
        graph_store=state.graph_store,
    )
    state.metrics.retrieval_duration_seconds.record(time.perf_counter() - start)
    if result.degraded:
        state.metrics.retrieval_degraded_total.add(1)
    nodes = []
    for scored in result.results:
        node = await state.repository.get_node(scored.node_id)
        if node is not None:
            nodes.append(node)
    return nodes


@router.get("/nodes/{node_id}", response_model=KnowledgeNode)
async def get_node(node_id: str, request: Request) -> KnowledgeNode:
    state = request.app.state
    node = await state.repository.get_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Knowledge node not found")
    return node


@router.patch("/nodes/{node_id}", response_model=KnowledgeNode)
async def update_node(node_id: str, body: UpdateNodeRequest, request: Request) -> KnowledgeNode:
    state = request.app.state
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    existing = await state.repository.get_node(node_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Knowledge node not found")
    try:
        return await graph_operations.correct_node(
            state.repository,
            node_id,
            updates=updates,
            expected_version=existing.version,
            actor="api.correction",
            correlation_id=uuid4(),
        )
    except graph_operations.NodeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except VersionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
