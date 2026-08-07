"""Every subject AI Model Orchestration Engine is permitted to subscribe to --
docs/design/phase-2a/00-ai-model-orchestration-engine.md §13.

`ai_model.generate.request` / `ai_model.embed.request` are here, not
`published.py`: `BoundEventBus.serve()` checks the *subscribable* allow-list,
matching `subscribe()`'s convention (same as World Model Engine's own
`events/subscribed.py`, where `world_model.context.request` lives here for the
identical reason).

`ai_model.transcribe.request` / `ai_model.synthesize.request` added per
docs/design/phase-2d/01-communication-engine.md §0.3 -- `communication-engine`'s
first real event-driven caller of the speech modalities, served the same way
generate/embed already are.

`ai_model.detect_wake_phrase.request` / `ai_model.embed_voice.request` /
`ai_model.embed_face.request` / `ai_model.estimate_gaze.request` added per
docs/design/phase-2d/03-perception-engine.md §0.2 -- `perception-engine`'s
first real event-driven caller of the biometric/wake-signal modalities, served
the same way transcribe/synthesize already are.

Per §13, this engine has no *subscribed* subject (in the "reacts to another
engine's event" sense) -- every entry below is a served RPC, not a reaction to
an upstream producer.
"""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "ai_model.generate.request",
        "ai_model.embed.request",
        "ai_model.transcribe.request",
        "ai_model.synthesize.request",
        "ai_model.detect_wake_phrase.request",
        "ai_model.embed_voice.request",
        "ai_model.embed_face.request",
        "ai_model.estimate_gaze.request",
    }
)
