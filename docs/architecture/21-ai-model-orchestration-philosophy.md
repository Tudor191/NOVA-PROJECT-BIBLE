# AI Model Orchestration Philosophy

This document is the canonical reference for the AI Model Orchestration Engine —
why it exists, what it is and is not responsible for, and how every future AI
provider integration should be built against it. It does not replace the engine's
design document ([docs/design/phase-2a/00-ai-model-orchestration-engine.md](../design/phase-2a/00-ai-model-orchestration-engine.md))
or its ADRs (ADR-020 through ADR-024); it exists to state the *reasoning* behind
those decisions in one place, in prose, so a future engineer — or a future
instance of this same coding agent — adding a fifth, tenth, or fiftieth model
provider can understand the philosophy well enough to extend it correctly without
re-deriving it from first principles or re-reading five ADRs to reconstruct the
intent behind them.

## Why this layer exists

NOVA is built on a permanent constraint the user stated before Phase 2A began: no
subsystem should ever depend directly on an LLM provider. Every interaction with
any AI model must pass exclusively through the AI Model Orchestration Layer, with
no exceptions (ADR-020). That constraint exists for a concrete, practical reason —
not architectural purism for its own sake.

AI models are the single most volatile dependency in NOVA's entire stack.
Providers change pricing overnight. Models are deprecated with weeks of notice.
New, better models ship faster than almost any other kind of infrastructure
NOVA depends on. A NOVA that hard-wired Reasoning Engine, Planning Engine, or any
future cognitive subsystem to `anthropic.Anthropic()` or `openai.OpenAI()`
directly would have made a bet that specific SDK, that specific pricing model,
and that specific set of capabilities would remain correct for the lifetime of
those subsystems. That bet is false on its face — Bible Part 7 exists precisely
because NOVA's designers already knew this.

So the AI Model Orchestration Engine exists to absorb all of that volatility in
exactly one place. Every other engine that needs intelligence — today Reasoning
Engine doesn't exist yet, but Phase 2B will build it as this engine's first real
caller — asks a *question*, never picks a *provider*. Replacing OpenAI,
Anthropic, DeepSeek, Ollama, or any future model should never require a change
outside this one engine. That is the entire reason this layer is a layer, rather
than a shared library every engine links against: a library still requires every
caller to update when a provider's interface changes; a service boundary means
only this engine ever needs to.

## What responsibilities belong to this layer

Everything Bible Part 7 calls "AI Model Abstraction" and "Model Gateway"
concentrates here, and nowhere else:

- **Model Registry** — the catalog of every known intelligence provider and
  model, its capabilities, cost, and health.
- **Provider Abstraction** — one `ModelConnector` interface that every provider
  implements identically from the caller's point of view.
- **Routing** — deciding, for a given request, which model should handle it, and
  recording exactly why.
- **Execution** — actually calling the selected model: generation, streaming,
  tool calling, embedding.
- **Fallback** — retrying, substituting, or degrading gracefully when a model or
  provider fails.
- **Cost and budget tracking** — knowing what every request costs, and stopping
  before a budget is exceeded.
- **Privacy enforcement** — making sure a request classified as sensitive never
  reaches a provider that isn't cleared to see it.
- **Telemetry** — recording, for every single request, enough structured
  information that a human (or a future engine) can answer "why did NOVA choose
  this model, and what happened" without guessing.

If a capability's job is to get a prompt to a model and a response back —
correctly, safely, cheaply, and explainably — it belongs here.

## What responsibilities explicitly do not belong to this layer

This is the boundary that makes the layer trustworthy, and it is at least as
important as the list above. The AI Model Orchestration Engine does not, and
must never:

- **Reason.** It does not decide what conclusion to draw from a model's output,
  weigh evidence, or plan. That is Reasoning Engine's job (Phase 2B), and
  ADR-026 exists specifically to make sure Reasoning Engine, when it is built,
  treats this engine the same way this engine treats a provider SDK — as a
  dependency it calls through a clean interface, never logic it absorbs.
- **Remember.** It has no memory of past conversations, past requests, or past
  users. Long-Term Memory belongs to Memory Engine. A caller that wants a past
  conversation reflected in a prompt must assemble that context itself and hand
  it in as an already-formed `ContextComponent` — this engine never goes and
  fetches it.
- **Know facts.** It has no opinion about what is true, validated, or
  corroborated. That is Knowledge Engine's job. This engine's Model Registry
  stores facts *about models* (their cost, their capabilities, their health) —
  never facts about the world a model might be asked about.
- **Know current state.** It has no picture of what the user is doing right
  now, what project is open, or what device they're on. That is World Model
  Engine's job.
