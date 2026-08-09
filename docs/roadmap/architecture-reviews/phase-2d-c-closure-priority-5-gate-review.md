# Phase 2D-C Closure — Priority 5 Gate Review: personality-engine's `channel` parameter

**Scope of this review: Priority 5 only**, per direct instruction. Priorities
1-4 are implemented, closed, and not reopened here. Priority 6 is
**untouched**. Phase 2D-D has not been started.

**Decision: Go**, for Priority 5 exactly as approved. `personality-engine`'s
`channel` parameter now produces a real, tested, deterministic effect
(voice overrides verbosity to `"concise"`) instead of being silently
ignored. This closes the personality-engine side of the gap the
[research document](phase-2d-c-closure-priority-5-research.md) traced —
**it does not, and was never intended to, make that effect observable in
any delivered NOVA response**; that remains a separate, disclosed,
unbuilt dependency. See §5.

---

## 1. The three approved forks and their decisions

| Fork | Decision | What it means |
|---|---|---|
| **A** — whether to implement now, given the end-to-end reachability gap | **A1** | Implement personality-engine's own fix only. Do not reopen Priority 3's scope reduction, do not add communication↔reasoning wiring, do not build a full response-shaping chain. |
| **B** — how to translate "voice caps verbosity" into code with no existing scale | **B1** | A fixed override to the single, already-precedented value `"concise"` — not a graduated, invented taxonomy. |
| **C** — whether to also address `resolve_response_shaping()`'s dead-code status | **C1** | Leave it exactly as Priority 3 left it. Not touched by this pass. |

All three implemented exactly as decided — no deviation, no expanded
interpretation.

## 2. What was implemented

**`services/personality-engine/src/nova_personality_engine/domain/
style_selector.py`** — the only production file changed:

```python
_VOICE_CHANNEL = "voice"
_VOICE_VERBOSITY_OVERRIDE = "concise"

def select_style(*, situation_hint, channel, memory_profile):
    style = _SITUATION_HINT_TO_STYLE.get(...)   # unchanged
    verbosity = (
        _VOICE_VERBOSITY_OVERRIDE if channel == _VOICE_CHANNEL
        else memory_profile.verbosity
    )
    return style, verbosity, memory_profile.technical_depth
```

**Exact behavior:**

- `channel == "voice"` → `verbosity` is always `"concise"`, regardless of
  what `memory_profile.verbosity` currently resolves to.
- Every other value — `"text"`, any other string (`"sms"`,
  `"notification"`, `""`, etc.), and `None` — leaves `memory_profile.
  verbosity` **completely unchanged**, byte-for-byte identical to the
  pre-Priority-5 behavior.
- `style` (the situation-hint-derived `CommunicationStyle`) and
  `technical_depth` are **never** touched by `channel`, in any case —
  verified directly, not just documented (§4).
- `channel`'s type is unchanged: `str | None` at every layer (API query
  param, RPC payload, domain function). No type-tightening to
  `nova_contracts.events.communication.ChannelType` was made — the research
  document (§2.7) named this as optional and not required, and it was not
  pursued, keeping the diff to exactly the one file needed.

## 3. Why no verbosity scale was introduced

