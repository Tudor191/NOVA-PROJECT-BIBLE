# STEP 3 — Extraction E: Shared `nova-contracts` Reference Types — Architecture Review & Gate Review

**Status:** Complete. `MemoryReference`, `WorldModelSnapshot`, and
`PersonalContext` are extracted into `nova_contracts.entities` and re-exported
from `executive-cognition-engine` and `reasoning-engine`'s own
`domain/models.py` files. `communication-engine`'s own, deliberately narrower
`WorldModelSnapshot` is untouched and stays local, per explicit approved
scope.

**Scope:** The final piece of STEP 3 of the Project Health Review's approved
5-step plan ([project-health-review-2026-08.md](project-health-review-2026-08.md)),
implementing Extraction E of the approved proposal
(`docs/design/nova-service-kit/boilerplate-extraction-proposal.md`), gated
separately from the A+B+C+D wave
([step3-nova-service-kit-extraction-gate-review.md](step3-nova-service-kit-extraction-gate-review.md))
behind its own mandatory design review, run and approved before any
implementation began.

---

## 1. Architecture Review

### 1.1 The design review, and what it found

Before writing any code, all three candidate types were inspected across
every engine that has a same- or similarly-named class, against the 10-point
checklist the user required:

1. **Semantic vs. structural identity** — `MemoryReference` and
   `WorldModelSnapshot` are constructed by byte-identical logic in
   `executive-cognition-engine`'s and `reasoning-engine`'s own
   `clients/memory_client.py` and `clients/world_model_client.py`: both read
   the same upstream `nova_contracts` reply payload
   (`MemoryRetrieveReplyPayload`, `ContextReplyPayload`) and map the same
   fields the same way. `PersonalContext` is the same honest placeholder
   projection in both, pending a future Digital Twin Engine. This is genuine
   construction-logic identity, not coincidental shape overlap.
2. **Ownership** — Memory Engine owns `MemoryReference`'s source data; World
   Model Engine owns `WorldModelSnapshot`'s and (by projection)
   `PersonalContext`'s. Neither consuming engine owns any of the three; both
   are equally non-owning peer consumers, which is exactly the shape ADR-004's
   shared-vocabulary exception exists for.
3. **Every producer/consumer** — enumerated: two producers (Memory Engine,
   World Model Engine, via their reply payloads), three prior independent
   consumer-side redefinitions (`executive-cognition-engine`,
   `reasoning-engine`, `communication-engine`).
4. **Domain-ownership violation risk** — none: `nova_contracts` is the
   sanctioned shared-vocabulary package both engines already depend on for a
   dozen other types; this is not a new cross-engine call.
5. **Serialization/`schema_version`/TypeScript/backwards compatibility** —
   none of these three types is ever published on the Event Bus directly (no
   `@register_payload` on any of them, before or after); ADR-024 governs
   public wire interfaces, which these are not. Confirmed via
   `codegen/generate_typescript.py`'s explicit `MODELS` allowlist, which never
   included them and still does not.
6. **ADR/boundary constraints** — none prohibit this; ADR-004's own
   shared-vocabulary exception is the applicable rule, already exercised by
   both engines' existing enum re-exports in the same files.
7. **Narrow ID+summary value-object principle** — intact: `MemoryReference`
   still carries only `memory_id`/`summary`/`confidence`, never Memory
   Engine's full record.
8. **Additional-field/semantics risk** — this is where the review found a
   genuine fork, not a false positive (§1.2 below).
9. **`nova-contracts` vs. engine-local** — `nova-contracts`, in a new
   `entities.py` module distinct from `events/`, since these types are never
   independently published payloads. `docs/architecture/
   02-repository-and-folder-structure.md` §4's own original canonical design
   already anticipated a `schemas/entities/` space for "shared domain
   entities" alongside `events/`, never built until this extraction.
10. **Migration path** — import + re-export via each engine's existing
    `domain/models.py` `__all__`, the same mechanism already proven 8+ times
    over in these same two files for other `nova_contracts` types. Zero other
    file in either engine needed to change, since both files already export
    these three names and every consumer (the `clients/` files) imports them
    from `domain.models`, not from a class defined in that module.

### 1.2 A genuine semantic fork, surfaced and resolved per instruction

The review found a third, previously-unexamined implementation:
`communication-engine`'s own `WorldModelSnapshot`
(`domain/ports.py`), carrying only 5 of the other two engines' 8 fields
(`user_id`, `objective`, `project_id`, `device`, `degraded` — missing `task`,
`activity`, `confidence`). Its own `clients/world_model_client.py` was
inspected and confirmed to deliberately construct only those 5 fields from
the same `ContextReplyPayload` — not an oversight, a narrower, use-case-scoped
projection.