- **Source content or tools.** The Prompt Pipeline, Context Builder, Tool
  Calling, and Function Registry — four of Phase 2A's own named focus areas —
  are formatting and translation mechanisms, never sourcing or capability
  mechanisms. This engine receives already-assembled, source-labeled context
  components and already-defined tool schemas from its caller. It never calls
  Memory, Knowledge, World Model, or the Personality Engine itself, and it
  never knows what a tool *does* — only how to translate its schema into a
  given provider's wire format. This is the single most important boundary
  decision in the engine's design (design doc §0), because it is the one most
  tempting to violate: it would be easy, and would look like a helpful
  shortcut, for this engine to "just also" fetch relevant memories before
  building a prompt. Doing that would quietly turn a stateless gateway into a
  second Reasoning Engine, and NOVA does not get to have two.
- **Speak to the user.** No engine renders user-facing output directly (ADR-005).
  This engine returns structured results to its caller; only the Communication
  Engine ever produces what the user actually sees or hears.

Whenever a proposed feature for this engine would require it to fetch, judge, or
remember something rather than route, execute, and report on a model call, that
feature belongs in a different engine.

## Why it must remain stateless

ADR-022 makes this a hard requirement, not a preference: the AI Model
Orchestration Engine behaves as a stateless cognitive gateway. Conversation
state, memory, world model, and knowledge must remain external.

The test for this is deliberately concrete and operational, not philosophical:
*if this engine's entire process were killed and restarted between two calls
from the same caller in the same conversation, would anything observable
break?* For this engine, the answer must always be no. The only thing that
survives a restart is the Model Registry snapshot — and that is explicitly a
derived, disposable cache of data that lives durably in Postgres, refreshed on
registry-mutation events, never the source of truth itself.

Statelessness is what makes this engine horizontally scalable without a single
line of session-affinity logic, trivially restartable without a coordination
protocol, and — most importantly for its actual role — impossible to
accidentally couple to a particular conversation's history. A stateful
orchestration layer would inevitably start accumulating shortcuts: caching a
recent context here, remembering a user's last model choice there. Each
shortcut would be individually reasonable and collectively fatal to the
boundary above, because state is exactly what turns "I route requests" into "I
also happen to know things," and knowing things is not this engine's job.

## Why providers must remain interchangeable

Bible Part 7's "AI Model Abstraction" and this engine's entire reason for
existing (see above) both collapse to the same requirement if any provider is
allowed to leak provider-specific behavior past its own connector. ADR-023
makes this concrete and testable: every provider connector — `FakeConnector`,
`OllamaConnector`, `AnthropicConnector`, and every future one — must pass one
identical compliance test suite. Adding a new provider requires implementing
the `ModelConnector` Protocol and passing the compliance tests. Nothing else in
the codebase should need to change.

This matters for a reason more specific than "abstraction is good practice."
NOVA's routing decisions (see below) compare candidates from *different*
providers against each other on equal footing — capability score, cost,
latency, historical success rate. That comparison is only meaningful if every
connector reports those dimensions the same way, and if calling `.generate()`
on any of them behaves identically from the router's point of view: same
request shape in, same result shape out, same exception type
(`NotSupportedError`) for a capability a connector genuinely doesn't have,
never a provider-specific surprise. A router that had to special-case one
provider's quirks would stop being a router and start being a pile of
`if provider == "anthropic"` statements — exactly the coupling this whole
layer exists to prevent one level up.

## How routing decisions are made

ADR-021 establishes the standard: routing must be deterministic and explainable
wherever possible. This is implemented literally, not just claimed. `domain/
router.py`'s `plan_routing` function is a pure function of `(request, models,
historical_success_rates)` — no I/O, no randomness, no hidden state. Given the
same inputs, it always returns the same decision, and every candidate model's
score is visible in that decision, never just the winner's.

The routing pipeline follows Bible Part 7's nine-step "Orchestration
Principle" literally:

```
Receive Request -> Analyze Context -> Estimate Complexity -> Determine Required Skills
    -> Evaluate Available Models -> Select Best Model -> Execute -> Validate Output
    -> Store Experience (-> Improve Future Routing)
