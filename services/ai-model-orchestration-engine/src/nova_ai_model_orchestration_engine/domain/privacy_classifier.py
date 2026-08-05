"""Bible Part 7 "Privacy Management" -- classifies (or, more often, simply
carries forward) a request's privacy tier, since this engine holds no context of
its own to classify *from* (ADR-022: stateless gateway). The caller supplies a
`privacy_hint`; this module's job is to make that hint an unambiguous, validated
`PrivacyLevel`, never to infer sensitivity from content this engine was never
meant to inspect.
"""

from __future__ import annotations

from nova_ai_model_orchestration_engine.domain.models import GenerateRequest, PrivacyLevel

__all__ = ["classify"]


def classify(request: GenerateRequest) -> PrivacyLevel:
    """Returns `request.privacy_hint` as-is. A thin function today, not a
    trivial one to remove: it is the single place every downstream routing
    decision reads the privacy tier from, so a future need to layer additional
    policy on top of the caller's hint (e.g. a hard floor enforced by
    configuration) has exactly one call site to change."""
    return request.privacy_hint
