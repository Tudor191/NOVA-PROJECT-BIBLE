# ADR-023 — Every provider connector passes one identical compliance test suite

**Subsystem:** AI Model Orchestration Engine (Phase 2A)
**Status:** Accepted — new permanent engineering principle

## Context

Bible Part 7: "Adding a provider should require only a connector implementation."
SAD 06 §6 already sketched a `test_connector_swap.py` proving the *rest of the
engine* doesn't care which connector is in use. Before the first production
connector was considered complete, the user extended this: every connector itself
must pass an identical compliance test suite, adding a provider must require
implementing the interface and passing that suite *only*, and no provider-specific
behavior may leak outside the connector.

These are two complementary, not duplicate, guarantees: `test_connector_swap.py`
proves the *engine* is connector-agnostic; this ADR's compliance suite proves every
*connector* is actually behaviorally equivalent where the `ModelConnector` Protocol
promises equivalence (and cleanly, honestly different only where a provider
genuinely can't do something, e.g. Anthropic having no public embedding endpoint).

## Problem

`ModelConnector` (design doc §5) is a Python `Protocol` — satisfying it is a
static, structural type-check (does the method exist with the right signature),
not a behavioral guarantee (does `generate()` actually return a well-formed
result under a timeout, does `embed()` actually raise `NotSupportedError` cleanly
rather than an unhandled exception when unsupported, does `stream()` actually
yield incrementally rather than buffering everything and yielding once). What
closes the gap between "type-checks" and "behaves correctly, identically to every
other connector"?

## Alternatives considered

- **Per-connector, independently written test files** (`test_ollama_connector.py`,
  `test_anthropic_connector.py`, each with its own ad hoc assertions). Rejected:
  this is exactly how provider-specific behavior leaks into the test suite
  unnoticed — a subtle difference in what each file happens to check for is
  indistinguishable, at a glance, from a genuine capability difference, and two
  connectors could silently drift out of behavioral parity while both suites stay
  green.
- **Compliance tests written against real provider APIs** (a live Ollama server, a
  live Anthropic account) as the only verification. Rejected as the *sole*
  mechanism: this makes the compliance suite flaky and slow in CI, and — more
  importantly — it can't run against a connector for a provider with no free tier
  or no way to guarantee availability in CI. A "live model smoke test" already
  exists in the design (§19) as a separate, manually-triggered check; the
  compliance suite itself must be runnable, deterministically, on every PR.

## Decision

`tests/contract/test_connector_compliance.py` (the `tests/contract/` directory
already exists in every engine's scaffold, unused until now) is a single test
module, parametrized over every registered connector implementation
(`FakeConnector`, `OllamaConnector`, `AnthropicConnector`, and every connector
added afterward), each configured with a lightweight fake/mock transport so the
suite runs with no live provider dependency. The same test functions run against
every connector in the parametrization; there is no per-connector test file. The
suite asserts, identically for every connector:

- `generate()` returns a well-formed `GenerateResult` for a valid request.
- `generate()` raises a well-formed, catchable error (never an unhandled
  provider-SDK-specific exception) for a malformed request or a simulated
  transport failure.
- `stream()` yields at least one chunk incrementally (not one giant buffered
  chunk) for a valid streaming request.
- `embed()` either returns well-formed embeddings, or raises `NotSupportedError`
  cleanly — never anything else — for a connector that doesn't support the
  modality.
- `health()` returns a well-formed `ConnectorHealth` under both a healthy and a
  simulated-unhealthy transport.
- `tool_call` schema round-trips: a tool schema passed in produces a correctly
  provider-formatted request, and a simulated tool-call response parses back into
  the same normalized `ToolCall` shape regardless of connector.

Adding a new provider connector means: implement `ModelConnector`, add one line to
this suite's parametrization list, make it pass. Nothing else is required for the
connector to be considered structurally correct (production registration,
benchmarking, and health monitoring are separate, already-designed concerns, §2/§7
of the design doc).

## Consequences

- A connector that passes the compliance suite is provably behaviorally
  equivalent to every other connector wherever the Protocol claims equivalence —
  not just type-compatible.
- Any place a connector's test coverage *diverges* from every other connector's is
  now visible by construction (a skipped/xfailed parametrized case), which is
  exactly where genuine provider capability differences (Anthropic's missing
  embedding support) get documented as an explicit, asserted exception rather than
  a silent gap.
- This suite becomes the second layer of ADR-020 enforcement: the import-linter
  contract stops a provider SDK from being imported outside `connectors/`; this
  suite stops a connector's *behavior* from leaking provider-specific quirks into
  what the rest of the engine can rely on.

## Tradeoffs

- Writing one suite that fairly exercises every connector, including future ones
  with genuinely different capability profiles, requires more upfront design care
  than writing each connector's tests independently as convenient. Accepted
  because the alternative — the gap this ADR exists to close — is exactly the kind
  of provider-specific leakage Part 7 and the user's instruction both explicitly
  rule out.

## Future implications

Every future connector (vision, speech, a fourth cloud provider) is added to this
same suite's parametrization, never given its own bespoke test file. If a future
connector genuinely cannot satisfy one of the suite's assertions (a real capability
gap, not a shortcut), that is recorded as an explicit, named exception in the
suite itself — visible, not silently skipped.
