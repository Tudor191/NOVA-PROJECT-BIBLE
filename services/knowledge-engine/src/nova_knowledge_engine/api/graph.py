"""`/v1/knowledge/graph` -- subgraph query for visualization (docs/design/phase-1/
02-knowledge-engine.md §14, referenced from SAD 04).

Builds the node set from Postgres (`KnowledgeMetadataRepository.list_nodes`, which
already has the `scope`/`project_id`/`user_id` filtering §14's `scope=project:<id>`
query param needs), then gathers edges among just that node set via one
`GraphStore.traverse(node_id, max_hops=1)` call per node. `GraphQuery` requires a
single `label` (no label-agnostic "give me everything" primitive, ADR-007's
backend-agnostic constraint), so a single batched Cypher query for an arbitrary
node set isn't expressible through the abstracted interface -- documented as a
Phase 1 simplification (`README.md`'s Known Limitations), acceptable at the small
subgraph sizes a visualization call requests (`limit`, capped at 50).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from nova_graphstore_sdk import TraversalDirection, TraversalSpec
from pydantic import BaseModel

from nova_knowledge_engine.domain.models import KnowledgeLayer, KnowledgeScope

router = APIRouter(prefix="/v1/knowledge", tags=["knowledge"])

MAX_SUBGRAPH_NODES = 50


class GraphNodeView(BaseModel):
    node_id: str
    label: str
    name: str
    layer: KnowledgeLayer
    confidence: float


class GraphEdgeView(BaseModel):
    from_id: str
    to_id: str
    relationship_type: str


class SubgraphResponse(BaseModel):
    nodes: list[GraphNodeView]
    edges: list[GraphEdgeView]


def _parse_scope(raw: str | None) -> tuple[KnowledgeScope | None, UUID | None, UUID | None]:
    """Parses the `scope=project:<id>` / `scope=personal:<id>` / `scope=global`
    query param shape §14 specifies."""
    if raw is None:
        return None, None, None
    if raw == "global":
        return KnowledgeScope.GLOBAL, None, None
    if ":" not in raw:
        raise HTTPException(status_code=400, detail=f"Invalid scope {raw!r}")
    kind, _, raw_id = raw.partition(":")
    try:
        parsed_id = UUID(raw_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid scope id in {raw!r}") from exc
    if kind == "project":
        return KnowledgeScope.PROJECT, parsed_id, None
    if kind == "personal":
        return KnowledgeScope.PERSONAL, None, parsed_id
    raise HTTPException(status_code=400, detail=f"Invalid scope kind in {raw!r}")


@router.get("/graph", response_model=SubgraphResponse)
async def get_subgraph(
    request: Request,
    scope: str | None = None,
    label: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_SUBGRAPH_NODES)] = MAX_SUBGRAPH_NODES,
) -> SubgraphResponse:
    state = request.app.state
    parsed_scope, project_id, user_id = _parse_scope(scope)
    nodes = await state.repository.list_nodes(
        scope=parsed_scope, project_id=project_id, user_id=user_id, label=label, limit=limit
    )
    node_ids = {n.node_id for n in nodes}

    edges: list[GraphEdgeView] = []
    seen: set[tuple[str, str, str]] = set()
    for node in nodes:
        try:
            result = await state.graph_store.traverse(
                node.node_id, TraversalSpec(direction=TraversalDirection.BOTH, max_hops=1, limit=50)
            )
        except Exception:  # noqa: BLE001 -- a single unreachable-node traversal must not fail the whole subgraph
            continue
        for rel in result.relationships:
            if rel.from_id not in node_ids or rel.to_id not in node_ids:
                continue
            key = (rel.from_id, rel.to_id, rel.type)
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                GraphEdgeView(from_id=rel.from_id, to_id=rel.to_id, relationship_type=rel.type)
            )

    return SubgraphResponse(
        nodes=[
            GraphNodeView(
                node_id=n.node_id,
                label=n.label,
                name=n.name,
                layer=n.layer,
                confidence=n.confidence,
            )
            for n in nodes
        ],
        edges=edges,
    )
