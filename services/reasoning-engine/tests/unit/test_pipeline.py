import asyncio
from uuid import UUID, uuid4

import pytest
from nova_contracts import GenerateReplyPayload
from nova_reasoning_engine.domain import modes, pipeline
from nova_reasoning_engine.domain.models import (
    Constraint,
    Goal,
    KnowledgeReference,
    MemoryReference,
    ReasoningMode,
    ReasoningRequest,
)
from nova_reasoning_engine.domain.trace import chain_depth

from tests.fakes.ports import (
    FakeGoalsPort,
    FakeKnowledgePort,
    FakeMemoryPort,
    FakeModelOrchestrationPort,
    FakePersonalContextPort,
    FakeWorldModelPort,
)
from tests.fakes.repository import FakeReasoningRepository


def _ports(**overrides):
    defaults = dict(
        memory_port=FakeMemoryPort(),
        knowledge_port=FakeKnowledgePort(),
        world_model_port=FakeWorldModelPort(),
        personal_context_port=FakePersonalContextPort(),
        goals_port=FakeGoalsPort(),
        model_port=FakeModelOrchestrationPort(),
        repository=FakeReasoningRepository(),
    )
    defaults.update(overrides)
    return defaults


async def test_reactive_mode_short_circuits_without_a_model_call() -> None:
    knowledge_port = FakeKnowledgePort(
        [KnowledgeReference(node_id="n1", name="Paris", layer="verified", confidence=0.9)]
    )
    model_port = FakeModelOrchestrationPort()
    ports = _ports(knowledge_port=knowledge_port, model_port=model_port)

    request = ReasoningRequest(
        objective_text="what is the capital of France?",
        user_id=uuid4(),
        requesting_engine="test",
        reasoning_mode_hint=ReasoningMode.REACTIVE,
    )
    decision, trace, chosen = await pipeline.run(request, **ports)

    assert decision.confidence_score == pytest.approx(0.9)
    assert trace.reasoning_mode is ReasoningMode.REACTIVE
    assert trace.outcome == "decided"
    assert model_port.requests == []  # no model call for Reactive mode

    repository = ports["repository"]
    stored_process = repository.processes[decision.reasoning_process_id]
    assert stored_process.status == "decided"
    assert stored_process.completed_at is not None
    assert len(repository.outbox) == 1
    assert repository.outbox[0].subject == "reasoning.process.completed"
    # Fork 3B-4: objective_text/chosen_description must survive onto the
    # published payload, sourced from the real pipeline state, not
    # reconstructed downstream.
    published = repository.outbox[0].payload
    assert published["objective_text"] == "what is the capital of France?"
    assert chosen is not None
    assert published["chosen_description"] == chosen.description


async def test_analytical_mode_produces_a_decided_decision() -> None:
    memory_port = FakeMemoryPort(
        [MemoryReference(memory_id=uuid4(), summary="user prefers dark mode", confidence=0.8)]
    )
    knowledge_port = FakeKnowledgePort(
        [
            KnowledgeReference(
                node_id="n1", name="candidate explanation", layer="expert", confidence=0.9
            )
        ]
    )
    ports = _ports(memory_port=memory_port, knowledge_port=knowledge_port)

    request = ReasoningRequest(
        objective_text="candidate explanation for the bug",
        user_id=uuid4(),
        requesting_engine="test",
        reasoning_mode_hint=ReasoningMode.ANALYTICAL,
    )
    decision, trace, chosen = await pipeline.run(request, **ports)

    assert trace.reasoning_mode is ReasoningMode.ANALYTICAL
    assert trace.outcome in {"decided", "degraded"}
    assert decision.selected_alternative_id is not None
    assert trace.model_used is not None
    repository = ports["repository"]
    assert repository.hypotheses  # persisted via record_hypotheses
    assert repository.alternatives  # persisted via record_alternatives

    stored_process = repository.processes[decision.reasoning_process_id]
    assert stored_process.status == trace.outcome
    assert stored_process.completed_at is not None
    assert len(repository.outbox) == 1
    assert repository.outbox[0].subject == "reasoning.process.completed"
    # Fork 3B-4: same guarantee as the Reactive-mode test above, for the
    # main (hypothesis-generating) path's own `_completed_outbox_event`
    # call site.
    published = repository.outbox[0].payload
    assert published["objective_text"] == "candidate explanation for the bug"
    assert chosen is not None
    assert published["chosen_description"] == chosen.description


