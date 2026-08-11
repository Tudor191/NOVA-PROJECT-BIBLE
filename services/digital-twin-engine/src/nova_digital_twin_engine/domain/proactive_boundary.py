"""Proactive suggestion boundary policy (docs/design/phase-2d/
06-personal-companion.md Sec10.1, Fork D) -- "A pure function, no side
effects: given a proposed proactive message (content, topic tag) and the
user's configured boundary policy (frequency limit per topic, per time
window; enabled/disabled), returns allow/deny. This is the only genuinely
new logic this feature needs -- everything downstream of "allowed" reuses
existing infrastructure."

A topic with no configured limit is **declined, not allowed** -- the same
"no signal is better than a wrong one" discipline
`conversation_orchestration.maybe_activate_listening` already applies when
zero or multiple eligible sessions make the right answer ambiguous (Doc 22
Principle 6): an unconfigured topic is a boundary the user has not yet set,
not evidence that no boundary is wanted.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from nova_digital_twin_engine.domain.models import (
    ProactiveBoundaryPolicy,
    ProactiveDeliveryRecord,
    ProactiveSuggestion,
    ProactiveSuggestionDecision,
)

__all__ = ["evaluate_proactive_suggestion"]


def evaluate_proactive_suggestion(
    *,
    policy: ProactiveBoundaryPolicy,
    suggestion: ProactiveSuggestion,
    recent_deliveries: list[ProactiveDeliveryRecord],
    now: datetime,
) -> ProactiveSuggestionDecision:
    if not policy.enabled:
        return ProactiveSuggestionDecision(
            allowed=False, reason="proactive suggestions are disabled for this user"
        )

    limit = policy.max_per_topic_per_window.get(suggestion.topic)
    if limit is None:
        return ProactiveSuggestionDecision(
            allowed=False,
            reason=(
                f"no configured frequency limit for topic {suggestion.topic!r}; "
                "declining rather than guessing one"
            ),
        )

    window_start = now - timedelta(hours=policy.window_hours)
    recent_count = sum(
        1
        for delivery in recent_deliveries
        if delivery.topic == suggestion.topic and delivery.delivered_at >= window_start
    )
    if recent_count >= limit:
        return ProactiveSuggestionDecision(
            allowed=False,
            reason=(
                f"{recent_count} of {limit} allowed deliveries for topic "
                f"{suggestion.topic!r} already sent in the last {policy.window_hours}h"
            ),
        )

    return ProactiveSuggestionDecision(
        allowed=True,
        reason=(
            f"{recent_count} of {limit} allowed deliveries for topic "
            f"{suggestion.topic!r} sent in the last {policy.window_hours}h"
        ),
    )
