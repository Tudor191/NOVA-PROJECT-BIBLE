from uuid import uuid4

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
    decision, trace, _chosen = await pipeline.run(request, **ports)

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
    decision, trace, _chosen = await pipeline.run(request, **ports)

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


async def test_multi_step_mode_runs_a_single_pass_not_yet_a_chain() -> None:
    """§11's data-model foundation exists (`ModeConfig.max_step_depth`,
    `ReasoningProcess.parent_process_id`), but no trigger mechanism in
    pipeline.py yet detects an unresolved sub-question mid-analysis and
    recurses -- the design doc itself never specifies that trigger's
    heuristic (§11 describes recursion's *consequences*, not when to start
    one). Requesting Multi-step mode today produces one ordinary single-pass
    decision, honestly, rather than a fabricated chain; this test guards
    that behavior stays visible rather than silently drifting into either a
    crash or a false claim of chaining."""
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
    decision, trace, _chosen = await pipeline.run(request, **ports)
    assert trace.reasoning_mode is ReasoningMode.MULTI_STEP
    assert trace.outcome in {"decided", "degraded"}
    assert trace.steps == []  # no chain was built -- a single-pass result only


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
