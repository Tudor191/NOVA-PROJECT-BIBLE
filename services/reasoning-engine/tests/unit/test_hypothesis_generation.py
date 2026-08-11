from uuid import uuid4

from nova_contracts import GenerateReplyPayload
from nova_reasoning_engine.domain import hypothesis_generation
from nova_reasoning_engine.domain.models import ContextBundle, HypothesisGenerationRequest

from tests.fakes.ports import FakeModelOrchestrationPort


def test_build_prompt_context_omits_prior_response_when_not_supplied() -> None:
    components = hypothesis_generation.build_prompt_context(
        "what should we do next?", ContextBundle()
    )
    assert all(c.source != "prior_response" for c in components)


def test_build_prompt_context_includes_prior_response_when_supplied() -> None:
    components = hypothesis_generation.build_prompt_context(
        "what should we do next?",
        ContextBundle(),
        prior_nova_utterance="The meeting is on Tuesday.",
    )
    prior = [c for c in components if c.source == "prior_response"]
    assert len(prior) == 1
    assert prior[0].text == "The meeting is on Tuesday."


async def test_generate_hypotheses_without_prior_utterance_never_requests_correction_verdict() -> (
    None
):
    model_port = FakeModelOrchestrationPort()
    request = HypothesisGenerationRequest(
        objective="pick an approach", context=ContextBundle(), minimum_hypotheses=3
    )
    hypotheses, _model_used, is_correction = await hypothesis_generation.generate_hypotheses(
        request,
        reasoning_process_id=uuid4(),
        model_port=model_port,
        requesting_engine="test",
        correlation_id=uuid4(),
    )
    assert is_correction is None
    assert len(hypotheses) == 3
    # No instruction component should mention the correction verdict at all.
    sent = model_port.requests[0]
    assert not any(c.source == "prior_response" for c in sent.context)
    instruction = next(c for c in sent.context if c.source == "instruction")
    assert "CORRECTION" not in instruction.text


async def test_generate_hypotheses_parses_correction_yes_and_strips_the_line() -> None:
    model_port = FakeModelOrchestrationPort(
        reply=GenerateReplyPayload(
            text=(
                "1. The first candidate explanation.\n"
                "2. The second candidate explanation.\n"
                "3. The third candidate explanation.\n"
                "CORRECTION: yes"
            ),
            input_tokens=10,
            output_tokens=10,
            finish_reason="stop",
            structural_confidence=0.9,
            model_id=uuid4(),
            provider="fake",
        )
    )
    request = HypothesisGenerationRequest(
        objective="it's actually Wednesday, not Tuesday",
        context=ContextBundle(),
        minimum_hypotheses=3,
        prior_nova_utterance="The meeting is on Tuesday.",
    )
    hypotheses, _model_used, is_correction = await hypothesis_generation.generate_hypotheses(
        request,
        reasoning_process_id=uuid4(),
        model_port=model_port,
        requesting_engine="test",
        correlation_id=uuid4(),
    )
    assert is_correction is True
    assert len(hypotheses) == 3
    assert all("CORRECTION" not in h.description for h in hypotheses)

    sent = model_port.requests[0]
    prior = [c for c in sent.context if c.source == "prior_response"]
    assert len(prior) == 1
    instruction = next(c for c in sent.context if c.source == "instruction")
    assert "CORRECTION: yes" in instruction.text
    assert "CORRECTION: no" in instruction.text


async def test_generate_hypotheses_parses_correction_no() -> None:
    model_port = FakeModelOrchestrationPort(
        reply=GenerateReplyPayload(
            text=(
                "1. The first candidate explanation.\n"
                "2. The second candidate explanation.\n"
                "3. The third candidate explanation.\n"
                "CORRECTION: no"
            ),
            input_tokens=10,
            output_tokens=10,
            finish_reason="stop",
            structural_confidence=0.9,
            model_id=uuid4(),
            provider="fake",
        )
    )
    request = HypothesisGenerationRequest(
        objective="I'm not sure, maybe Tuesday?",
        context=ContextBundle(),
        minimum_hypotheses=3,
        prior_nova_utterance="The meeting is on Tuesday.",
    )
    _hypotheses, _model_used, is_correction = await hypothesis_generation.generate_hypotheses(
        request,
        reasoning_process_id=uuid4(),
        model_port=model_port,
        requesting_engine="test",
        correlation_id=uuid4(),
    )
    assert is_correction is False


async def test_generate_hypotheses_missing_correction_line_is_none_not_false() -> None:
    """A prior utterance was supplied (so the verdict was requested), but the
    model reply never emitted the line -- this must stay `None` ("no verdict
    present"), never silently coerce to `False` ("verified, not a
    correction")."""
    model_port = FakeModelOrchestrationPort()  # default reply has no CORRECTION line
    request = HypothesisGenerationRequest(
        objective="pick an approach",
        context=ContextBundle(),
        minimum_hypotheses=3,
        prior_nova_utterance="The meeting is on Tuesday.",
    )
    _hypotheses, _model_used, is_correction = await hypothesis_generation.generate_hypotheses(
        request,
        reasoning_process_id=uuid4(),
        model_port=model_port,
        requesting_engine="test",
        correlation_id=uuid4(),
    )
    assert is_correction is None


def test_correction_instruction_states_the_exact_exclusions() -> None:
    """Fork E approval, requirement 3: uncertainty, disagreement, a
    clarification request, and user self-correction must never count -- this
    guards that the exact text given to the model still names all four."""
    text = hypothesis_generation._CORRECTION_INSTRUCTION
    assert "uncertainty" in text
    assert "disagreement" in text
    assert "clarification" in text
    assert "correcting their own earlier statement" in text