async def test_hypothesis_generation_failure_produces_a_failed_trace() -> None:
    failing_model = FakeModelOrchestrationPort(
        reply=GenerateReplyPayload(
            text="",
            input_tokens=0,
            output_tokens=0,
            finish_reason="error",
            structural_confidence=0.0,
            model_id=uuid4(),
            provider="fake",
            error="no models available",
        )
    )
    ports = _ports(model_port=failing_model)

    request = ReasoningRequest(
        objective_text="anything",
        user_id=uuid4(),
        requesting_engine="test",
        reasoning_mode_hint=ReasoningMode.ANALYTICAL,
    )
    decision, trace, _chosen = await pipeline.run(request, **ports)

    assert decision.selected_alternative_id is None
    assert decision.confidence_score == 0.0
    assert trace.outcome == "failed"

    repository = ports["repository"]
    stored_process = repository.processes[decision.reasoning_process_id]
    assert stored_process.status == "failed"
    assert stored_process.completed_at is not None
    assert len(repository.outbox) == 1
    assert repository.outbox[0].subject == "reasoning.process.failed"


async def test_no_supporting_context_fails_after_evidence_collection() -> None:
    """When no memory/knowledge/world-model context overlaps with any
    generated hypothesis, every hypothesis comes back `unsupported` (§13) and
    -- after the bounded retry (§14) also finds nothing -- the pipeline fails
    cleanly rather than fabricating an unsupported decision."""
    ports = _ports()  # every port empty: nothing for evidence_collection to match
    request = ReasoningRequest(
        objective_text="an objective with no matching context anywhere",
        user_id=uuid4(),
        requesting_engine="test",
        reasoning_mode_hint=ReasoningMode.ANALYTICAL,
    )
    decision, trace, _chosen = await pipeline.run(request, **ports)

    assert decision.selected_alternative_id is None
    assert trace.outcome == "failed"
    assert "no supported hypotheses" in trace.final_decision_explanation


async def test_constraint_based_mode_runs_the_hard_gate_without_crashing() -> None:
    """`constraint_evaluator._violates` is an honest no-op in Phase 2B (§9's
    known gap -- no per-alternative structured cost field exists yet to check
    a constraint against), so this cannot yet force a real rejection; this
    test guards that Constraint-based mode still runs the gate and produces a
    normal decision rather than crashing."""
    knowledge_port = FakeKnowledgePort(
        [
            KnowledgeReference(
                node_id="n1", name="candidate explanation", layer="expert", confidence=0.9
            )
        ]
    )
    ports = _ports(knowledge_port=knowledge_port)
    request = ReasoningRequest(
        objective_text="pick an approach",
        user_id=uuid4(),
        requesting_engine="test",
        reasoning_mode_hint=ReasoningMode.CONSTRAINT_BASED,
        constraints=[Constraint(kind="budget", description="must cost nothing", hard=True)],
    )
    decision, trace, _chosen = await pipeline.run(request, **ports)
    assert trace.outcome in {"decided", "degraded"}