```

Complexity estimation is a structural heuristic — a weighted sum over task
type, context size, and tool count — deliberately *not* another model call.
Asking a model to judge how hard a request is before deciding which model
should handle it would be circular, and would make the router's own behavior
non-deterministic through a side door. Every eligible candidate is then scored
by a fixed formula combining capability score, cost, latency, and historical
success rate, and ranked; ties break on model ID, ascending, so re-ordering the
same input candidates never changes the outcome. If execution fails, the
fallback chain (ADR-021, Part 7 "Fallback Strategy") walks to the next-ranked
candidate the router hasn't already tried, and that walk is itself recorded —
the sequence of models a request actually passed through is exactly what
`RoutingDecision.candidates` and `fallback_from` capture, never an unrecorded
retry loop.

The result is that "why this model" is never a question this engine has to
guess at after the fact. It is a question the routing decision already
answered, structurally, before execution even happened.

## How privacy affects routing

Bible Part 7's Privacy Management requirement — public, internal, confidential,
highly sensitive, with highly sensitive data never leaving the local device
unless the user explicitly allows it — is enforced as a hard filter on model
eligibility, not a preference the router weighs against other factors.

Every model carries a `max_privacy_tier`: the highest, most sensitive privacy
classification it is permitted to serve. A request classified `HIGHLY_SENSITIVE`
is only eligible for a model whose ceiling is itself `HIGHLY_SENSITIVE` — in
practice, a local model, since no cloud provider is trusted with that
classification by construction. There is no override, and no scoring path
around this filter: a cloud model that scores highest on every other dimension
is simply never a candidate for a request the privacy classifier has ruled it
out for. When the privacy classification actually narrows the eligible pool,
that fact is recorded on the routing decision itself
(`privacy_constraint_applied`) and surfaces in the decision's explanation, so
a caller can see that privacy — not cost or capability — was the deciding
factor, whenever it was.

Privacy classification itself is a thin passthrough of a caller-supplied hint
today (`domain/privacy_classifier.py`) — this engine does not attempt to infer
sensitivity from content, because doing so reliably is a real, unsolved
research problem this engine has no business gambling the user's privacy
guarantee on. The classification is the caller's declared judgment; the
enforcement of what that judgment then permits is this engine's job, and it is
enforced absolutely.

## How telemetry supports explainability

ADR-021 requires structured telemetry on every inference request — success,
fallback-recovered success, or exhausted failure alike — with exactly ten
fields: selected provider, selected model, routing reason, estimated
complexity, latency, token usage, estimated cost, retry count, fallback usage,
and privacy classification. This is not incidental logging; it is the
mechanism that makes every other claim in this document verifiable rather than
merely asserted.

Two properties make this telemetry actually useful, not just present:

1. **Every request produces a record, including failures.** A request that
   exhausts its fallback chain still writes a `UsageRecord` with
   `outcome="failed"` and a `RequestFailedPayload` naming every model that was
   attempted and why the last one failed. A silent failure — a request that
   simply vanishes with no trace — is treated as a defect, not an edge case
   that telemetry happens not to cover.
2. **The human-readable explanation is derived from the structured fields, never
   authored independently.** `RoutingDecision.explanation` is built by
   formatting the same `capability_score`/`cost_score`/`latency_score`/
   `historical_success_rate` numbers that are already on the decision object —
   it can never claim a reason the structured data doesn't support, because
   there is no code path that lets it say anything the numbers don't already
   say.

The practical effect: `GET /v1/usage` and `GET /v1/models/select` (the dry-run
routing endpoint) are not debugging afterthoughts bolted onto the engine. They
are direct windows into the same structured decisions the engine makes on
every real request, which is what lets a future Reasoning Engine, a human
operator, or the user themselves trust a routing decision without having to
take it on faith.

## How future providers should integrate

This is the section a future integration should start from. Adding a new
provider — Google Gemini, OpenAI, a future local runtime, anything — is meant
to be a small, bounded, mechanical task, not an architectural one:

1. **Write one new connector module** under `connectors/`, the only directory
   in the entire NOVA codebase permitted to import that provider's SDK
   (ADR-020, enforced by an import-linter contract, not just this document).
   Implement the `ModelConnector` Protocol: `generate`, `stream`, `embed`,
   `health`. Any capability the provider genuinely doesn't support — most
   providers have no public embedding endpoint, for instance — raises
   `NotSupportedError`, never a provider-specific exception and never a
   silent no-op.
2. **Handle every provider-specific wire-format difference inside that one
   module, and nowhere else.** Anthropic's `system` parameter being top-level
   rather than a message role is the concrete precedent: it is translated
   entirely inside `AnthropicConnector`; no other file in the codebase knows
   or needs to know that quirk exists.
3. **Pass the ADR-023 compliance suite.** `tests/contract/
   test_connector_compliance.py` runs one shared set of test functions against
   every registered connector, with the new one added to its parametrization
   list. If the new connector passes, it behaves identically to every existing
   one from the router's point of view, proven rather than assumed.
4. **Register real models for the new provider in the Model Registry**, with
   honest capability scores, an honest `max_privacy_tier` (cloud providers
   default to `INTERNAL`, never higher, unless a specific provider is
   genuinely cleared for more), and real cost-per-token figures if the
   provider charges for usage.
5. **Extend `connectors/factory.py`** with one new branch mapping the model's
   `connector_type` to the new connector class, reading whatever credential
   the provider needs from `Settings` — following the same pattern
   `AnthropicConnector`'s API-key handling already established: a missing
   credential means the connector is simply absent from the live connector
   set, never a runtime surprise at first request.

Nothing else changes. No other engine's code changes. No router logic changes
— the new provider's models simply become additional candidates the same
scoring formula already ranks. This is the concrete, load-bearing proof that
the boundary described in this document holds: a provider is worth exactly as
much as its connector, its registry entry, and its compliance-suite pass, and
nothing about NOVA's cognitive layers needs to know, or care, that it exists.
