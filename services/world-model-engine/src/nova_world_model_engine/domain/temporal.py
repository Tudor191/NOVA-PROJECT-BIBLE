"""Temporal Model -- history queries (docs/design/phase-1/03-world-model-engine.md
§2 "Context Timeline", §7 step 3). Read-side only; writes happen through
`object_graph.py` (history rows ride along with every observation) -- this
module composes those reads for callers like `api/objects.py`'s history
endpoint, keeping API routes from calling the repository directly.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from nova_world_model_engine.domain.models import ObjectStateHistoryEntry, Prediction
from nova_world_model_engine.domain.ports import WorldHistoryRepository


async def object_history(
    repository: WorldHistoryRepository,
    object_id: str,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
) -> list[ObjectStateHistoryEntry]:
    return await repository.list_object_history(object_id, since=since, until=until, limit=limit)


async def recent_predictions(
    repository: WorldHistoryRepository, *, user_id: UUID, limit: int = 50
) -> list[Prediction]:
    return await repository.list_predictions(user_id=user_id, limit=limit)
