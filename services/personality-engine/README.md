# personality-engine

The Personality Engine (Bible Part 17, per `docs/design/phase-2d/
02-personality-engine.md`) owns NOVA's Core Identity, Consistency Validator,
Style Selector, and Personality Memory -- Phase 2D-A of the roadmap, one of
the two Voice & Communication Foundation engines alongside
`communication-engine`.

## Responsibility -- and the boundary that shapes every other decision below

Design doc §0.1-§0.3, Doc 23 (NOVA Personality Specification), ADR-030: this
engine is *who NOVA is while speaking*, never *how or whether NOVA speaks* (
that is `communication-engine`, ADR-005's gate) and never *what NOVA has
learned about this specific user's preferences* (that is
`digital-twin-engine`, Phase 2D-D). Concretely:

- **Rule-based, deterministic, zero model calls (§0.3).** Both served RPCs --
  `validate_response` and `style.select` -- are fixed logic over a small,
  versioned state (`domain/models.py`'s `CoreIdentity`), never an LLM
  judgment call. This is the concrete application of Master Blueprint §13.2
  (low latency is part of NOVA's personality): a validator that stays
  deterministic and sub-millisecond over one that calls a model for richer
  semantic judgment, chosen specifically because it is the lower-latency
  option that still satisfies correctness.
- **Stores and applies resolved preferences; never learns them (ADR-030).**
  `domain/models.py`'s `MemoryProfile` is a static default until Phase 2D-D's
  `digital-twin-engine` exists to publish real values via
  `personality.memory.update` -- the dependency direction is Digital Twin ->
  Personality, never the reverse; this engine cannot query "what does the
  user prefer," it can only receive already-resolved values.
- **Four validator check families, two are hard stops (§4, §8).**
  `domain/validator.py`'s forbidden-pattern and emotional-stability checks
  short-circuit with `passed=False, adjusted_content=None` -- delivering an
  ethics-violating response, even adjusted, is worse than the interruption
  cost of a brief delay. Confidence-language and professionalism-floor are
  soft corrections that still return `passed=True`.
- **Core Identity changes only through a Doc 23 amendment, never a runtime
  API (§3, §14).** `alembic/versions/0001_initial_schema.py` seeds the one
  `core_identity` row directly from Doc 23 §2/§6; there is no
  `PUT /identity` endpoint, by design.
- **The one no-graceful-degradation failure mode (§8).** Every other Personal
  Edition default (verbosity, style) falls back safely; a Core Identity load
  failure does not -- there is no safe default for *who NOVA is*, so the
  engine fails readiness and serves no traffic instead of guessing.

## Architecture

```mermaid
flowchart TB
    subgraph API["api/ (FastAPI)"]
        identity["identity.py\n(GET /identity, /identity/snapshot)"]
        validate["validate.py\n(POST /validate)"]
        style["style.py\n(GET /style)"]
        memory["memory.py\n(GET /memory, read-only)"]
        health["health.py"]
    end

    subgraph Events["events/"]
        serveValidate["serve(personality.validate_response.request)"]
        serveStyle["serve(personality.style.select.request)"]
    end

    subgraph Domain["domain/ (framework-free, no model calls)"]
        validator["validator.py\n(4 check families)"]
        styleSelector["style_selector.py\n(context-hint rule table)"]
        models["models.py\n(CoreIdentity, MemoryProfile)"]
        ports["ports.py (PersonalityRepository Protocol)"]
    end

    subgraph Repository["repository/"]
        pgRepo["postgres_personality_repository.py"]
    end

    API --> Domain
    Events --> Domain
    Domain -. depends on .-> ports
    Repository -. implements .-> ports
    API --> Repository
    pgRepo --> Postgres[(Postgres\npersonality schema)]
    serveValidate --> EventBus{{nova-eventbus-sdk}}
    serveStyle --> EventBus
```

`domain/` never imports FastAPI, SQLAlchemy, `nova_eventbus_sdk`, or (per
ADR-020) any LLM/AI provider SDK -- and defines no model-orchestration port
at all, mirroring Executive Cognition Engine's identical absence of one
(§0.3: this engine calls no model, by construction). `Core Identity` and
`Personality Memory` are loaded once into `app.state` at startup
(`main.py`), never fetched per-request -- the sub-millisecond, no-external-
call performance target in §12 would not survive a real Postgres round trip
per validation.

## Owned events

| Direction | Subject | Payload |
|---|---|---|
| Serves | `personality.validate_response.request` / reply | `PersonalityValidateResponseRequestPayload` / `ReplyPayload` -- Event Bus RPC alternative to `POST /validate`, same `domain.validator.validate` underneath |
| Serves | `personality.style.select.request` / reply | `PersonalityStyleSelectRequestPayload` / `ReplyPayload` -- Event Bus RPC alternative to `GET /style` |

`events/published.py` is an empty `frozenset` by design (§10) -- this engine
publishes nothing in Phase 2D-A; both RPC replies are returned directly from
`BoundEventBus.serve()` handlers. `personality.memory.update` (§7.2, ADR-030)
is defined in `nova-contracts` per ADR-024 versioning discipline but not yet
in `events/subscribed.py` -- no handler exists until Phase 2D-D's
`digital-twin-engine` is the one actually publishing it. See
`events/published.py` / `events/subscribed.py` for the enforced allow-lists.

## Owned APIs

- `GET /identity` -- the current `CoreIdentity` (§3); 503 if not loaded.
- `GET /identity/snapshot` -- a cacheable summary (`IdentitySnapshot`) for
  `communication-engine`'s fast-path (that document's §13); 503 if not
  loaded.
- `POST /validate` -- runs `domain.validator.validate`, records a
  `validation_audit` row regardless of outcome (Doc 23 §8's trust-through-
  inspectability requirement); 503 if Core Identity is not loaded.
- `GET /style` -- runs `domain.style_selector.select_style` against
  `situation_hint`/`channel` query params; 503 if Core Identity is not
  loaded.
- `GET /memory` -- the current resolved `MemoryProfile` (§6), read-only this
  phase -- no endpoint mutates it (ADR-030).
- `GET /internal/health`, `GET /internal/readiness`, `GET /internal/metrics`.

`Update Preferences`, `Behavior Analysis`, `Emotion Profile`, `Teaching Mode`
(Bible Part 17) are not exposed this phase -- each requires either
`digital-twin-engine` or `perception-engine`'s emotional-cue signals (2D-B),
neither of which exists yet (§11).

## Observability

`observability.py` defines `PersonalityEngineMetrics`, created once per
process right after `configure_observability()` runs.

| Metric | Kind | Labels |
|---|---|---|
| `personality_engine_validate_response_duration_seconds` | Histogram | -- |
| `personality_engine_style_select_duration_seconds` | Histogram | -- |
| `personality_engine_validations_total` | Counter | `outcome` (`passed`/`failed`) |
| `personality_engine_violations_total` | Counter | `check_family` |

Structured logs go through `nova_observability.get_logger`.

## Running locally

```bash
# from the repo root
docker compose -f infra/docker/docker-compose.local.yml up -d postgres nats
uv run --package personality-engine alembic -c services/personality-engine/alembic.ini upgrade head
uv run --package personality-engine uvicorn nova_personality_engine.main:app --reload --port 8000
```

Real Postgres is required to boot `main.py` without dependency injection;
this container has no Docker daemon, so that path is not exercised here --
see Testing below for what *is* verified without it.

## Testing

```bash
uv run --package personality-engine pytest services/personality-engine/tests
```

- `tests/unit/` -- pure domain logic: every validator check family
  (`test_validator.py`, including the hard-stop-short-circuits-soft-
  correction case) and every situation-hint-to-style mapping including the
  no-hint default and channel forward-compatibility (`test_style_selector.py`).
- `tests/integration/` -- boots the real FastAPI app (lifespan-driven, real
  routes) with `PersonalityRepository` substituted for an in-memory fake
  (`tests/fakes/repository.py`): every API endpoint including the 503
  no-Core-Identity path (`test_api_identity.py`, `test_api_validate.py`,
  `test_api_style.py`, `test_api_memory.py`), the not-ready-without-identity
  readiness case (`test_health.py`), and a real Event Bus round-trip through
  the served `personality.validate_response.request`/`personality.style.
  select.request` RPCs (`test_events_personality_request.py`) -- the one
  place `events/handlers.py`'s handlers are invoked through an actual
  subscription rather than called as bare functions.
- `tests/contract/` has no compliance suite this phase -- this engine has
  exactly one port (`PersonalityRepository`) and one real implementation, the
  same shape as `memory-engine`/`knowledge-engine`'s own single-repository
  engines, which carry the identical empty `tests/contract/__init__.py`.

Current count: 54 tests, all passing; `ruff check` and `mypy` both clean
across `src/`; `lint-imports` 4/4 contracts kept.

## Known limitations (Phase 2D-A)

- **`postgres_personality_repository.py` has no committed pytest coverage
  against a real Postgres instance** -- every prior engine's own committed
  suite has the identical gap (fakes only); this sandbox has no Docker
  daemon to run one against.
- **`select_style`'s `channel` parameter is accepted but does not yet
  influence selection** -- no Phase 2D-A acceptance criterion depends on
  channel-specific style, and inventing that rule now, untested against real
  usage, would be exactly the "quality over feature count" violation Master
  Blueprint §13.7 forbids. The parameter exists for forward compatibility
  (§13.6).
- **`MemoryProfile` is a static default for the whole phase** -- by design
  (ADR-030): real personalization arrives only once `digital-twin-engine`
  ships in Phase 2D-D and starts publishing `personality.memory.update`.
