"""`POST /validate` (docs/design/phase-2d/02-personality-engine.md Sec11) --
HTTP mirror of the `personality.validate_response` Event-Bus RPC
(`events/handlers.py`), for admin/debug use. Runs the same
`domain.validator.validate` the RPC path runs."""

from __future__ import annotations

import time
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from nova_personality_engine.domain.models import ConfidenceTier, ValidationResult
from nova_personality_engine.domain.validator import validate

router = APIRouter(tags=["validate"])


class ValidateRequest(BaseModel):
    content: str
    confidence_tier: ConfidenceTier = ConfidenceTier.UNKNOWN
    session_id: UUID


@router.post("/validate", response_model=ValidationResult)
async def validate_response(body: ValidateRequest, request: Request) -> ValidationResult:
    state = request.app.state
    if state.core_identity is None:
        raise HTTPException(status_code=503, detail="Core identity is not loaded.")

    started = time.perf_counter()
    result = validate(body.content, confidence_tier=body.confidence_tier)
    state.metrics.validate_response_duration_seconds.record(time.perf_counter() - started)

    state.metrics.validations_total.add(1, {"outcome": "passed" if result.passed else "failed"})
    for violation in result.violations:
        state.metrics.violations_total.add(1, {"check_family": violation.check_family.value})

    await state.repository.record_validation_audit(
        session_id=body.session_id, result=result, selected_style=None
    )
    return result
