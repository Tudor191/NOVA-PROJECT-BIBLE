# ADR-024 — Every public interface is versioned from the beginning

**Subsystem:** AI Model Orchestration Engine (Phase 2A), binding on every subsystem's public interfaces from Phase 2A onward
**Status:** Accepted — new permanent engineering principle

## Context

Every engine's HTTP API has already used a `/v1/...` prefix since Phase 0 (`SAD
11`), which is versioning in name, but no engine's *event payload contracts* carry
an explicit version marker, and no written policy states what changing a payload
is allowed to do without breaking every consumer simultaneously. Before the first
production connector was considered complete, the user made this a permanent,
general rule, not scoped to just this engine: "Every public interface must remain
versioned from the beginning. Future breaking changes should never require
simultaneous updates across the entire system."

## Problem

`/v1/` in a URL versions the *API surface*; it says nothing about whether a given
payload schema can gain a field, lose a field, or change a field's meaning without
every consumer of that event needing to update in lockstep. Without an explicit
answer, the default behavior of a shared Pydantic model (`nova_contracts`) is
whatever falls out of however each change happens to be written — which is exactly
how "adding a provider" or "adding a routing factor" could accidentally become a
breaking change for every existing caller.

## Alternatives considered

- **Version only the HTTP API, leave event payloads unversioned.** Rejected: event
  payloads are just as much a public interface as HTTP endpoints (every engine's
  `published.py`/`subscribed.py` allow-list is exactly that — a public contract,
  enforced the same way an API's OpenAPI schema is), and Part 7's routing/telemetry
  payloads (ADR-021) are exactly the kind of schema likely to gain new fields as
  routing sophistication grows.
- **A global contract version number, bumped whenever anything changes.** Rejected:
  this would force every consumer to re-verify compatibility on every unrelated
  change elsewhere in `nova_contracts`, the opposite of "breaking changes should
  never require simultaneous updates across the entire system" — a change to a
  World Model payload should never force a re-check of an AI Model Orchestration
  payload's consumers.
- **Semantic-version every payload class individually with a full major.minor.patch
  scheme.** Rejected as more machinery than the actual problem needs right now:
  Pydantic's own additive-field tolerance (unknown/optional fields don't break
  existing consumers that don't reference them) already solves the common case:
  the real requirement is a *policy* about what counts as additive vs. breaking,
  plus a marker that lets a consumer detect which shape it received, not a version
  number on every class.

## Decision

Two concrete, minimal mechanisms, applied starting with every AI Model
Orchestration Engine payload added in Phase 2A, and binding on every subsystem's
public interfaces from Phase 2A forward:

1. **Every event payload class gains a `schema_version: int = 1` field.** Adding a
   field to an existing payload is never a version bump (Pydantic model
   consumers that don't reference a new field are unaffected — this is the
   additive case, and it is the default, expected kind of change). Removing a
   field, changing a field's type incompatibly, or changing a field's meaning
   without changing its name *is* a version bump — a new payload class is
   introduced (`GenerateResultV2`, or the field-level change is published under a
   new event subject) rather than the old shape being mutated out from under
   existing consumers. `schema_version` is what lets a consumer that genuinely
   needs to distinguish shapes do so explicitly, rather than needing to.
2. **HTTP APIs keep the existing `/v1/` convention** (already true, SAD 11) — this
   ADR formalizes it as a permanent rule rather than an incidental pattern: a
   breaking HTTP change is a new `/v2/` route living alongside `/v1/`, never an
   in-place change to `/v1/`'s existing response shape.

Both mechanisms share one policy: **additive changes never require a version bump
or a simultaneous update anywhere; only genuinely breaking changes get a new
version, and the old version keeps working, unchanged, for as long as any consumer
needs it.**

## Consequences

- A future consumer of `ai_model.request.completed` can check `schema_version`
  once and know exactly which fields it can rely on, rather than needing to
  coordinate a simultaneous deploy with this engine every time the payload grows.
- This engine's own event payloads (ADR-021's `RoutingDecision`/`RequestTelemetry`,
  §13 of the design doc) are the first real test of this policy: as routing grows
  more sophisticated (new scoring factors, new telemetry fields), those fields
  are added additively, `schema_version` stays `1`, and nothing downstream breaks.

## Tradeoffs

- Every payload class carries one extra field that, most of the time, never
  changes value. Accepted as a near-zero cost against the alternative (a future
  breaking change with no way for consumers to detect it before it breaks them).
- This policy asks every future author to correctly judge "additive vs. breaking"
  at the moment they make a change, which requires some judgment rather than a
  purely mechanical check. Accepted because the alternative (a rigid, fully
  automated compatibility checker) is real infrastructure this project doesn't yet
  have a concrete need for — evidence-driven optimization applied to tooling
  investment, not just runtime code.

## Future implications

Every future subsystem's `nova_contracts` payloads should carry `schema_version`
from their first commit, not retrofitted later — this ADR is written so that
"versioned from the beginning" is true by construction for everything built after
it, the same way ADR-020's import-linter contract makes the provider-isolation
rule true by construction rather than by reminder. Retrofitting `schema_version`
onto Phase 1's existing Memory/Knowledge/World Model payloads is not required by
this ADR (they predate it, and none has yet needed a breaking change) but should
happen the first time any of them actually needs one, rather than being deferred
further at that point.