Per the explicit instruction to stop and ask rather than resolve a genuine
fork silently, this was surfaced to the user before any implementation, with
the two live options (share communication-engine's copy too, using
`| None`-defaulted extra fields, vs. exclude it and keep it local). The user
selected **exclude communication-engine**, confirming the standing principle
this session now carries forward: **structural similarity alone is not
sufficient grounds for extraction** — a coincidentally-similar shape used for
a genuinely different, narrower purpose stays local, not because it's
inconvenient to unify, but because unifying it would hide a real semantic
difference behind a generic type.

### 1.3 What was built

- **`packages/nova-contracts/src/nova_contracts/entities.py`** (new) — three
  `pydantic.BaseModel` classes, verbatim field-for-field copies of the
  removed engine-local definitions: `MemoryReference`, `WorldModelSnapshot`
  (8 fields, the `executive-cognition-engine`/`reasoning-engine` shape, not
  `communication-engine`'s narrower one), `PersonalContext`. No
  `@register_payload`, no `schema_version` — these are internal domain
  reference types, not wire payloads.
- **`packages/nova-contracts/src/nova_contracts/__init__.py`** — re-exports
  the three new names alongside every existing `events/`-sourced type,
  documents the `entities.py` category's own rationale in the module
  docstring.
- **`executive-cognition-engine`'s `domain/models.py`** — the three local
  class bodies removed; replaced with
  `from nova_contracts.entities import MemoryReference, PersonalContext, WorldModelSnapshot`.
  `__all__` needed no change (already listed all three names, previously
  bound to the local classes, now bound to the imports). `Goal` — already
  diverged with `goal_tier` per ADR-029 — is untouched, as scoped.
- **`reasoning-engine`'s `domain/models.py`** — the same treatment for the
  same two of its three reference types; `KnowledgeReference` (§7.4, no
  equivalent anywhere else in the repository) stays exactly as it was, local
  and unextracted. `Goal` and `Constraint` are untouched.
- **Every `clients/` file in both engines** — zero changes. They import
  `MemoryReference`/`WorldModelSnapshot`/`PersonalContext` from their own
  engine's `domain.models`, which still exports those exact names — now via
  re-export instead of local definition, invisibly to every importer.
- **`communication-engine`** — zero changes, confirmed via `git status`/`git
  diff` showing no diff anywhere under `services/communication-engine/`.

### 1.4 Architectural rules preserved — verified, not assumed

| Rule | Verification |
|---|---|
| ADR-004 (Event Bus is the only legal cross-engine channel; `nova_contracts` is the sanctioned shared-vocabulary exception) | No engine imports another engine's internals; both engines import a third, neutral package — the identical exception mechanism the same two files' existing enum re-exports already use |
| ADR-024 (every *public* interface is versioned from day one) | Confirmed inapplicable — these types are never independently published on the Event Bus; no `@register_payload` before or after |
| Structural-similarity-is-not-sufficient standing principle | `communication-engine`'s narrower `WorldModelSnapshot` stays local; the fork was surfaced to the user rather than resolved by generic-izing the shared type |
| Narrow ID+summary value-object pattern | `MemoryReference` unchanged: `memory_id`, `summary`, bounded `confidence` — never Memory Engine's full record |
| No TypeScript codegen surface added | `codegen/generate_typescript.py`'s `MODELS` allowlist untouched; regenerating produces zero diff under `typescript/` |
| No new import-linter contract needed | The existing "Engines are independent (ADR-004)" contract already permits both engines importing `nova_contracts`; no new boundary was introduced |

---

## 2. What changed — exact files

### New (1)

- `packages/nova-contracts/src/nova_contracts/entities.py` (77 lines)

### Modified (3)

- `packages/nova-contracts/src/nova_contracts/__init__.py` — added the
  `entities` import line and 3 `__all__` entries, plus a docstring paragraph
- `services/executive-cognition-engine/src/nova_executive_cognition_engine/domain/models.py`
  — 3 local classes (37 lines) removed, replaced with a 1-line import;
  docstring updated
- `services/reasoning-engine/src/nova_reasoning_engine/domain/models.py` — 3
  local classes (`MemoryReference`, `WorldModelSnapshot`, `PersonalContext`)
  removed, replaced with a 1-line import; docstring updated;
  `KnowledgeReference` (§7.4, no equivalent anywhere else) untouched

### Untouched, confirmed

- `services/communication-engine/` — zero diff (§1.3, verified via `git
  status`/`git diff`)
- `packages/nova-contracts/codegen/generate_typescript.py` — zero diff
- `packages/nova-testkit/`, `docs/architecture/17-cicd-pipeline.md`, the
  deferred CI policy, real-infrastructure verification — none touched, none
  in scope

---

## 3. Production SLOC — before/after

Measured via `scc` (consistent with the STEP 2/STEP 3 checkpoints' own
methodology), same `src/` + Alembic `versions/` scope:

| | Before (STEP 3 A+B+C+D checkpoint) | After (this extraction) | Δ |
|---|---|---|---|
| **Production SLOC** | 32,017 | **32,043** | **+26** |

Verified two independent ways: (1) a full-corpus `scc` run over every `src/`
and `versions/` directory, and (2) a targeted `scc` diff of only the four
touched files against their pre-extraction (`git show HEAD:...`) contents —
both agree exactly on +26.

This is a small **net increase**, not a decrease, and that is expected and
correct: extracting two engines' duplicate definitions of the same 3 types
into 1 shared definition removes 2 copies' worth of code, but `entities.py`
itself adds fresh docstring/rationale text (proportionally larger than the
STEP 3 A+B+C+D extractions' terser canonical modules, because this
extraction's design review surfaced a genuine fork that the module's own
docstring now documents for future maintainers — see §1.1-§1.2). Unlike
STEP 3's A+B+C+D wave, this extraction touches only Python files already
within the Production SLOC scope (`src/`) — no new test suite, README, ADR,
or non-production file was added — so Total SLOC (all languages) moves by
the identical +26.

**50,000 SLOC milestone**: 32,043 / 50,000 ≈ **64.1%** (17,957 lines
remaining; direction unchanged from STEP 3's 64.0%).

---

## 4. Test results

**Full workspace** (`npx turbo run test --force`, all 18 packages):
**18/18 tasks successful, 0 failures, 970 passed** — byte-identical to the
STEP 3 A+B+C+D baseline. No test was added, removed, or modified by this
extraction; this is a pure type-relocation, and the unchanged count is itself
the confirmation of that.

| Package | Result | vs. STEP 3 baseline |
|---|---|---|
| nova-contracts | 76 passed | unchanged |
| executive-cognition-engine | 66 passed | unchanged |
| reasoning-engine | 71 passed | unchanged |
| communication-engine | 70 passed, 6 deselected | unchanged |
| all other 14 packages | unchanged | unchanged |
| **Total** | **970 passed, 0 failed** | **unchanged** |

`ruff check` and `mypy` (both across every affected package) are clean: 0
issues.

---

## 5. Coverage

The 85% `domain/`-scoped coverage gate was re-confirmed as **genuinely
enforcing**, not merely reporting, via the same negative-control method used
at the STEP 2 and STEP 3 checkpoints: running each touched engine's suite
with `--cov-fail-under=100` (unreachable) produced exit code 1 in both cases.

| Engine | `--cov-fail-under=100` result | Real coverage (85% gate) |
|---|---|---|
| executive-cognition-engine | `FAIL Required test coverage of 100% not reached. Total coverage: 98.19%`, exit 1 | 98% domain coverage (`domain/models.py` itself: 100%) |
| reasoning-engine | `FAIL Required test coverage of 100% not reached. Total coverage: 93.39%`, exit 1 | 93% domain coverage (`domain/models.py` itself: 100%) |

Both engines' real domain coverage is unchanged from the STEP 3 baseline and
comfortably above the real 85% threshold. `domain/models.py` itself is fully
exercised (100%) in both engines — the relocated types were, and remain,
fully covered by the existing test suite.

---

## 6. Import-linter results

**6/6 contracts kept, 0 broken** — unchanged from STEP 3, no new contract
added (none was needed; §1.4):

1. Engines are independent (ADR-004) — KEPT
2. No engine imports a message broker client directly (ADR-006) — KEPT
3. No engine imports a graph database client directly (ADR-007) — KEPT
4. No engine imports an LLM/AI provider SDK directly (ADR-020) — KEPT
5. `nova-testkit` has no engine-specific knowledge (ADR-033) — KEPT
6. `nova-service-kit` has no engine-specific knowledge (ADR-034) — KEPT

---

## 7. Additional verification

- **Docker Compose configuration**: `docker compose -f
  infra/docker/docker-compose.local.yml config` — exit 0, resolves cleanly.
  Unaffected by this extraction (no service definitions, images, or
  environment variables changed).
- **TypeScript generation**: `codegen/generate_typescript.py` itself is
  unmodified (`git diff` empty); re-running it regenerates all 74 contract
  files with **zero diff** under `typescript/` — confirming
  `MemoryReference`/`WorldModelSnapshot`/`PersonalContext` were correctly
  excluded from the `MODELS` allowlist, as scoped.
- **Regression verification**: `executive-cognition-engine` and
  `reasoning-engine` both retain their full pre-extraction test-pass counts
  (66 and 71 respectively) and identical domain coverage; every `clients/`
  file that constructs these types was confirmed unmodified.
- **`communication-engine` isolation**: `git status`/`git diff` against
  `services/communication-engine/` both report no changes — the engine this
  extraction deliberately excluded is untouched, not merely unaffected.

---

## 8. New technical debt

None. This extraction removes duplication (2 engines' worth of local
redefinitions) and adds no new abstraction beyond a straightforward shared
type module — the same pattern this codebase already uses for a dozen other
`nova_contracts` types re-exported through these same two files.

---

## 9. Architectural risks

None introduced. The one genuine risk the design review was specifically
built to catch — silently unifying `communication-engine`'s narrower
`WorldModelSnapshot` with the other two engines' 8-field version, which would
have let two of those three fields silently default to `None` for
`communication-engine` if it were ever wired to the shared type — was
identified and avoided by keeping that engine's copy local, per the user's
explicit decision.

---

## 10. Engine-boundary confirmation

- `nova_contracts.entities` is imported only by `executive-cognition-engine`
  and `reasoning-engine` (plus `nova_contracts.__init__` itself, for
  re-export) — never by `communication-engine`, and never engine-to-engine.
- Neither engine imports the other's internals; both import a third, neutral
  package — the same shape as every other `nova_contracts` re-export already
  in these two files.
- `nova-service-kit`'s ADR-034 boundary and `nova-testkit`'s ADR-033 boundary
  are both unaffected — neither package was touched by this extraction.

---

## 11. Gate Review

### 11.1 Deliverables checklist

| Item | Status |
|---|---|
| Mandatory 10-point design review performed before implementation | ✅ §1.1 |
| Genuine semantic fork (`communication-engine`) surfaced to the user before implementation, not resolved silently | ✅ §1.2 |
| `MemoryReference`, `WorldModelSnapshot`, `PersonalContext` extracted to `nova_contracts.entities` | ✅ §1.3 |
| Fields, validation, behavior, semantics preserved verbatim | ✅ §1.3, confirmed via 100% `domain/models.py` coverage in both engines |
| No `schema_version` added (internal types, not wire payloads) | ✅ §1.1 item 5 |
| Re-exported from both engines' existing `domain/models.py`, consumers unchanged | ✅ §1.3, zero `clients/` file changed |
| `communication-engine` completely untouched | ✅ §1.3, §7, §10 — zero diff confirmed |
| No TypeScript codegen addition | ✅ §1.4, §7 — zero diff on regeneration |
| No new import-linter contract (none needed) | ✅ §6 |
| `nova-testkit`, `17-cicd-pipeline.md`, CI policy, real-infra verification, Phase 2D-C untouched | ✅ §2 |

### 11.2 Gate criteria

| Criterion | Result |
|---|---|
| Ruff clean | ✅ 0 issues |
| Mypy clean (all affected packages) | ✅ 0 issues, 102 source files |
| Full test suite passes, count unchanged | ✅ 970 passed, 0 failed — identical to STEP 3 baseline |
| Import-linter | ✅ 6/6 kept, 0 broken |
| Coverage gate functions (negative control) | ✅ Confirmed via `--cov-fail-under=100` on both touched engines — see §5 |
| Docker Compose config valid | ✅ §7 |
| TypeScript generation unaffected | ✅ §7 |
| Regression: both engines behaviorally identical | ✅ §7 |
| `communication-engine` zero diff | ✅ §7, §10 |
| SLOC delta recorded | ✅ §3 |
| No engine boundary violated | ✅ §1.4, §6, §10 |
| No new architectural risk | ✅ §9 |
| No unrelated technical debt or documentation touched | ✅ §2, §8 |

### 11.3 Recommendation

**Gate passed.** Extraction E is complete, verified against the approved
scope, and ready for the user's review. The design review process worked
exactly as intended: it surfaced a genuine semantic fork
(`communication-engine`'s narrower `WorldModelSnapshot`) before any code was
written, the user made an explicit, informed choice, and the implementation
follows that choice precisely — nothing was unified that shouldn't have
been.

This closes STEP 3 of the Project Health Review's 5-step plan in full (the
A+B+C+D wave plus this separately-gated Extraction E). Per explicit
instruction, **Phase 2D-C does not begin** — this report stops here, for the
user's review.
