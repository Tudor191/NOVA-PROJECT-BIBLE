# Phase 2D-A Technical Design — 02: Personality Engine

Implements [Bible Part 17](../../bible/part-17-personality-engine.md), per the
[Phase 2D Master Architectural Blueprint](00-master-blueprint.md) §4.1 (Phase
2D-A). This document's entire purpose is to make
[Doc 23 — NOVA Personality Specification](../../architecture/23-nova-personality-specification.md)
*buildable* — every technical decision below traces to a specific Doc 23 section,
and §15 maps them explicitly. Doc 23 defines who NOVA is; this document defines how
that identity is enforced in running code, deterministically, on every response
[01-communication-engine.md](01-communication-engine.md) delivers.

Status: **Approved. Implemented and Gate-Reviewed (Go), approved by the user.**
`personality-engine` is now built at production-grade per this design package,
with the
[Architecture Review Report](../../roadmap/architecture-reviews/phase-2d-a-voice-communication-foundation.md)
and the formal
[Phase 2D-A Gate Review](../../roadmap/architecture-reviews/phase-2d-a-gate-review.md)
filed.

## 0. The boundary this document defends

### 0.1 This engine implements Doc 23; it does not redefine it

Nothing in this document introduces a new personality trait, value, or ethical
constraint. Doc 23 is the source of truth; where this document lists "constant
traits" or "forbidden behaviors," it is restating Doc 23 §2/§6 in a form a
validator can check against, never inventing new content. If a future
implementation need ever seems to require a personality decision Doc 23 doesn't
already answer, that is a Doc 23 amendment (a conversation with the user, per its
own closing section), never something decided inside this engine's code.

### 0.2 The Personality/Digital-Twin boundary — this engine stores and applies, never learns

Per Master Blueprint §9.2 and Doc 23 §7: `digital-twin-engine` (Phase 2D-D, not
yet built) is the epistemic learner — it detects a preference from accumulated
evidence and tracks its confidence and history. `personality-engine` **stores the
current resolved value and applies it as an expression constraint** — it never
observes user behavior, never accumulates evidence, and contains no learning loop
of any kind. This is a hard boundary, not a simplification: if this engine ever
grows logic that says "the user seems to prefer X, let me adjust," that logic has
silently become `digital-twin-engine`'s job, mis-implemented in the wrong service,
recreating exactly the undifferentiated preferences blob Master Blueprint Risk
§11.5 warns against. §6 below shows precisely where "resolved preference" values
come from this phase (a static default, since `digital-twin-engine` doesn't exist
yet) versus where they'll come from once Phase 2D-D ships.

### 0.3 ADR-020 compliance: this engine calls no model, by construction

Mirroring `executive-cognition-engine`'s own precedent (Phase 2C §0.2: "this
engine calls no model and stores almost nothing"), `personality-engine`'s
consistency validation and style selection are **rule-based and deterministic**,
never a model call. This is a deliberate design choice, not a temporary
simplification: semantic *correctness* of content is Reasoning Engine's
responsibility (Phase 2B), already discharged before content ever reaches this
engine. This engine's job is narrower — checking that phrasing, tone, and
confidence-language markers are consistent with Doc 23's fixed traits, values, and
forbidden-behavior list (§4) — a structural check, not a judgment call requiring
intelligence. Being rule-based also makes this engine fast enough to sit in
`communication-engine`'s synchronous response path (Master Blueprint Risk §11.1)
without becoming the latency bottleneck a model call would introduce, and makes
its behavior exactly as consistent as Doc 23 §8 (Trust) requires — a rule either
fires the same way every time, or it is not doing its job.

## 1. Overall architecture

