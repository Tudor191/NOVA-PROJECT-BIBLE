from typing import Literal

from nova_ai_model_orchestration_engine.domain import context_builder
from nova_ai_model_orchestration_engine.domain.models import ContextComponent

TruncationPolicy = Literal["drop", "truncate_end", "summarize_external"]


def _component(
    source: str,
    tokens: int,
    *,
    priority: int = 0,
    policy: TruncationPolicy = "truncate_end",
) -> ContextComponent:
    return ContextComponent(
        source=source,
        text="x" * tokens,
        token_estimate=tokens,
        priority=priority,
        truncation_policy=policy,
    )


def test_all_components_fit_within_budget() -> None:
    components = [_component("memory", 100), _component("knowledge", 100)]
    result = context_builder.fit_to_budget(components, context_window=8192, max_output_tokens=2048)
    assert result.total_tokens == 200
    assert result.dropped_sources == []
    assert [c.source for c in result.components] == ["memory", "knowledge"]


def test_lower_priority_dropped_first_when_over_budget() -> None:
    # budget = 500 - 100 - 64 = 336
    low = _component("world_model", 300, priority=0, policy="drop")
    high = _component("system_identity", 300, priority=10, policy="drop")
    result = context_builder.fit_to_budget([low, high], context_window=500, max_output_tokens=100)
    assert [c.source for c in result.components] == ["system_identity"]
    assert result.dropped_sources == ["world_model"]


def test_truncate_end_shrinks_rather_than_drops() -> None:
    component = _component("memory", 1000, policy="truncate_end")
    result = context_builder.fit_to_budget([component], context_window=600, max_output_tokens=100)
    # budget = 600 - 100 - 64 = 436
    assert result.dropped_sources == []
    assert result.components[0].token_estimate == 436
    assert len(result.components[0].text) < 1000


def test_original_order_preserved_among_survivors() -> None:
    a = _component("a", 50, priority=1)
    b = _component("b", 50, priority=5)
    c = _component("c", 50, priority=3)
    result = context_builder.fit_to_budget([a, b, c], context_window=8192, max_output_tokens=0)
    assert [comp.source for comp in result.components] == ["a", "b", "c"]


def test_drop_policy_excludes_entirely_when_no_room() -> None:
    filler = _component("system_identity", 400, priority=10, policy="drop")
    dropped = _component("memory", 300, priority=0, policy="drop")
    result = context_builder.fit_to_budget(
        [filler, dropped], context_window=500, max_output_tokens=36
    )
    # budget = 500 - 36 - 64 = 400 -- exactly fits filler, nothing left for dropped
    assert result.dropped_sources == ["memory"]
