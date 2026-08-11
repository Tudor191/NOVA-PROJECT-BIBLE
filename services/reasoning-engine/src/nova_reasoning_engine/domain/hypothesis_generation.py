"""Hypothesis Generation (docs/design/phase-2b/00-reasoning-engine.md §12) --
Bible Part 8: "Before concluding, NOVA generates multiple explanations... each
hypothesis is investigated independently."

**Why this step legitimately calls a model, unlike almost every other
domain-layer decision in NOVA.** Generating candidate explanations *is the
actual cognitive task* Bible Part 8 assigns this engine -- it is not a
meta-decision about how to reason, it is the reasoning itself. Every other
*scoring* mechanism in this design (§8, §9, §10, §15, §16) is deliberately
structural and model-free; this module is the deliberate, documented
exception, per ADR-020 ("every AI model interaction passes through the
orchestration layer").

**Phase 2D-D's correction judgment** (docs/design/phase-2d/
06-personal-companion.md §5.3) reuses this same, single model call rather
than adding a second one -- per that document's own instruction, no
separate classifier or parallel reasoning path. When
`HypothesisGenerationRequest.prior_nova_utterance` is set, the prompt gains
one more context component and one more instruction; the reply is parsed
for both the hypotheses and the correction verdict in one pass."""

from __future__ import annotations

import re
from uuid import UUID

from nova_contracts import ContextComponentPayload, GenerateRequestPayload, PrivacyLevel

from nova_reasoning_engine.domain.models import (
    ContextBundle,
    Hypothesis,
    HypothesisGenerationRequest,
)
from nova_reasoning_engine.domain.ports import ModelOrchestrationPort

__all__ = ["HypothesisGenerationError", "build_prompt_context", "generate_hypotheses"]

_NUMBERED_LINE = re.compile(r"^\s*(?:\d+[.)]|-|\*)\s+(.+)$")
_CORRECTION_LINE = re.compile(r"^\s*CORRECTION:\s*(yes|no)\s*$", re.IGNORECASE)
_CORRECTION_INSTRUCTION = (
    'Then, on its own final line, write exactly "CORRECTION: yes" if the '
    "objective substantively contradicts or corrects something NOVA itself "
    'said in the prior_response context below -- otherwise write "CORRECTION: '
    'no". Only write "yes" for a genuine, evidence-based contradiction of what '
    "NOVA said. Do not write \"yes\" merely because the objective expresses "
    "uncertainty, disagreement without a substantive counter-claim, a request "
    "for clarification, or the user correcting their own earlier statement -- "
    "none of those are corrections of NOVA."
)
"""Phase 2D-D §5.1's exact exclusions, given to the model verbatim rather
than left to inference -- the same "state the precise behavioral
distinction directly" discipline `personality.validate_response`'s own
constraint-checking already uses elsewhere in this codebase."""


class HypothesisGenerationError(Exception):
    """Raised when the model call fails (`finish_reason == "error"`) or
    returns no parseable hypotheses -- `pipeline.py` routes this into
    Failure Handling (§17), never surfaces it as an unhandled exception."""


def _component(source: str, text: str, *, priority: int) -> ContextComponentPayload:
    return ContextComponentPayload(
        source=source, text=text, token_estimate=len(text) // 4, priority=priority
    )


def build_prompt_context(
    objective: str, context: ContextBundle, *, prior_nova_utterance: str | None = None
) -> list[ContextComponentPayload]:
    """Formats the already-assembled `ContextBundle` as `ContextComponent`s
    exactly the way the AI Model Orchestration Engine's own Prompt Pipeline
    expects (design doc §12) -- this module is a caller of that boundary,
    never a violator of it (§0).

    `prior_nova_utterance` (Phase 2D-D §5.2/§5.3): when supplied, appended as
    a `prior_response` component so the model has NOVA's own prior statement
    in view for the correction judgment -- omitted entirely otherwise, so a
    caller with no conversation session (e.g. a future Planning Engine) never
    pays for or triggers that judgment."""
    components = [_component("objective", objective, priority=10)]

    if prior_nova_utterance:
        components.append(_component("prior_response", prior_nova_utterance, priority=9))

    if context.memories:
        text = "\n".join(f"- {m.summary}" for m in context.memories)
        components.append(_component("memory", text, priority=8))

    if context.knowledge:
        text = "\n".join(f"- {k.name} ({k.layer})" for k in context.knowledge)
        components.append(_component("knowledge", text, priority=8))

    if context.world_model is not None:
        wm = context.world_model
        fields = (
            ("objective", wm.objective),
            ("project_id", wm.project_id),
            ("device", wm.device),
            ("task", wm.task),
            ("activity", wm.activity),
        )
        text = ", ".join(f"{field}={value}" for field, value in fields if value is not None)
        if text:
            components.append(_component("world_model", text, priority=6))

    if context.goals:
        text = "\n".join(f"- {g.description} (priority {g.priority:.2f})" for g in context.goals)
        components.append(_component("goals", text, priority=7))

    if context.constraints:
        text = "\n".join(
            f"- {c.description} ({'hard' if c.hard else 'soft'})" for c in context.constraints
        )
        components.append(_component("constraints", text, priority=9))

    return components