The closure document's own prose ("caps verbosity at a bound below X's
ceiling") reads as a graduated, ordered scale. **No such scale exists
anywhere in this codebase or its design documents** — re-confirmed at
implementation time, not assumed from the research document alone:
`MemoryProfile.verbosity` is, and remains, an unconstrained `str` (default
`"moderate"`); the only other value ever used anywhere is `"concise"`,
appearing only as arbitrary example data in `personality-engine`'s own test
fixtures. No ADR, Bible section, Doc 23, or TDD defines an ordered verbosity
taxonomy. Building a graduated scale (`minimal < concise < moderate <
detailed < comprehensive`, formalized as a new `StrEnum`) would have
required inventing a value set and ordering nothing in this project has ever
specified — exactly the "channel-specific behavior merely because the field
exists" the user's own standing instruction, and Fork B's approved decision
(B1), explicitly ruled out. The fixed override to the one already-used value
is the most literal, least-invented translation of the real design evidence
(Doc 23 §2's "Channel... Adaptive" row; the original 2D-C TDD's "voice
responses shorter... by default") into code.

## 4. Why the dead `resolve_response_shaping()` path was deliberately left untouched

`communication-engine`'s `domain/response_shaping.py::
resolve_response_shaping()` is the only function anywhere in this codebase
that could ever pass a real, non-`None` channel value into
`select_style`. It is not called by any production code path — confirmed
again at implementation time (grep across `communication-engine/src` for
`resolve_response_shaping`, `derive_situation_hint`: the only match outside
`response_shaping.py` itself is its own unit test). Wiring it into the real
turn-handling path was Priority 3's own, already-approved scope reduction
(Priority 3 Gate Review §1, §8) — reopening it was explicitly named as Fork
A's A2/A3 in the research document and explicitly declined by the user's
approval of A1. This pass changed **zero lines** in `communication-engine`
— confirmed by `git status`/`git diff --stat` showing no file under
`services/communication-engine/` touched (§7).

## 5. Not end-to-end observable — restated, not softened

**A real user speaking to NOVA over voice does not, after this pass, receive
a more concise response than the same content over text.** The chain
remains broken exactly where the research document traced it:

```
select_style(channel="voice")              [NOW WORKS -- this pass]
  <- PersonalityClient.select_style          (unchanged, already correct)
  <- resolve_response_shaping(channel=...)   [STILL DEAD CODE -- Fork C, C1]
  <- [nothing calls this in production]
  ... communication-engine's real turn-handling path (Priority 3) calls
      reasoning.reason.request with a payload that has no style/verbosity/
      technical_depth/channel field at all -- unchanged, unverified as
      ever, out of this pass's scope.
```

Nothing in this pass changes any part of that chain below `select_style`
itself. `select_style` is now correct and fully tested in isolation; no
live conversation reaches it with a real channel value today, exactly as
disclosed in the research document and re-confirmed, not merely repeated,
at implementation time.

## 6. The stale task-tracker claim — status after this pass

The research document flagged that this session's own task tracker lists
"2D-C-5: Prerequisite — reasoning-engine consumes ResponseShapingDirective
(§0.7)" as `completed`, while direct code inspection shows reasoning-engine
consumes no such thing. **This claim remains stale after this pass** —
Priority 5's approved scope (Fork C, C1) explicitly did not touch
`reasoning-engine` or wire `ResponseShapingDirectivePayload` consumption;
`git diff --stat` confirms zero lines changed under
`services/reasoning-engine/`. The task-tracker entry's inaccuracy is
unrelated to and unaffected by this pass, and is restated here rather than
silently left for a future session to rediscover.

## 7. Verification results

| Check | Result |
|---|---|
| `ruff check` (whole monorepo, `pnpm lint` / `turbo run lint`) | 18/18 packages pass |
| `mypy src` (whole monorepo — the actual CI-equivalent gate, confirmed via `package.json`'s own `lint` script) | 18/18 packages pass, 0 errors |
| `ruff format --check` (files this pass touched) | Clean — `style_selector.py`/`test_style_selector.py` reformatted once during implementation (spacing only, no semantic change) and re-verified; `test_api_style.py`/`test_events_personality_request.py` already correctly formatted. Two pre-existing, unrelated formatting-drift files (`alembic/versions/0001_initial_schema.py`, `tests/unit/test_validator.py`) were left untouched, not swept in, matching the same discipline Priority 4 applied to an identical pre-existing drift finding. |
| Full pytest suite (whole monorepo, `pnpm test` / `turbo run test`, excludes `real_infra`) | 18/18 packages pass |
| personality-engine `domain/` coverage | 99% overall; **100%** on `style_selector.py` itself (gate: 85%) |
| Coverage gate negative control | `--cov-fail-under=100` (unreachable, since `validator.py` has one pre-existing uncovered line) → **exit 1**, `FAIL Required test coverage of 100% not reached. Total coverage: 99.22%` — the gate genuinely enforces |
| import-linter | 6/6 contracts kept, 0 broken — identical set to every prior checkpoint |
| `docker compose -f infra/docker/docker-compose.local.yml config` | exit 0 — no service/image/env change this pass |
| TypeScript contract generation (`generate_typescript.py`) | re-run, **zero diff** — confirms `nova-contracts` was not touched (decision #5: not modified, since the existing contract did not prevent the approved local behavior) |
| `git diff --stat` — `services/communication-engine/` | **empty** — zero unintended production diff |
| `git diff --stat` — `services/reasoning-engine/` | **empty** — zero unintended production diff |
| `git status --porcelain` (whole repo) | Exactly 5 files: `personality-engine/README.md`, `domain/style_selector.py`, `tests/unit/test_style_selector.py`, `tests/integration/test_api_style.py`, `tests/integration/test_events_personality_request.py` — no other engine, no `nova-contracts`, no migration, no config touched |

**Production SLOC** (`cloc`, `src/` only, excludes tests):

| Scope | Before | After | Δ |
|---|---|---|---|
| `services/personality-engine/src` | 604 | 609 | **+5** |
| Whole monorepo `services/*/src` + `packages/*/src` | 24,954 | 24,959 | +5 (100% attributable to personality-engine; every other engine's `src/` is byte-identical) |

## 8. Tests added

- **`tests/unit/test_style_selector.py`** (+4 test functions / +8 test
  cases once parametrization is counted, replacing the one test that
  documented the *absence* of channel behavior as correct):
  - `test_voice_channel_overrides_verbosity_to_concise` — using a profile
    whose verbosity is `"moderate"` (not already `"concise"`), proving the
    override actually changes something rather than coincidentally
    matching.
  - `test_non_voice_channel_preserves_the_memory_profile_verbosity`
    (parametrized over `None`, `"text"`, `"sms"`, `"notification"`, `""`)
    — proving "non-voice or None" means *every* value other than the
    literal string `"voice"`, not only `"text"`.
  - `test_voice_channel_override_is_idempotent_when_the_profile_is_already_concise`
    — the boundary case where the override and the profile's own value
    coincide.
  - `test_channel_never_affects_style_or_technical_depth` — computes
    `select_style` across `None`/`"voice"`/`"text"`/`"sms"` with the same
    `situation_hint` and profile, asserts `style` and `technical_depth` are
    each a single identical value across all four, *and* that verbosity
    itself does differ for `"voice"` — proving the test would have caught
    a regression in either direction, not just the one it was written for.
  - All 13 pre-existing test cases (situation-hint mapping ×8,
    case-insensitivity, no-hint default ×3, verbosity/technical_depth
    passthrough) — unmodified, still passing, proving the change made no
    other behavior different. (21 total test cases now collected in this
    file, up from 14 before this pass: 13 unmodified + 8 new − 1 removed.)
- **`tests/integration/test_api_style.py`** (+3 tests) — the real HTTP
  route (`GET /v1/personality/style?channel=voice`), through the real
  FastAPI app: voice overrides verbosity to `"concise"`; `None`/`"text"`
  preserve the default `MemoryProfile`'s `"moderate"`; voice does not
  change `style`.
- **`tests/integration/test_events_personality_request.py`** (+1 test) —
  the real `personality.style.select.request` Event-Bus RPC round trip
  (not just the HTTP mirror), confirming the fix is reachable through both
  of personality-engine's own served surfaces identically.
- **No changes to `communication-engine`'s `test_response_shaping.py`** —
  deliberately, per the research document's own §2.10: that test already
  passes `channel="voice"` through a fake and asserts pass-through; it does
  not, and should not, start asserting *real* personality-engine behavior,
  since the path it exercises remains unreachable from any real turn.
- **No `real_infra`-marked test added or needed** — no schema change, no
  new database interaction.

## 9. New findings and discrepancies discovered during implementation

- **None beyond what the research document already surfaced.** Every
  claim the research document made (the exact call sites, the dead-code
  status of `resolve_response_shaping()`, the absence of a verbosity
  scale, the default `MemoryProfile().verbosity == "moderate"`) was
  re-confirmed, not merely assumed, while implementing and testing —
  including by direct experiment: the new integration tests exercise the
  real `FakePersonalityRepository()` default (`MemoryProfile()`, verbosity
  `"moderate"`) through the real HTTP and RPC surfaces, and observe exactly
  the predicted `"concise"`/`"moderate"` split.
- **One pre-existing, unrelated documentation drift noticed, not
  fixed**: the personality-engine README's "Current count: 54 tests, all
  passing" line was already inaccurate before this pass (71 tests collect
  today on a clean checkout, before any Priority 5 change) — a drift from
  unrelated prior work, not something this pass introduced or was asked to
  correct. Left untouched per the explicit "do not make unrelated cleanup
  changes" instruction; noted here rather than silently carried forward
  unremarked.
- **One pre-existing, unrelated formatting drift noticed, not fixed**:
  `alembic/versions/0001_initial_schema.py` and `tests/unit/test_validator.py`
  are not `ruff format`-clean on the current baseline — confirmed
  unrelated to this pass (neither file was touched), left untouched
  rather than swept into an unrelated reformat, matching the exact
  discipline applied to an equivalent finding during Priority 4.

## 10. Remaining limitations — explicitly not closed by this pass

- **The response-shaping chain remains fully unwired**, exactly as before
  this pass (§5): `resolve_response_shaping()` uncalled by production code;
  no additive field on `ReasoningRequestPayload`; no reasoning-engine
  generation-prompt integration. All three are Fork A's A2/A3, explicitly
  declined.
- **Priorities 1-4 remain exactly as their own Gate Reviews left them** —
  not reopened, not touched.
- **Priority 6** (real-infrastructure verification, task #93) — not
  referenced as an implementation target, not advanced by this pass.
- **Phase 2D-D** — not started.
- **The stale task-tracker claim (§6)** — remains stale, unrelated to and
  unaffected by this pass.

Phase 2D-D has not been started. Priority 6 has not been touched. Per
instruction, this review stops here and awaits the user's review before any
further work begins.
