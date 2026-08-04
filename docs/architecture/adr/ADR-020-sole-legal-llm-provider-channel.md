# ADR-020 — AI Model Orchestration Engine is the only legal channel to any LLM/AI provider

**Subsystem:** AI Model Orchestration Engine (Phase 2A); binding on every subsystem built from Phase 2A onward
**Status:** Accepted — new permanent engineering rule, effective immediately

## Context

Bible Part 7 states the underlying problem directly: "NOVA must never depend on a
single Artificial Intelligence model... The AI Model Orchestration Engine provides a
unified abstraction layer between NOVA and every intelligence provider... Replacing
the underlying model should never require rewriting NOVA." Part 7's own
"Architectural Requirements" section goes further, naming eight subsystems the
engine "must remain completely independent from" (Memory, Planning, Knowledge,
Personality, World Model, Executive Cognition, Action, Capabilities) and stating "it
serves only as the intelligence provider layer."

Before this ADR, exactly one precedent for this pattern existed: ADR-009
(`EmbeddingProvider` abstraction), which gave Memory Engine and Knowledge Engine a
Protocol-based embedding interface with a default `OllamaEmbeddingProvider`
implementation, specifically so that "when the AI Model Orchestration Engine ships in
Phase 2, it becomes a second `EmbeddingProvider` implementation... not a redesign of
either engine." That sentence, written during Phase 1, already anticipated this ADR.

On approving the Phase 1 Gate Review and authorizing Phase 2A, the user stated this
as an explicit, absolute, permanent rule: "No subsystem should ever depend directly
on an LLM provider. Every interaction with any AI model must pass exclusively
through the AI Model Orchestration Layer. No exceptions."

## Problem

Now that a real engine exists whose entire purpose is being the intelligence-provider
gateway, what enforces that every other subsystem — present and future — actually
routes through it, rather than importing an OpenAI/Anthropic/Ollama SDK directly the
first time doing so seems like the path of least resistance for some new feature?

## Alternatives considered

- **A documented convention with no enforcement mechanism.** Rejected: this project's
  own history already shows why — ADR-004 (Event Bus is the only legal cross-engine
  channel) and ADR-006/007 (Event Bus/Graph Store behind explicit interfaces) are all
  enforced by the root `pyproject.toml`'s `import-linter` contracts, checked in CI on
  every PR, specifically because a documented-only rule erodes the first time a
  deadline makes a direct import tempting. A rule this central deserves the same
  mechanical enforcement, not a weaker version of it.
- **Allow direct provider access for "simple" cases** (e.g., a future engine doing a
  single one-off classification call) as a pragmatic escape hatch. Rejected outright
  per the user's explicit "No exceptions" — and rejecting it is also the technically
  correct call: a "simple" direct call today is exactly the kind of case that becomes
  expensive to migrate later (Memory/Knowledge Engine's embedding calls, addressed
  below, are the concrete proof this project already has of that cost).
- **Scope the rule to only text-generation models**, leaving embeddings, vision,
  speech, etc. as separate concerns each engine can still access directly. Rejected:
  Bible Part 7 explicitly lists Embedding Models, Vision Models, Speech Recognition/
  Synthesis Models, Reasoning Models, Coding Models, Image/Video Generation Models,
  and "Future AI architectures" all under one unified `ModelConnector` abstraction
  ("Every language model should implement the same interface... The rest of NOVA
  never communicates directly with a specific provider") — narrowing the rule to only
  text generation would contradict the Bible's own scope for this engine.

## Decision

From Phase 2A onward, **no subsystem other than `ai-model-orchestration-engine` may
import or call any LLM/AI provider SDK or API directly, for any modality** (text
generation, embeddings, vision, speech recognition/synthesis, or any future
modality). Every interaction with an AI model — regardless of which subsystem
needs it — is a request through `ai-model-orchestration-engine`'s API/event
contracts. This is enforced the same way ADR-004/006/007 are enforced: a new
`import-linter` contract in the root `pyproject.toml`, added as part of Phase 2A's
own verification pass, forbidding every engine except
`nova_ai_model_orchestration_engine` from importing a provider SDK (`openai`,
`anthropic`, `ollama`, `google.generativeai`, etc.) — checked in CI on every PR,
identically in spirit to the existing broker/graph-client rules.

**Memory Engine and Knowledge Engine's existing direct Ollama embedding calls (via
`nova-embeddings-sdk`, built under ADR-009 in Phase 1) are a named exception to
enforce against, not a silent grandfather clause.** They predate this ADR and this
engine's existence, and per ADR-009's own text were always intended to become a
second `EmbeddingProvider` implementation once this engine shipped. They are
**recorded here as tracked migration debt** (see Future implications) rather than
silently exempted from the rule or silently ignored.