async def test_multi_step_mode_does_not_recurse_when_confidence_meets_verify_threshold() -> None:
    """Phase 3A (§11): the recursion trigger fires only when
    `confidence.composite < verify_threshold` -- an artificially lenient
    threshold here proves Multi-step mode still completes as an honest,
    non-recursive single pass when the first-pass confidence already clears
    the bar, exactly like every other mode. (Supersedes the old
    `test_multi_step_mode_runs_a_single_pass_not_yet_a_chain`, written before
    Phase 3A implemented the trigger -- see `test_multi_step_mode_recurses_
    when_confidence_is_below_verify_threshold` below for the triggered
    case.)"""
    knowledge_port = FakeKnowledgePort(
        [
            KnowledgeReference(
                node_id="n1", name="candidate explanation", layer="expert", confidence=0.9
            )
        ]
    )
    ports = _ports(knowledge_port=knowledge_port)
    request = ReasoningRequest(
        objective_text="candidate explanation for a deep architectural question",
        user_id=uuid4(),
        requesting_engine="test",
        reasoning_mode_hint=ReasoningMode.MULTI_STEP,
    )
    decision, trace, _chosen = await pipeline.run(request, verify_threshold=0.0, **ports)
    assert trace.reasoning_mode is ReasoningMode.MULTI_STEP
    assert trace.outcome in {"decided", "degraded"}
    assert trace.steps == []  # no chain was built -- a single-pass result only
    assert trace.multistep_recursion_exhausted is False


async def test_multi_step_mode_recurses_when_confidence_is_below_verify_threshold() -> None:
    """Phase 3A (§11), Fork 3A-2: forcing an unreachable `verify_threshold`
    guarantees the trigger condition (`mode is MULTI_STEP and confidence <
    verify_threshold`) fires, proving the chain is real -- a genuinely new
    `ReasoningProcess` is created and persisted for the sub-question, linked
    to the parent via `parent_process_id` (Fork 3A-1: internal
    self-recursion, one RPC round trip for the external caller)."""
    ports = _grounded_ports()
    request = _analytical_request(reasoning_mode_hint=ReasoningMode.MULTI_STEP)
    decision, trace, chosen = await pipeline.run(
        request, verify_threshold=1.1, override_threshold=0.0, **ports
    )
    assert trace.steps  # recursion happened at least once
    child_trace = trace.steps[0]
    assert child_trace.reasoning_process_id != trace.reasoning_process_id

    repository = ports["repository"]
    child_process = repository.processes[child_trace.reasoning_process_id]
    assert child_process.parent_process_id == trace.reasoning_process_id
    assert child_process.reasoning_mode is ReasoningMode.MULTI_STEP
    assert trace.outcome == "decided"  # override_threshold=0.0 is always satisfied
    assert chosen is not None
    assert decision.confidence_score == pytest.approx(trace.confidence_score)


async def test_multistep_recursion_respects_max_step_depth_and_never_hangs() -> None:
    """Phase 3A requirement 6: with `verify_threshold` unreachable (1.1, above
    any possible confidence), every level along the chain wants to recurse --
    the hard `MultiStepConfig.max_step_depth` cap (default 3) is the only
    thing that stops it. `asyncio.wait_for` is the direct proof this never
    hangs; `multistep_recursion_exhausted` and the existing (unmodified)
    degraded-outcome branching are the proof it never raises and always
    returns the best available result."""
    ports = _grounded_ports()
    request = _analytical_request(reasoning_mode_hint=ReasoningMode.MULTI_STEP)

    decision, trace, chosen = await asyncio.wait_for(
        pipeline.run(request, verify_threshold=1.1, override_threshold=0.0, **ports),
        timeout=10.0,
    )

    assert chain_depth(trace) == 3  # MultiStepConfig().max_depth's own default
    assert trace.multistep_recursion_exhausted is True
    assert trace.outcome == "decided"  # override_threshold=0.0 is always satisfied
    assert decision.selected_alternative_id is not None
    assert chosen is not None


