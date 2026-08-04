"""Prediction worker -- Arq scheduled job driving `domain/prediction.py`
against `WorldHistoryRepository` (docs/design/phase-1/03-world-model-engine.md
§7, §20's Phase 1 heuristic scope -- see `domain/prediction.py`'s module
docstring for why this is structural pattern-matching, not a learned model).

Same user-discovery limitation as `snapshot_worker.py`: takes an explicit
`user_ids` list rather than inventing a directory lookup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from nova_contracts import PredictionPayload
from nova_observability import get_logger

from nova_world_model_engine.domain import prediction
from nova_world_model_engine.domain.ports import OutboxEvent, WorldHistoryRepository

if TYPE_CHECKING:
    from nova_world_model_engine.observability import WorldModelEngineMetrics

logger = get_logger("world-model-engine.workers.prediction")

HISTORY_SAMPLE_LIMIT = 1000


async def run_predictions(
    history_repo: WorldHistoryRepository,
    *,
    user_ids: list[UUID],
    metrics: WorldModelEngineMetrics | None = None,
) -> int:
    generated = 0
    for user_id in user_ids:
        history = await history_repo.list_recent_history_for_user(
            user_id=user_id, limit=HISTORY_SAMPLE_LIMIT
        )
        predictions = prediction.predict_from_history(history, user_id=user_id)
        for pred in predictions:
            outbox = OutboxEvent(
                subject="world_model.prediction.generated",
                payload=PredictionPayload(
                    prediction_id=pred.id,
                    user_id=pred.user_id,
                    prediction=pred.prediction,
                    confidence=pred.confidence,
                    predicted_for=pred.predicted_for,
                ).model_dump(mode="json"),
                correlation_id=uuid4(),
            )
            await history_repo.create_prediction(pred, outbox_event=outbox)
            generated += 1
            if metrics is not None:
                metrics.predictions_generated_total.add(1)
    if generated:
        logger.info("predictions generated", extra={"count": generated})
    return generated


async def arq_run_predictions(ctx: dict) -> None:
    """Arq entrypoint (`WorkerSettings.cron_jobs` in `workers/__init__.py`)."""
    await run_predictions(
        ctx["history_repository"],
        user_ids=ctx.get("known_user_ids", []),
        metrics=ctx.get("metrics"),
    )
