"""The Prompt Pipeline / Context Builder (Bible Part 7 "Prompt Orchestration",
"Model Memory Limits"; docs/design/phase-2a/00-ai-model-orchestration-engine.md
§0). Fits already-assembled, named context components into a target model's
token budget -- this module never decides what's relevant, never calls Memory,
Knowledge, World Model, or Personality Engine. It produces a provider-agnostic,
ordered list of surviving components; each `connectors/*.py` implementation
formats that list into its own wire shape (message-role array, single string,
etc.) -- formatting-per-provider is a connector concern, fitting-within-budget is
this module's.
"""

from __future__ import annotations

from nova_ai_model_orchestration_engine.domain.models import ContextComponent

__all__ = ["AssembledContext", "fit_to_budget"]

# Reserve headroom for the model's own output plus a safety margin for tokenizer
# estimation error (this engine's `token_estimate` is a caller-supplied estimate,
# not an exact provider-specific tokenizer count -- Part 7's "avoid unnecessary
# token consumption" is served by leaving slack, not by pretending the estimate
# is exact).
_SAFETY_MARGIN_TOKENS = 64


class AssembledContext:
    __slots__ = ("components", "total_tokens", "dropped_sources")

    def __init__(
        self,
        components: list[ContextComponent],
        *,
        total_tokens: int,
        dropped_sources: list[str],
    ) -> None:
        self.components = components
        self.total_tokens = total_tokens
        self.dropped_sources = dropped_sources


def fit_to_budget(
    components: list[ContextComponent],
    *,
    context_window: int,
    max_output_tokens: int,
) -> AssembledContext:
    """Orders components by `priority` (descending; ties keep input order --
    stable, deterministic, per ADR-021's determinism standard applied here too),
    then keeps as many as fit within `context_window - max_output_tokens -
    safety_margin`. A component whose `truncation_policy` is `"drop"` is either
    included whole or not at all; `"truncate_end"` (and, today, `"summarize_external"`
    -- see the note below) is cut to whatever budget remains rather than dropped
    entirely, so partial context beats no context.

    `"summarize_external"` is accepted but **not yet implemented as real
    summarization** -- it behaves identically to `"truncate_end"` today. Building
    real summarization would mean this engine calling a model on its own
    initiative to compress another component, which is exactly the kind of
    scope creep the independence boundary (design doc §0) and the
    evidence-driven-optimization standard both argue against without a concrete
    caller that actually needs it yet. Documented here and in the README's Known
    Limitations, not silently passed through as if it worked."""
    budget = context_window - max_output_tokens - _SAFETY_MARGIN_TOKENS
    ordered = sorted(enumerate(components), key=lambda pair: (-pair[1].priority, pair[0]))

    kept: list[ContextComponent] = []
    dropped: list[str] = []
    remaining = max(budget, 0)
    kept_with_index: list[tuple[int, ContextComponent]] = []

    for original_index, component in ordered:
        if component.token_estimate <= remaining:
            kept_with_index.append((original_index, component))
            remaining -= component.token_estimate
            continue

        if component.truncation_policy == "drop" or remaining <= 0:
            dropped.append(component.source)
            continue

        # truncate_end / summarize_external (today, identical behavior -- see above)
        keep_fraction = remaining / component.token_estimate
        cut_at = max(int(len(component.text) * keep_fraction), 0)
        if cut_at == 0:
            dropped.append(component.source)
            continue
        truncated = component.model_copy(
            update={"text": component.text[:cut_at], "token_estimate": remaining}
        )
        kept_with_index.append((original_index, truncated))
        remaining = 0

    # Priority only controlled *which* components survive; restore original
    # relative order (by input position, not by `source`, which callers are free
    # to repeat) for the surviving ones.
    kept_with_index.sort(key=lambda pair: pair[0])
    kept = [component for _, component in kept_with_index]

    return AssembledContext(
        kept, total_tokens=sum(c.token_estimate for c in kept), dropped_sources=dropped
    )