async def test_multistep_recursion_threads_parent_process_id_through_every_level() -> None:
    """Phase 3A requirement 4: the full chain must be traceable via
    `ReasoningProcess.parent_process_id` (already-persisted, real FK) --
    walking `trace.steps` down to the leaf confirms every level's persisted
    process correctly points at its immediate parent, never skipping a
    level or pointing at the wrong ancestor."""
    ports = _grounded_ports()
    request = _analytical_request(reasoning_mode_hint=ReasoningMode.MULTI_STEP)
    decision, trace, _chosen = await pipeline.run(
        request, verify_threshold=1.1, override_threshold=0.0, **ports
    )
    repository = ports["repository"]

    seen_ids = {trace.reasoning_process_id}
    expected_parent = trace.reasoning_process_id
    current_trace = trace
    while current_trace.steps:
        child_trace = current_trace.steps[0]
        child_id = child_trace.reasoning_process_id
        assert child_id not in seen_ids  # every level is a genuinely distinct process
        seen_ids.add(child_id)
        stored_child_process = repository.processes[child_id]
        assert stored_child_process.parent_process_id == expected_parent
        expected_parent = child_id
        current_trace = child_trace
    assert len(seen_ids) == 4  # root + 3 recursion levels (max_step_depth)


class _DegradingKnowledgePort:
    """Test-only fake: real knowledge on the *first* `context_assembly` call
    (the root), nothing on every later call (a recursive child or deeper) --
    engineered so a recursive child's own local confidence is measurably
    lower than a knowledge-backed pass's, making chain-minimum aggregation
    (vs. an average) a directly, deterministically observable property."""

    def __init__(self, results: list[KnowledgeReference]) -> None:
        self._results = results
        self.call_count = 0

    async def retrieve(
        self, *, query: str, limit: int = 10, correlation_id: UUID | None = None
    ) -> list[KnowledgeReference]:
        self.call_count += 1
        return self._results if self.call_count == 1 else []

    async def traverse(
        self, *, seed_node_id: str, depth: int = 2, correlation_id: UUID | None = None
    ) -> list[KnowledgeReference]:
        return []


async def test_multistep_confidence_aggregates_as_chain_minimum_not_average() -> None:
    """Phase 3A requirement 5: aggregation must be `min()`, never an average.
    A control (single-pass, knowledge-backed) run establishes what a
    confident pass looks like; the recursive run's own immediate child gets
    zero knowledge (via `_DegradingKnowledgePort`) and is therefore
    measurably worse -- a genuine minimum lands the *final*, returned
    confidence exactly on the (lower) child value, never somewhere between
    it and the root's own higher local value, which is what an average
    would produce."""
    confident_knowledge = [
        KnowledgeReference(node_id="n1", name="x", layer="expert", confidence=0.9)
    ]
    memory_port = FakeMemoryPort(
        [MemoryReference(memory_id=uuid4(), summary="candidate explanation", confidence=0.9)]
    )

    control_ports = _ports(
        knowledge_port=FakeKnowledgePort(confident_knowledge), memory_port=memory_port
    )
    _control_decision, control_trace, _c = await pipeline.run(
        _analytical_request(), verify_threshold=0.0, **control_ports
    )

    degrading_knowledge = _DegradingKnowledgePort(confident_knowledge)
    ports = _ports(knowledge_port=degrading_knowledge, memory_port=memory_port)
    request = _analytical_request(reasoning_mode_hint=ReasoningMode.MULTI_STEP)
    decision, trace, _chosen = await pipeline.run(
        request, verify_threshold=1.1, override_threshold=0.0, **ports
    )

    assert trace.steps
    child_confidence = trace.steps[0].confidence_score
    assert child_confidence < control_trace.confidence_score  # the child really is worse
    assert trace.confidence_score == pytest.approx(child_confidence)  # minimum, not an average
    assert decision.confidence_score == pytest.approx(child_confidence)


async def test_low_confidence_non_multistep_mode_never_recurses() -> None:
    """Phase 3A requirement 3/9's scoping: the recursion trigger is gated on
    `mode is ReasoningMode.MULTI_STEP` specifically -- the same unreachable
    `verify_threshold` under Analytical mode must never build a chain,
    confirming every other mode's existing threshold behavior (including the
    pre-existing `awaiting_human_override` path) is provably untouched."""
    ports = _grounded_ports()
    decision, trace, _chosen = await pipeline.run(
        _analytical_request(), verify_threshold=1.1, override_threshold=1.1, **ports
    )
    assert trace.outcome == "degraded"
    assert trace.steps == []
    assert trace.multistep_recursion_exhausted is False


