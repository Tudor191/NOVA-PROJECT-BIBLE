"""`/v1/world/graph` -- subgraph query for visualization (docs/design/phase-1/
03-world-model-engine.md §14, §7 step 2). Unlike Knowledge Engine's
`/v1/knowledge/graph` (which starts from a Postgres-scoped node list), World
Model has no Postgres-side object listing by scope -- `object_state_history`
is keyed by `object_id`/time, not scope/project. This route instead starts
from a single seed node (the `:WorldProject` named by `scope=project:<id>`)
and traverses outward, matching §7 step 2's "graph traversal via GraphStore,
bounded hops."
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from nova_graphstore_sdk import TraversalDirection, TraversalSpec
from pydantic import BaseModel

router = APIRouter(prefix="/v1/world", tags=["world"])


class GraphNodeView(BaseModel):
    object_id: str
    labels: tuple[str, ...]
    properties: dict


class GraphEdgeView(BaseModel):
    from_id: str
    to_id: str
    relationship_type: str


class SubgraphResponse(BaseModel):
    nodes: list[GraphNodeView]
    edges: list[GraphEdgeView]


def _seed_id_from_scope(raw: str) -> str:
    if ":" not in raw:
        raise HTTPException(
            status_code=400, detail=f"Invalid scope {raw!r}, expected 'project:<id>'"
        )
    kind, _, seed_id = raw.partition(":")
    if kind != "project":
        raise HTTPException(status_code=400, detail=f"Unsupported scope kind {kind!r}")
    return seed_id


@router.get("/graph", response_model=SubgraphResponse)
async def get_subgraph(
    request: Request,
    scope: str,
    max_hops: Annotated[int, Query(ge=1, le=5)] = 2,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> SubgraphResponse:
    state = request.app.state
    seed_id = _seed_id_from_scope(scope)
    try:
        result = await state.graph_store.traverse(
            seed_id,
            TraversalSpec(direction=TraversalDirection.BOTH, max_hops=max_hops, limit=limit),
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Graph store unavailable") from exc
    return SubgraphResponse(
        nodes=[
            GraphNodeView(object_id=n.id, labels=n.labels, properties=n.properties)
            for n in result.nodes
        ],
        edges=[
            GraphEdgeView(from_id=r.from_id, to_id=r.to_id, relationship_type=r.type)
            for r in result.relationships
        ],
    )