```
                    ┌───────────────────────────────────────┐
                    │            personality-engine            │
                    │                                            │
communication-engine│  personality.validate_response RPC (§7)   │
  (§8.3 of that doc)│         │                                  │
        ────────────┼────────▶│                                  │
                    │         ▼                                  │
                    │  Core Identity & Values (§3, static config) │
                    │         │                                  │
                    │         ▼                                  │
                    │  Consistency Validator (§4, rule-based)      │
                    │         │                                  │
                    │         ▼                                  │
                    │  Style Selector (§5, deterministic rules)    │
                    │         │                                  │
                    │         ▼                                  │
                    │  Personality Memory (§6, resolved values —   │
                    │  static defaults this phase, §0.2)           │
                    │         │                                  │
        ◀───────────┼─────────┘  (validated/styled response)     │
                    └───────────────────────────────────────┘
```

Three internal components: **Core Identity Store** (§3), **Consistency Validator**
(§4), **Style Selector** (§5) — each stateless computation over the small,
mostly-static state in §9's schema (per Master Blueprint §8's classification:
"stateful, but narrowly").

## 2. Responsibilities of every component

| Component | Owns | Never does |
|---|---|---|
| Core Identity Store | The fixed traits/values/ethical constraints (Doc 23 §2, §6), versioned config | Learning, adaptation, content generation |
| Consistency Validator | Structural checks against forbidden patterns and confidence-language rules (§4) | Judging factual/semantic correctness (Reasoning Engine's job) |
| Style Selector | Mapping context → style palette entry (§5) | Learning user preference (`digital-twin-engine`'s job, §0.2) |
| Personality Memory | Current resolved expression settings (§6) | Detecting or evidencing preferences |

## 3. Core Identity & Fundamental Values — data model

A single, versioned configuration record — not a database of "personality
decisions," because there is exactly one NOVA (Doc 23 §1) and its core identity
does not vary per user, per session, or per deployment:

```python
class CoreIdentity(BaseModel):
    schema_version: int = 1
    traits: list[str]           # Doc 23 §2's twelve, fixed: calm, professional,
                                 # respectful, curious, reliable, patient,
                                 # confident, analytical, honest, supportive,
                                 # focused, consistent
    values: list[str]           # Doc 23 §2's eight, ordered, "Trust Before
                                 # Intelligence" first per the standing directive
    forbidden_behaviors: list[str]  # Doc 23 §6, used by §4's validator
    version_note: str           # human-readable, for the audit trail (§4)
```

This record changes only when Doc 23 itself is amended (its own closing section:
"a dated amendment," never a quiet exception) — never through this engine's own
runtime logic, and never per-user.

## 4. Consistency Validator

Structural, deterministic checks — no model call (§0.3). Four check families,
each traceable to a specific Doc 23 section:

1. **Confidence-language consistency** (Doc 23 §5.2, §2's Trust Before
   Intelligence directive). Cross-checks the caller-supplied confidence tier
   (High/Medium/Low/Unknown — this engine trusts the tier as given by the
   content-producing engine, the same epistemic-deference pattern ADR-028
   established for Executive Cognition; it does not re-derive confidence) against
   phrasing markers: a `Low`/`Unknown` tier paired with unhedged, declarative
   phrasing ("This is definitely...") fails validation and is returned with a
   hedging correction applied. A `High` tier is never *downgraded* in phrasing —
   only overclaiming is corrected, never underclaiming, since underclaiming never
   violates Trust Before Intelligence.
2. **Forbidden-pattern matching** (Doc 23 §6): a maintained pattern set for the
   named forbidden behaviors expressible as text patterns — manufactured urgency
   phrasing, guilt-inducing phrasing, fabricated shared-feeling claims ("I
   understand how you feel," per Doc 23 §4.6's explicit example). A match fails
   validation; the response is not delivered as-is (§8's failure handling
   specifies what happens next — this is a hard stop, not a soft warning, for
   this category).
3. **Emotional Stability markers** (Doc 23 §4.6's standing directive):
   sarcasm/defensiveness pattern detection (e.g., dismissive framing of a
   correction) — same hard-stop treatment as (2).
4. **Style-register consistency** (Doc 23 §9 Professionalism floor): flags
   responses that fall outside the professionalism floor regardless of selected
   style (§5) — e.g. content that would be inappropriate even for "Creative" or
   "Friendly" register.

**Validator output:** `ValidationResult { passed: bool, adjusted_content:
str | None, violations: list[ViolationRecord] }`. A `ViolationRecord` captures
which check family fired and why, written to the audit trail (§9) — Doc 23 §8's
Trust model depends on this being inspectable, not a black box, mirroring
Executive Cognition's own Explainability requirement (Phase 2C §16) applied here.

## 5. Style Selector

Bible Part 13's nine-style palette (professional, educational, technical,
friendly, executive, creative, minimal, analytical, emergency), selected this
phase by a **deterministic rule table** keyed on caller-supplied context hints
(channel, an optional `situation_hint` the content-producing engine may attach to
its `communication.intent` event — e.g. `"debugging"`, `"learning_session"`) with
`professional` as the default when no hint is supplied. This is intentionally the
simplest possible correct implementation — Master Blueprint §4.3 assigns *adaptive*
style selection (learned from context, tone-matching the user's own emotional
state per Doc 23 §4.6) to Phase 2D-C, which will extend this same
`personality-engine` service (§17) with richer selection logic, not replace this
table.

Every style output still passes through §4's validator — no style, however
selected, may violate the Professionalism floor (Doc 23 §9) or any forbidden
behavior (Doc 23 §6).

## 6. Personality Memory — resolved expression settings

Per §0.2, this is a **read-only-from-this-engine's-own-perspective** store of
resolved values (verbosity, technical depth, terminology preference — Doc 23 §2's
"adaptive" column): populated by `digital-twin-engine` once Phase 2D-D exists, via
`personality.memory.update` (an inbound event this engine subscribes to, §10).
**Until Phase 2D-D ships, this table contains exactly one row — a static,
config-defined default profile** (moderate verbosity, moderate technical depth) —
never a fabricated "learned" value (Doc 23 §6: inventing facts, including
invented preferences, is forbidden). This mirrors `communication-engine`'s own
§0.6 pattern of defining a port for a not-yet-built dependency rather than
building a speculative integration.

## 7. Interaction with other engines

### 7.1 `communication-engine` (server side)

Serves two RPCs, both consumed by `communication-engine`'s intent gate
([01-communication-engine.md §7-8.3](01-communication-engine.md)):

- `personality.validate_response` — runs §4's validator, returns
  `ValidationResult`.
- `personality.style.select` — runs §5's selector, returns the chosen style and
  the current Personality Memory profile (§6) for the caller to apply to
  generation parameters (e.g. requested response length).

### 7.2 `digital-twin-engine` (deferred, consumer relationship inverted once it exists)

This phase, no integration exists (§6). Once Phase 2D-D ships,
`digital-twin-engine` becomes a **publisher** into this engine (§10's
`personality.memory.update`) — the dependency direction is Digital Twin → 
Personality, never the reverse, preserving §0.2's boundary structurally: this
engine cannot query Digital Twin for "what does the user prefer," it can only
receive already-resolved values Digital Twin chooses to publish.

## 8. Failure handling

| Failure | Behavior |
|---|---|
| Validator finds a hard-stop violation (§4.2/4.3) | Response is **not delivered as originally supplied**; `communication-engine` receives `passed: false` and must not deliver the content unmodified — per §9's audit record, this is logged as a caught violation, never silently passed through (this is the one path where `communication-engine`'s §9 "deliver with fallback" does *not* apply, because delivering an ethics-violating response is worse than the interruption-cost of a brief delay) |
| Personality Memory (§6) has no row (misconfiguration) | Falls back to the hardcoded default profile in code, never a null/crash — this is a config-integrity bug to alert on, not a runtime decision point |
| Core Identity Store fails to load at startup | Engine fails health checks and does not serve traffic — there is no safe default for *who NOVA is*, unlike style/verbosity defaults; this is the one failure mode with no graceful degradation, by design |

## 9. Data model — `personality` Postgres schema

```sql
CREATE TABLE personality.core_identity (
    id               INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),  -- singleton, §3
    schema_version   INT NOT NULL,
    traits           JSONB NOT NULL,
    values           JSONB NOT NULL,
    forbidden_behaviors JSONB NOT NULL,
    version_note     TEXT NOT NULL,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE personality.memory_profile (
    id                    INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),  -- singleton
                                                                       -- this phase, §6
    verbosity             TEXT NOT NULL DEFAULT 'moderate',
    technical_depth        TEXT NOT NULL DEFAULT 'moderate',
    terminology_preference  JSONB,
    source                 TEXT NOT NULL DEFAULT 'static_default',   -- vs.
                                                                       -- 'digital_twin'
                                                                       -- once 2D-D ships
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE personality.validation_audit (
    audit_id         UUID PRIMARY KEY,
    session_id        UUID NOT NULL,      -- correlates to communication.conversation_session
    passed            BOOLEAN NOT NULL,
    violations        JSONB,              -- list[ViolationRecord], §4
    selected_style    TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

`memory_profile` is a singleton this phase (§6) — its schema is written so a
future per-user row (trivial, since ADR-025's single-user default means "per
user" and "the one row" are the same thing today) requires no migration beyond
dropping the `CHECK (id = 1)` constraint.

## 10. Event contracts

RPC pairs served by this engine: `personality.validate_response.request` /
`.reply`, `personality.style.select.request` / `.reply` (§7.1).

Subscribed (not yet publishing anything this phase, since nothing downstream
needs it): `personality.memory.update` — inbound from `digital-twin-engine`, once
it exists (§7.2, §0.6-equivalent deferred port, defined now per ADR-024
versioning discipline, unused until Phase 2D-D).

Subject naming: `personality.<domain>.<action>`, identical convention to every
prior engine.

## 11. APIs exposed

Bible Part 17's "Personality APIs" list, realized:

All routes are served under the `/v1/personality` prefix, per the project-wide
`/v1/<domain>/...` REST convention (Phase 2D-A Gate Review correction — bare
paths were an inconsistency against every other engine's own API surface):

| Endpoint | Method | Notes |
|---|---|---|
| `/v1/personality/identity` | GET | Retrieve Personality (§3) |
| `/v1/personality/validate` | POST | Validate Response — HTTP mirror of the RPC (§7.1), for admin/debug use |
| `/v1/personality/style` | GET | Communication Style — current default/context-mapped style (§5) |
| `/v1/personality/identity/snapshot` | GET | Identity Snapshot — used by `communication-engine`'s fast-path (§13 of that doc) |
| `/v1/personality/memory` | GET | Retrieve current Personality Memory profile (§6) |

`/internal/health`, `/internal/readiness`, `/internal/metrics` remain
unprefixed by `/v1` — the ops/probe surface, not a versioned domain API.

`Update Preferences`, `Behavior Analysis`, `Emotion Profile`, `Teaching Mode`
(Bible Part 17) are **not exposed this phase** — each requires either
`digital-twin-engine` (preferences, behavior analysis over accumulated evidence)
or `perception-engine`'s emotional-cue signals (2D-B), neither of which exists
yet (§0.2, §7.2).

## 12. Performance considerations

Both served RPCs are pure, deterministic, in-memory computation over the small
state in §9 (no external calls, no model inference, §0.3) — sub-millisecond
target, so this engine is never the dominant term in `communication-engine`'s
latency budget (Master Blueprint Risk §11.1). The `/v1/personality/identity/snapshot`
endpoint exists specifically to support that document's §13 fast-path, cached client-side
by `communication-engine` rather than refetched per utterance. This design —
rule-based validation over a model call — is itself the concrete application of
Master Blueprint §13.2 (low latency is part of NOVA's personality): between a
validator design that calls a model for richer semantic judgment and one that
stays deterministic and sub-millisecond, §0.3 already chose the latter
specifically because it is the lower-latency option that still satisfies
correctness, exactly the standing tie-break rule §13.2 states.

## 13. Scalability considerations

Stateless computation over a tiny, mostly-static dataset (§9) — this engine
scales by simple replication with no coordination needed between instances (the
singleton rows in §9 are read-heavy, written only on Doc 23 amendment or, later,
Digital Twin updates).

## 14. Security considerations

No user-identifying content is stored beyond `session_id` correlation in the
audit trail (§9) — this engine has no concept of "which user" beyond what
`communication-engine` supplies per request, consistent with ADR-025's
single-user default not requiring a tenant model here either. `core_identity`
mutation (Doc 23 amendments) is not exposed via any API in §11 — it is a
deployment-time configuration change, never a runtime-mutable value, closing off
an entire class of "personality drift via API misuse" risk by construction.

## 15. Doc 22 / Doc 23 compliance

| Decision | Principle |
|---|---|
| §0.1 this document restates, never redefines, Doc 23 | Doc 23's own closing section: amendments are a user conversation, never a code-level exception |
| §4.1 confidence-language validator | Doc 23 §5.2, §2 Trust Before Intelligence |
| §4.2 forbidden-pattern hard stop | Doc 23 §6 |
| §4.3 emotional-stability markers | Doc 23 §4.6, §6 standing directive |
| §4.4 professionalism floor applies to every style | Doc 23 §9 |
| §6 static default, never fabricated "learned" preference | Doc 23 §6 (inventing facts forbidden) |
| §8 core-identity load failure has no fallback | Doc 23 §1 (identity is not expected to change, and must never silently default to "no identity") |
| §14 no runtime API can mutate core identity | Doc 23 §1, Personality Consistency standing directive |
| §0.3 rule-based validator, sub-millisecond, no model call | Master Blueprint §13.2 (low latency is part of NOVA's personality) |
| §17's additive extension path (2D-C style logic, 2D-D real preferences) | Master Blueprint §13.6 (progressive capability) |
| §5's deliberately minimal, correct-first rule table over a speculative ML-based selector | Master Blueprint §13.7 (quality over feature count) |

## 16. Testing strategy

- Validator unit tests: one test per forbidden-pattern category (§4.2, §4.3),
  confidence-tier/phrasing mismatch cases (§4.1, both over- and under-claiming),
  professionalism-floor edge cases across every style (§4.4).
- Style Selector tests: every context-hint → style mapping in §5's rule table,
  including the no-hint default.
- Contract tests: `personality.validate_response`, `personality.style.select`
  payloads.
- Consistency-under-load test: 1,000 scripted requests across varied contexts,
  assert `core_identity.traits`/`values` never appear altered in any response's
  audit record — the concrete test of "personality remains constant" (Doc 23 §2)
  under volume, not just under a single spot check.
- Startup-failure test: corrupt/missing `core_identity` row, assert the engine
  fails health checks rather than serving with a default identity (§8).

## 17. Future extension points

- **Phase 2D-C** extends this engine: §5's Style Selector gains real
  context-adaptive logic (tone-matching detected user emotional state, once
  Perception's cues and richer conversational context exist), and validated
  responses start informing `communication-engine`'s Clarification Engine
  interactions.
- **Phase 2D-D**: `digital-twin-engine` begins publishing real
  `personality.memory.update` events (§7.2, §10); §6's singleton profile becomes
  genuinely learned rather than a static default — no schema change required,
  only `source` transitioning from `'static_default'` to `'digital_twin'`.
- **Phase 4**: Perception's emotional-cue signals (Bible Part 13 "Emotional
  Awareness") become an input to style selection, still filtered through this
  engine's unchanged validator and professionalism floor.
- **Phase 6**: Executive Cognition's full orchestration (Phase 6) may query this
  engine's audit trail (§9) as one input to explainability requests spanning
  multiple engines — read-only, no new write path introduced here.