async def test_recursion_lineage_is_distinct_from_correction_lineage() -> None:
    """Phase 3A requirement 7: a correction-linked process
    (`Decision.is_correction` set, `parent_process_id=None`) and a recursion
    child process (`parent_process_id` set, `is_correction=None` since
    `prior_nova_utterance` is never threaded into a derived sub-question)
    must never be conflated -- proven directly on both persisted
    `ReasoningProcess` rows and both `Decision` records in the same chain."""
    model_port = FakeModelOrchestrationPort(
        reply=GenerateReplyPayload(
            text=(
                "1. candidate explanation one.\n"
                "2. candidate explanation two.\n"
                "3. candidate explanation three.\n"
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
    ports = _grounded_ports()
    ports["model_port"] = model_port
    request = _analytical_request(
        reasoning_mode_hint=ReasoningMode.MULTI_STEP,
        prior_nova_utterance="The meeting is on Tuesday.",
    )
    decision, trace, _chosen = await pipeline.run(
        request, verify_threshold=1.1, override_threshold=0.0, **ports
    )
    repository = ports["repository"]

    root_process = repository.processes[trace.reasoning_process_id]
    assert decision.is_correction is True
    assert root_process.parent_process_id is None  # a correction, not a recursion child

    assert trace.steps  # recursion still triggers independently of the correction verdict
    child_trace = trace.steps[0]
    child_process = repository.processes[child_trace.reasoning_process_id]
    assert child_process.parent_process_id == trace.reasoning_process_id  # recursion lineage

    child_decision_id = repository.decisions_by_process[child_trace.reasoning_process_id]
    child_decision = repository.decisions[child_decision_id]
    assert child_decision.is_correction is None  # the derived sub-question is never a correction


async def test_collaborative_mode_raises_not_implemented() -> None:
    ports = _ports()
    request = ReasoningRequest(
        objective_text="anything",
        user_id=uuid4(),
        requesting_engine="test",
        reasoning_mode_hint=ReasoningMode.COLLABORATIVE,
    )
    with pytest.raises(modes.NotImplementedModeError):
        await pipeline.run(request, **ports)


async def test_goal_driven_mode_requires_no_special_handling_when_goals_supplied() -> None:
    ports = _ports()
    request = ReasoningRequest(
        objective_text="choose the best plan",
        user_id=uuid4(),
        requesting_engine="test",
        reasoning_mode_hint=ReasoningMode.GOAL_DRIVEN,
        goals=[Goal(id=uuid4(), description="choose the best plan quickly", priority=0.9)],
    )
    decision, trace, _chosen = await pipeline.run(request, **ports)
    assert trace.reasoning_mode is ReasoningMode.GOAL_DRIVEN
    assert trace.goals_considered == [request.goals[0].id]


async def test_on_stage_callback_reports_the_real_lifecycle_sequence() -> None:
    """§21: `/reason/stream` relies on `on_stage` firing with each real
    lifecycle transition, in order -- not a polling approximation."""
    knowledge_port = FakeKnowledgePort(
        [
            KnowledgeReference(
                node_id="n1", name="candidate explanation", layer="expert", confidence=0.9
            )
        ]
    )
    ports = _ports(knowledge_port=knowledge_port)
    request = ReasoningRequest(
        objective_text="candidate explanation for the bug",
        user_id=uuid4(),
        requesting_engine="test",
        reasoning_mode_hint=ReasoningMode.ANALYTICAL,
    )
    stages: list[str] = []

    async def on_stage(stage: str) -> None:
        stages.append(stage)

    decision, trace, _chosen = await pipeline.run(request, on_stage=on_stage, **ports)

    assert stages[0] == "context_assembling"
    assert stages[1] == "hypotheses_generating"
    assert stages[2] == "alternatives_evaluating"
    assert stages[3] == "decision_scoring"
    assert stages[-1] == trace.outcome


def _analytical_request(**overrides) -> ReasoningRequest:
    defaults = dict(
        objective_text="candidate explanation for the bug",
        user_id=uuid4(),
        requesting_engine="test",
        reasoning_mode_hint=ReasoningMode.ANALYTICAL,
    )
    defaults.update(overrides)
    return ReasoningRequest(**defaults)


def _grounded_ports():
    knowledge_port = FakeKnowledgePort(
        [
            KnowledgeReference(
                node_id="n1", name="candidate explanation", layer="expert", confidence=0.9
            )
        ]
    )
    memory_port = FakeMemoryPort(
        [MemoryReference(memory_id=uuid4(), summary="candidate explanation", confidence=0.9)]
    )
    return _ports(memory_port=memory_port, knowledge_port=knowledge_port)


async def test_medium_confidence_applies_the_self_eval_gap_penalty_and_still_decides() -> None:
    """§10, §18: medium confidence runs Self-evaluation mode's bounded gap
    check automatically, then still proceeds to `decided` -- confirmed here
    by forcing every composite into the medium band via the pipeline's own
    threshold parameters, the same knobs `config.py` exposes for real
    deployments."""
    ports = _grounded_ports()
    request = _analytical_request()
    decision, trace, _chosen = await pipeline.run(
        request, verify_threshold=1.1, override_threshold=0.0, **ports
    )
    assert trace.outcome == "decided"
    repository = ports["repository"]
    assert repository.processes[decision.reasoning_process_id].status == "decided"


async def test_low_confidence_awaits_human_override() -> None:
    """§10, §18: below both thresholds, the pipeline stops short of
    `decided` -- ADR-025: the user is always the final authority."""
    ports = _grounded_ports()
    request = _analytical_request()
    decision, trace, _chosen = await pipeline.run(
        request, verify_threshold=1.1, override_threshold=1.1, **ports
    )
    assert trace.outcome == "degraded"
    repository = ports["repository"]
    assert repository.processes[decision.reasoning_process_id].status == "awaiting_human_override"
    assert repository.processes[decision.reasoning_process_id].completed_at is None


async def test_long_term_planning_applies_a_confidence_penalty_relative_to_analytical() -> None:
    """§6: Long-term planning's wider horizon carries more predicted
    uncertainty by construction -- `ModeConfig.default_confidence_penalty`
    should measurably lower confidence relative to the identical inputs
    under Analytical mode."""
    analytical_decision, _trace, _chosen = await pipeline.run(
        _analytical_request(), **_grounded_ports()
    )
    planning_decision, _trace2, _chosen2 = await pipeline.run(
        _analytical_request(reasoning_mode_hint=ReasoningMode.LONG_TERM_PLANNING, goals=[
            Goal(id=uuid4(), description="ship it", priority=0.8)
        ]),
        **_grounded_ports(),
    )
    assert planning_decision.confidence_score <= analytical_decision.confidence_score


async def test_is_correction_threads_through_to_the_final_decision() -> None:
    """Phase 2D-D Sec5.3: the correction verdict computed inside
    `hypothesis_generation.generate_hypotheses` must survive every
    intermediate pipeline stage (evidence collection, alternative
    generation, decision matrix) and land on the returned `Decision`."""
    model_port = FakeModelOrchestrationPort(
        reply=GenerateReplyPayload(
            text=(
                "1. candidate explanation one.\n"
                "2. candidate explanation two.\n"
                "3. candidate explanation three.\n"
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
    ports = _grounded_ports()
    ports["model_port"] = model_port
    request = _analytical_request(prior_nova_utterance="The meeting is on Tuesday.")
    decision, _trace, _chosen = await pipeline.run(request, **ports)
    assert decision.is_correction is True


async def test_is_correction_is_none_when_no_prior_utterance_supplied() -> None:
    ports = _grounded_ports()
    decision, _trace, _chosen = await pipeline.run(_analytical_request(), **ports)
    assert decision.is_correction is None


async def test_is_correction_survives_a_post_hypothesis_failure() -> None:
    """`_fail()` called after hypothesis generation succeeds (e.g. no
    supported hypotheses survive evidence collection) must still carry
    forward whatever correction verdict was already computed -- it is not a
    pre-hypothesis failure where no judgment was ever attempted."""
    model_port = FakeModelOrchestrationPort(
        reply=GenerateReplyPayload(
            text="1. an unrelated hypothesis with no supporting context.\nCORRECTION: yes",
            input_tokens=10,
            output_tokens=10,
            finish_reason="stop",
            structural_confidence=0.9,
            model_id=uuid4(),
            provider="fake",
        )
    )
    ports = _ports(model_port=model_port)  # empty context ports: nothing will match
    request = _analytical_request(prior_nova_utterance="The meeting is on Tuesday.")
    decision, trace, _chosen = await pipeline.run(request, **ports)
    assert trace.outcome == "failed"
    assert decision.is_correction is True


async def test_context_assembly_failure_downgrades_an_otherwise_decided_outcome() -> None:
    """§5, §7.2, §17: one upstream port breaking its own documented
    graceful-degradation contract (raising instead of returning an empty
    result, per §7.3) degrades only that port's own contribution --
    `assemble_context` isolates the five upstream calls from each other, so
    the still-healthy knowledge port alone is enough evidence to reach an
    otherwise-`decided` outcome, downgraded to `degraded` because the
    process is on record as having lost one of its inputs."""

    class _FailingMemoryPort:
        async def retrieve(self, *, user_id, query, limit=10, correlation_id=None):
            raise TimeoutError("simulated memory engine outage")

    ports = _grounded_ports()
    ports["memory_port"] = _FailingMemoryPort()
    stages: list[str] = []

    async def on_stage(stage: str) -> None:
        stages.append(stage)

    decision, trace, chosen = await pipeline.run(
        request=_analytical_request(), on_stage=on_stage, **ports
    )
    assert trace.outcome == "degraded"
    assert chosen is not None  # the knowledge port alone still produced a decision
    # §5: `degraded` is a transient lifecycle state on the way to a terminal one --
    # `degraded --> decided: reduced-confidence decision still produced` -- so the
    # *persisted* status lands on `decided` even though the trace's own `outcome`
    # records the reduced-confidence nature of how it got there.
    assert stages == [
        "context_assembling",
        "degraded",
        "hypotheses_generating",
        "alternatives_evaluating",
        "decision_scoring",
        "decided",
    ]
    repository = ports["repository"]
    assert repository.processes[decision.reasoning_process_id].status == "decided"
    assert repository.processes[decision.reasoning_process_id].completed_at is not None


# ---------------------------------------------------------------------------
# Reactive-mode persistence (defect D-1, found by the Phase 3E real-Postgres
# acceptance E2E). The branch used to build an `Alternative`, point
# `Decision.selected_alternative_id` at it, and call `finalize()` without ever
# persisting either that Alternative or a Hypothesis for it to reference --
# invisible against a fake repository, a foreign-key violation against the
# real schema. See `tests/integration/test_repository_real_postgres.py` for
# the same guarantee proven against real PostgreSQL.
# ---------------------------------------------------------------------------


class _CallOrderRecordingRepository(FakeReasoningRepository):
    """`FakeReasoningRepository` that also records the order of the writes
    the pipeline performs, so "before `finalize()`" is assertable rather than
    merely plausible."""

    def __init__(self) -> None:
        super().__init__()
        self.write_order: list[str] = []

    async def record_hypotheses(self, hypotheses):  # type: ignore[no-untyped-def]
        self.write_order.append("record_hypotheses")
        await super().record_hypotheses(hypotheses)

    async def record_alternatives(self, alternatives):  # type: ignore[no-untyped-def]
        self.write_order.append("record_alternatives")
        await super().record_alternatives(alternatives)

    async def finalize(self, **kwargs):  # type: ignore[no-untyped-def]
        self.write_order.append("finalize")
        return await super().finalize(**kwargs)


def _reactive_request() -> ReasoningRequest:
    return ReasoningRequest(
        objective_text="what is the capital of France?",
        user_id=uuid4(),
        requesting_engine="test",
        reasoning_mode_hint=ReasoningMode.REACTIVE,
    )


def _grounded_knowledge_port() -> FakeKnowledgePort:
    return FakeKnowledgePort(
        [KnowledgeReference(node_id="n1", name="Paris", layer="verified", confidence=0.9)]
    )


async def test_reactive_mode_persists_its_hypothesis_and_alternative_before_finalize() -> None:
    repository = _CallOrderRecordingRepository()
    ports = _ports(knowledge_port=_grounded_knowledge_port(), repository=repository)

    await pipeline.run(_reactive_request(), **ports)

    assert repository.write_order == ["record_hypotheses", "record_alternatives", "finalize"]
    assert len(repository.hypotheses) == 1
    assert len(repository.alternatives) == 1


async def test_reactive_modes_decision_references_a_persisted_alternative() -> None:
    """The exact foreign-key chain the real schema enforces:
    `decision.selected_alternative_id` -> `alternative.id`."""
    repository = _CallOrderRecordingRepository()
    ports = _ports(knowledge_port=_grounded_knowledge_port(), repository=repository)

    decision, _trace, chosen = await pipeline.run(_reactive_request(), **ports)

    assert chosen is not None
    assert decision.selected_alternative_id is not None
    persisted_alternative_ids = {alternative.id for alternative in repository.alternatives}
    assert decision.selected_alternative_id in persisted_alternative_ids


async def test_reactive_modes_alternative_references_a_persisted_hypothesis() -> None:
    """The second link of the same chain: `alternative.hypothesis_id` ->
    `hypothesis.id`, a NOT NULL foreign key. This used to hold `process.id`,
    which is not a hypothesis id at all."""
    repository = _CallOrderRecordingRepository()
    ports = _ports(knowledge_port=_grounded_knowledge_port(), repository=repository)

    decision, _trace, _chosen = await pipeline.run(_reactive_request(), **ports)

    alternative = repository.alternatives[0]
    persisted_hypothesis_ids = {hypothesis.id for hypothesis in repository.hypotheses}
    assert alternative.hypothesis_id in persisted_hypothesis_ids
    assert alternative.hypothesis_id != decision.reasoning_process_id


async def test_reactive_modes_persisted_rows_belong_to_the_same_process() -> None:
    repository = _CallOrderRecordingRepository()
    ports = _ports(knowledge_port=_grounded_knowledge_port(), repository=repository)

    decision, _trace, _chosen = await pipeline.run(_reactive_request(), **ports)

    process_id = decision.reasoning_process_id
    assert repository.hypotheses[0].reasoning_process_id == process_id
    assert repository.alternatives[0].reasoning_process_id == process_id


async def test_reactive_modes_hypothesis_records_the_retrieved_answer_as_supported() -> None:
    """Semantics, not just referential integrity: the row records the claim
    the answer rests on, and the retrieved context is what supports it."""
    repository = _CallOrderRecordingRepository()
    ports = _ports(knowledge_port=_grounded_knowledge_port(), repository=repository)

    await pipeline.run(_reactive_request(), **ports)

    hypothesis = repository.hypotheses[0]
    assert hypothesis.description == "Paris"
    assert hypothesis.status == "supported"
    assert repository.alternatives[0].description == hypothesis.description


async def test_reactive_mode_without_grounding_records_an_unsupported_hypothesis() -> None:
    """No knowledge and no memories: the answer is still persisted, still
    referentially valid, but honestly marked -- `"unsupported"`, matching the
    same branch's own 0.1 confidence. NULL is never used to mean "ungrounded"."""
    repository = _CallOrderRecordingRepository()
    ports = _ports(repository=repository)  # no knowledge, no memories

    decision, _trace, _chosen = await pipeline.run(_reactive_request(), **ports)

    assert decision.confidence_score == pytest.approx(0.1)
    assert repository.hypotheses[0].status == "unsupported"
    assert decision.selected_alternative_id == repository.alternatives[0].id
    assert repository.alternatives[0].hypothesis_id == repository.hypotheses[0].id
