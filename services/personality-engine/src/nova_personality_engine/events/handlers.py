"""`personality.validate_response.request` and `personality.style.select.
request` served RPC handlers (docs/design/phase-2d/02-personality-engine.md
Sec7.1, Sec10, Sec11) -- the Event Bus counterparts to `POST /validate` and
`GET /style` (`api/validate.py`, `api/style.py`), for `communication-engine`'s
intent-gate callers that use request/reply over HTTP.
"""

from __future__ import annotations

import time

from fastapi import FastAPI
from nova_contracts import (
    EventEnvelope,
    PersonalityStyleSelectReplyPayload,
    PersonalityStyleSelectRequestPayload,
    PersonalityValidateResponseReplyPayload,
    PersonalityValidateResponseRequestPayload,
    ViolationRecordPayload,
)

from nova_personality_engine.domain.models import ConfidenceTier
from nova_personality_engine.domain.style_selector import select_style
from nova_personality_engine.domain.validator import validate

__all__ = ["make_style_select_handler", "make_validate_response_handler"]


def make_validate_response_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> PersonalityValidateResponseReplyPayload:
        state = app.state
        payload = PersonalityValidateResponseRequestPayload.model_validate(envelope.payload)

        started = time.perf_counter()
        result = validate(
            payload.content, confidence_tier=ConfidenceTier(payload.confidence_tier.value)
        )
        state.metrics.validate_response_duration_seconds.record(time.perf_counter() - started)

        state.metrics.validations_total.add(1, {"outcome": "passed" if result.passed else "failed"})
        for violation in result.violations:
            state.metrics.violations_total.add(1, {"check_family": violation.check_family.value})

        await state.repository.record_validation_audit(
            session_id=payload.session_id, result=result, selected_style=None
        )

        return PersonalityValidateResponseReplyPayload(
            passed=result.passed,
            adjusted_content=result.adjusted_content,
            violations=[
                ViolationRecordPayload(check_family=v.check_family, detail=v.detail)
                for v in result.violations
            ],
        )

    return handle


def make_style_select_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> PersonalityStyleSelectReplyPayload:
        state = app.state
        payload = PersonalityStyleSelectRequestPayload.model_validate(envelope.payload)

        started = time.perf_counter()
        style, verbosity, technical_depth = select_style(
            situation_hint=payload.situation_hint,
            channel=payload.channel,
            memory_profile=state.memory_profile,
        )
        state.metrics.style_select_duration_seconds.record(time.perf_counter() - started)

        return PersonalityStyleSelectReplyPayload(
            style=style, verbosity=verbosity, technical_depth=technical_depth
        )

    return handle
