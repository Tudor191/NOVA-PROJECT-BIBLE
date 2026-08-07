"""Every subject Perception Engine is permitted to publish -- docs/design/
phase-2d/03-perception-engine.md Sec13.2. See ADR-004
(docs/architecture/00-overview-and-decisions.md).

`perception.presence.observed` / `perception.identity.observed` /
`perception.attention.observed` deliberately match World Model Engine's
existing `perception.*.observed` wildcard subscription (Sec0.6) -- they feed
`ActiveContext` via that engine's now-wired `fuse_and_update`/
`upsert_present_identity`/`clear_present_identities` paths.

`perception.wake.detected` and `perception.addressee_signal.candidate`
deliberately do NOT match that wildcard (they end in `detected`/`candidate`,
not `observed`) -- discrete trigger events and per-utterance candidate
signals, never "current state of reality" facts, so they are never routed
into World Model's object/context pipelines. Both are consumed directly by
`communication-engine`'s future 2D-C addressee fusion (Sec0.7, Sec10);
Sec20's own test suite verifies this subject-naming distinction mechanically,
not just by convention.

The four `ai_model.*.request` subjects are this engine's own outbound RPC
calls (Sec0.2, `clients/ai_model_orchestration_client.py`) -- `BoundEventBus.
request()` checks the *publishable* allow-list even though the subject
grammatically looks like something this engine "receives a reply to," the
same convention every prior client engine's own `events/published.py`
follows (`communication-engine`'s own `ai_model.transcribe.request`/
`ai_model.synthesize.request` entries, `executive-cognition-engine`'s README).
"""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "perception.presence.observed",
        "perception.identity.observed",
        "perception.attention.observed",
        "perception.wake.detected",
        "perception.addressee_signal.candidate",
        "perception.consent.changed",
        "perception.sensor.health_changed",
        "ai_model.detect_wake_phrase.request",
        "ai_model.embed_voice.request",
        "ai_model.embed_face.request",
        "ai_model.estimate_gaze.request",
    }
)
