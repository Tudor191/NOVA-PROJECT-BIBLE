"""Bible Part 7 "Cost Management" -- per-request cost estimation and budget
threshold evaluation. Pure arithmetic over already-known token counts and a
model's registered per-token pricing; no I/O (persistence is
`UsageRepository`'s job, called from `domain/router.py` after a request
completes).
"""

from __future__ import annotations

from nova_ai_model_orchestration_engine.domain.models import Budget, ModelDescriptor

__all__ = ["budget_status", "estimate_cost"]


def estimate_cost(model: ModelDescriptor, *, input_tokens: int, output_tokens: int) -> float:
    """Local models have no per-token price (`cost_per_*_token` is `None`) --
    their cost is definitionally `0.0`, not "unknown"; Part 7's "if no budget
    exists, prefer local execution" only makes sense if local execution's cost is
    a real, comparable zero, not a missing value the router would have to guess
    at."""
    input_cost = (model.cost_per_input_token or 0.0) * input_tokens
    output_cost = (model.cost_per_output_token or 0.0) * output_tokens
    return input_cost + output_cost


def budget_status(budget: Budget, *, current_spend: float) -> tuple[bool, bool]:
    """Returns `(over_alert_threshold, over_limit)`. A caller (the router) uses
    `over_limit` to decide whether to restrict routing to zero-cost (local)
    candidates only (Part 7: "if no budget exists, prefer local execution" --
    applied here to "budget exhausted" too, since the practical effect is the
    same: don't spend past what's allowed)."""
    alert_amount = budget.limit_amount * (budget.alert_threshold_pct / 100)
    return (current_spend >= alert_amount, current_spend >= budget.limit_amount)