## Consequences

- `ai-model-orchestration-engine`'s `connectors/` directory becomes the only place in
  the entire codebase where a provider SDK import is permitted — every other engine
  depends only on `ai-model-orchestration-engine`'s own API/event contracts
  (`nova-contracts`), never on a provider SDK, mirroring exactly how ADR-006 makes
  `nova-eventbus-sdk` the only legal NATS/Kafka/RabbitMQ import site and ADR-007 makes
  `nova-graphstore-sdk` the only legal Neo4j import site.
- Reasoning Engine (Phase 2B), the first engine built entirely under this rule, has
  something concrete to prove it against: a contract test
  (`test_connector_swap.py`, per SAD 06 §6, already sketched before this ADR existed)
  runs its full test suite against a fake connector with zero code path touching a
  real provider SDK.
- Replacing or adding a provider (OpenAI, Anthropic, DeepSeek, Ollama, or any future
  provider) is now, by construction, a bounded change: implement one new
  `connectors/*_connector.py` file satisfying the `ModelConnector` Protocol, register
  it, done — never a change to any subsystem that merely *uses* models.

## Tradeoffs

- Every subsystem needing any AI capability now has an extra network/IPC hop (through
  `ai-model-orchestration-engine`) instead of calling a provider inline. Accepted
  because the alternative — direct coupling — is exactly what Bible Part 7 and the
  user's explicit instruction rule out; the latency cost of one additional
  well-observed hop is a deliberate trade against permanent architectural flexibility,
  not an oversight.
- The migration debt named above (Memory/Knowledge Engine's direct Ollama calls)
  means the rule is not, as of this ADR, universally true of the *existing* codebase
  — only of everything built from Phase 2A forward, with the pre-existing exception
  explicitly tracked rather than pretending it doesn't exist. A reader auditing
  "does NOVA actually follow ADR-020" needs this ADR's Future Implications section to
  get the honest answer, not just the Decision section.

## Future implications

- **Migrate Memory Engine and Knowledge Engine's embedding calls to route through
  `ai-model-orchestration-engine`** once it ships with embedding support (in scope
  for Phase 2A per Bible Part 7's "Embedding Models" — see the Phase 2A design doc).
  This is mechanical, not a redesign: both engines already depend only on the
  `EmbeddingProvider` Protocol (ADR-009), never on Ollama directly — swapping the
  concrete implementation from `OllamaEmbeddingProvider` to one backed by
  `ai-model-orchestration-engine` is a configuration change plus a new
  `EmbeddingProvider` implementation, exactly as ADR-009 always said it would be.
  This migration is recommended work, not bundled into Phase 2A's own scope (which
  is building the engine, not rewiring two already-shipped ones) — but it should not
  be deferred indefinitely, since every day it isn't done is a day ADR-020 is not yet
  universally true of the codebase.
- The new import-linter contract this ADR requires should be extended, not
  re-litigated, the moment a second provider-touching package appears anywhere
  outside `ai-model-orchestration-engine`'s `connectors/` — if that ever happens, it
  is a bug against this ADR, not a precedent for a new exception.
- Any future engine (Perception, Action, Autonomy, Digital Twin, or anything beyond
  the Phase 8 roadmap) that turns out to need AI model access gets it the same way:
  through `ai-model-orchestration-engine`, never by adding its own provider
  dependency. This ADR is written to need no revision when that happens.