def _parse_is_correction(text: str) -> bool | None:
    """Phase 2D-D §5.1 -- scans every line for the model's own
    `CORRECTION: yes|no` verdict, requested only when a `prior_response`
    context component was included (`generate_hypotheses` below). Returns
    `None` (not `False`) if the model never emitted the line at all --
    "no judgment attempted" is not the same claim as "judged, not a
    correction"."""
    for line in text.splitlines():
        match = _CORRECTION_LINE.match(line)
        if match:
            return match.group(1).lower() == "yes"
    return None


def _strip_correction_line(text: str) -> str:
    """Removes the `CORRECTION: yes|no` line before hypothesis parsing, so
    it can never be mistaken for a candidate hypothesis regardless of the
    model's exact formatting."""
    return "\n".join(line for line in text.splitlines() if not _CORRECTION_LINE.match(line))


def _parse_hypotheses(text: str, *, reasoning_process_id: UUID, minimum: int) -> list[Hypothesis]:
    lines = [m.group(1).strip() for line in text.splitlines() if (m := _NUMBERED_LINE.match(line))]
    if not lines:
        # No list markers found -- treat non-empty paragraphs as one hypothesis each,
        # never silently discard a usable response just because it wasn't numbered.
        lines = [p.strip() for p in text.split("\n\n") if p.strip()]
    return [
        Hypothesis(reasoning_process_id=reasoning_process_id, description=line)
        for line in lines[: max(minimum, len(lines))]
        if line
    ]


async def generate_hypotheses(
    request: HypothesisGenerationRequest,
    *,
    reasoning_process_id: UUID,
    model_port: ModelOrchestrationPort,
    requesting_engine: str,
    correlation_id: UUID,
    privacy_hint: PrivacyLevel = PrivacyLevel.INTERNAL,
) -> tuple[list[Hypothesis], str, bool | None]:
    """Calls `ModelOrchestrationPort.generate` and parses its response into
    independent `Hypothesis` candidates. Returns the hypotheses, a
    `model_used` identifier (`"<provider>:<model_id>"`) for the reasoning
    trace (§19), and (Phase 2D-D §5.1) the correction verdict -- `None`
    unless `request.prior_nova_utterance` was set."""
    task_type = request.thinking_mode_hint or "reasoning"
    prompt_instruction = (
        f"Generate at least {request.minimum_hypotheses} distinct, independently "
        "investigable hypotheses or candidate explanations for the objective below. "
        "List each on its own line, numbered."
    )
    if request.prior_nova_utterance:
        prompt_instruction = f"{prompt_instruction} {_CORRECTION_INSTRUCTION}"
    components = build_prompt_context(
        request.objective, request.context, prior_nova_utterance=request.prior_nova_utterance
    )
    components.append(_component("instruction", prompt_instruction, priority=10))

    try:
        reply = await model_port.generate(
            GenerateRequestPayload(
                context=components,
                task_type=task_type,
                privacy_hint=privacy_hint,
                requesting_engine=requesting_engine,
                correlation_id=correlation_id,
            )
        )
    except TimeoutError as exc:
        # Unlike the read-only ports (Memory/Knowledge/World Model), there is no
        # sensible empty fallback for a failed model call -- this engine cannot
        # generate hypotheses without one, so a transport timeout becomes the
        # same domain-level failure a `finish_reason="error"` reply already is.
        raise HypothesisGenerationError(f"model orchestration call timed out: {exc}") from exc

    if reply.finish_reason == "error":
        raise HypothesisGenerationError(reply.error or "model call returned finish_reason=error")

    is_correction = _parse_is_correction(reply.text) if request.prior_nova_utterance else None
    hypotheses_text = (
        _strip_correction_line(reply.text) if request.prior_nova_utterance else reply.text
    )
    hypotheses = _parse_hypotheses(
        hypotheses_text,
        reasoning_process_id=reasoning_process_id,
        minimum=request.minimum_hypotheses,
    )
    if not hypotheses:
        raise HypothesisGenerationError("model response contained no parseable hypotheses")

    return hypotheses, f"{reply.provider}:{reply.model_id}", is_correction
