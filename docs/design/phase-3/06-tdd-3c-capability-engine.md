# TDD 3C — `capability-engine`

**Status: design only, awaiting approval. No production code authorized.**

**Reconciliation pass (post-`phase-3c-research`, still design-only):** All
four Phase 3C architectural forks are now **RESOLVED and approved**. Fork
3C-1/3D-1 (adapter ownership): **Option A.** Fork 3C-2
(`AgentContext.granted_capabilities` population): **Option C, declared-intent
only** — approved; see §4. Fork 3C-3 (rollback/snapshot ownership):
**Option B.** Fork 3C-4 (installation idempotency): **Option B.** See §4
for the full record of each. Several citation-precision and disclosure
gaps found during this pass are corrected in place below (§2.2, §2.3,
§3, §7, §14). See `docs/design/phase-3/12-3c-architecture-research.md`
for the full research trail this reconciliation pass is based on.

---

## 0. Scope and dependencies

**Scope.** Registry, installation pipeline (real, all 8 stages, sandboxed
per Fork E3's approved lighter OS-level scoping), and a first batch of
four built-in capabilities (git, filesystem, terminal, HTTP) — per
`ENGINEERING_ROADMAP.md:516` and Bible Part 15.

**Dependencies.** None beyond Phase 2D-D closure — confirmed no
technical dependency on `planning-engine` (`3B`); kept second in the
roadmap's own sequencing (`ENGINEERING_ROADMAP.md:527`) by convention,
not necessity.

---

## 1. Existing capability vs. what's being built

Nothing exists yet — confirmed by directory listing (no
`services/capability-engine`) and repo-wide grep (no `Capability*` type
in `nova-contracts` beyond one docstring-only mention in
`executive-cognition-engine`'s `domain/ports.py:12`, which this TDD does
**not** resolve — see §11). Entirely new engine.

---

## 2. Domain model

### 2.1 Capability Object Model — Bible Part 15, mapped with gaps disclosed

`part-15-capability-engine.md:157-197` names 18 fields for "every
capability": *Unique Identifier, Name, Description, Category, Version,
Author, Dependencies, Required Permissions, Required Resources,
Supported Platforms, Input Schema, Output Schema, Execution Adapter,
Health Status, Confidence, Performance Metrics, Documentation, Example
Workflows.*

**Proposed Phase-3-scoped subset** (built-in, first-party capabilities
only — no third-party marketplace in Phase 3, per Fork E3/§9):

```python
class Capability(BaseModel):
    id: UUID
    name: str
    description: str
    category: str
    version: str
    dependencies: list[str] = []
    required_permissions: list[str]
    required_resources: list[str] = []
    input_schema: dict          # JSON Schema, per Input Schema field
    output_schema: dict
    execution_adapter: str      # e.g. "git", "filesystem", "terminal", "http"
    health_status: Literal["unknown", "healthy", "degraded", "unhealthy"]
    installed_at: datetime
```

**Deferred fields, explicitly disclosed, not silently dropped:**
`author` (meaningless for first-party built-ins), `confidence`
(no learning/scoring mechanism exists yet to populate it meaningfully in
Phase 3), `performance_metrics` (belongs in observability, §9, not the
domain record itself), `documentation`/`example_workflows` (marketplace-
facing fields, deferred alongside the marketplace itself per §14's
Non-goals), and **`Supported Platforms`** (found silently absent during
the reconciliation pass, now explicitly disclosed rather than left an
undisclosed gap: all four Phase 3 built-ins run inside `capability-engine`'s
own container image against one deployment target — there is no
cross-platform distribution story to describe yet, since no third-party
capability install path exists in Phase 3).

**RESOLVED (reconciliation pass):** this 13-field subset is ratified as
authoritative for Phase 3C implementation. No field is added or removed
from the model shown above; the only change from the original proposal
is the explicit disclosure of `Supported Platforms` as deferred, above.

### 2.2 `CapabilityHandle` — referenced by doc 12, never defined

`AgentContext.granted_capabilities: list[CapabilityHandle]`
(`12-agent-architecture.md:135` — corrected during the reconciliation
pass; the original citation of line 136 pointed at `correlation_id`, not
`granted_capabilities`) references a type never given a field list
anywhere in the documentation (same gap class as `Estimate`/`RiskLevel`
in TDD 3B). Proposed, minimal, in-process-only:

```python
class CapabilityHandle(BaseModel):
    capability_id: UUID
    name: str
    execution_adapter: str
```

**Grounding, corrected during the reconciliation pass:** the original
text cited `01-tdd-preparation-and-fork-resolutions.md` §5.5 for the
"`inprocess`-execution-backend reasoning already established for
`AgentContext`" — that citation does not hold up: §5.5 is titled
"`AgentResult`/`AgentMessage` have no field-level definition anywhere
yet" and never mentions `AgentContext`. The actual grounding is an
inference from `docs/architecture/12-agent-architecture.md:80,267`'s own
execution-backend table (`inprocess` — same-process `asyncio` task, the
only enabled backend in Phase 3) combined with `AgentContext` being a
plain `pydantic.BaseModel` (`12-agent-architecture.md:129`) rather than a
wire payload — i.e., nothing in the current architecture serializes
`AgentContext` across a process boundary in Phase 3, so keeping
`CapabilityHandle` minimal costs nothing today. This is a reasonable
design inference, not a previously-established fact; it is stated as
such here rather than attributed to a citation that does not support it.

**RESOLVED (reconciliation pass):** this 3-field shape remains correct
after resolving Fork 3C-1 (§4) as Option A — the full `Capability` record
is resolved live, per invocation, by `capability-engine` itself (§4's
resolved architecture), so `CapabilityHandle` never needs to carry more
than enough to identify and address a granted capability. It is also
correct under Fork 3C-2's own resolution (§4, Option C, declared-intent
only): the field's shape is unaffected by that decision either way — the
type stays exactly as proposed here regardless of whether or how
`AgentContext.granted_capabilities` is ever populated. **Ratified**, no
longer flagged as merely proposed.

### 2.3 Capability lifecycle and Installation Pipeline — Bible Part 15, implemented literally

Lifecycle (`part-15-capability-engine.md:39-81`): *Discover → Install →
Validate → Register → Learn → Execute → Monitor → Improve → Update →
Retire.* Installation Pipeline (`:241-275`): *Download → Integrity
Verification → Dependency Resolution → Permission Review → Sandbox
Testing → Registration → Health Check → Activation.*

**Design decision:** the four built-in capabilities go through the
**real** 8-stage pipeline at first boot (via a seed/bootstrap call
against `capability-engine`'s own install API), rather than being
hardcoded pre-registered rows — this proves the pipeline end-to-end using
low-risk, first-party capabilities before any future third-party
capability ever reaches it, matching this project's "prove the pattern
before scaling it" idiom (already used for the single `engineering`
Supervisor in TDD 3E and the single `research-agent` bring-up).

For a first-party, bundled capability, "Download" and "Integrity
Verification" (signature/checksum) operate against the capability's
own package embedded in `capability-engine`'s own container image,
not a network fetch — there is no external marketplace to download from
in Phase 3 (§14; corrected during the reconciliation pass — the original
cross-reference pointed at §9, which is Observability, not Non-goals).

---

## 3. Sandboxing design (Fork E3's approved resolution, made concrete)

Per the user's approved decision: **lighter OS-level permission/resource
scoping, no gVisor, Firecracker, container, subprocess, or remote
execution backend.** Concrete mechanism proposed for each of the four
built-in adapters, targeting the roadmap's own acceptance bar
(`ENGINEERING_ROADMAP.md:536`: *"no capability can escape its declared
permission scope"*):

| Adapter | Scoping mechanism |
|---|---|
| `filesystem` | Path-prefix allow-list validated before every read/write/list call against the capability's `required_resources` declaration, checked against the **canonicalized/resolved path** (not the raw string) — no operation outside the declared root(s), including via `../`-traversal or a symlink that resolves outside it. |
| `terminal` | Executable allow-list (only explicitly declared binaries), restricted working directory, restricted/minimal environment variables, hard timeout, `asyncio.create_subprocess_exec` (never `shell=True`, eliminating shell-injection as a class of escape). |
| `git` | Same mechanism as `terminal`, additionally scoped to a declared repository root path — git operations are terminal+filesystem operations under this model, not a fourth distinct sandboxing primitive. |
| `http` | Outbound-host allow-list (declared domains only), per-request timeout, no arbitrary redirect-following beyond the allow-list. |

This is a genuinely new, disclosed proposal — no prior document specifies
these exact mechanisms. **RESOLVED (reconciliation pass):** the mechanism
table is ratified as sufficiently specified for implementation, with one
correctness tightening (the `filesystem` row above now requires
canonicalized-path resolution, closing an unstated `../`/symlink-traversal
gap found during this pass) and one **known, explicitly disclosed
limitation carried forward, not silently accepted:** none of the four
adapters prevents a `terminal`/`git` capability's own spawned subprocess
from making its own outbound network calls, which would bypass the
`http` adapter's host allow-list entirely. Closing this fully would
require process-level network isolation (e.g. network namespaces/firewall
rules) — a heavier isolation mechanism than the lighter OS-level scoping
Fork E3 already approved for Phase 3, so it is **not** implemented here;
it is disclosed as a real, accepted gap in Phase 3's security boundary,
consistent with Fork E3's own instruction that "Phase 3's sandbox is a
real but narrower boundary... must be disclosed explicitly in TDD 3C, not
silently implied to be full isolation"
(`01-tdd-preparation-and-fork-resolutions.md:256-259`). This limitation
is distinguished clearly from `docs/architecture/13-auth-and-security.md:92-93`'s
gVisor/Firecracker language (line numbers corrected during this pass —
the original citation was off by two lines), which this design
deliberately does not implement (per Fork E3, not reopened by this
pass).

---

## 4. Architectural forks — reconciliation pass status

### Fork 3C-1 / 3D-1 — Relationship to `action-engine`'s adapters — **RESOLVED: Option A**

**Evidence.** The roadmap names overlapping adapter categories for both
engines: `capability-engine` gets *"a first batch of built-in
capabilities (git, filesystem, terminal, HTTP)"* (`:516`); `action-engine`
gets *"terminal + filesystem + git adapters"* (`:515`). No document
states whether these are the same underlying adapter code or two
independent implementations.

**Options.**
- **Option A (resolved).** `capability-engine` owns the one, real
  adapter implementation for each target (git/filesystem/terminal/HTTP).
  `action-engine` **consumes** `capability-engine`'s registered
  capabilities (via its own `CapabilityPort`, mirroring the
  `GoalsPort`/`DigitalTwinPort` per-calling-engine convention) rather
  than reimplementing adapter logic — `action-engine`'s own contribution
  is the risk/approval/rollback/audit wrapper around an invocation, not a
  second copy of "how to run git."
- **Option B (rejected).** Each engine implements and owns its own
  separate adapters — matches the roadmap's literal per-engine phrasing
  more directly, at the cost of duplicated OS-interaction code and two
  independent places a sandboxing bug could hide.

**RESOLVED (reconciliation pass): Option A**, approved. Re-verified
against fresh reads of this TDD, TDD 3D, and every cited precedent before
resolving; no contradiction found. If anything, the supporting evidence
is stronger than "recommendation" language suggested: `00-research-and-scope.md:646-650`
labels the underlying ownership boundary **"Established, not open"**
*before* either TDD 3C or TDD 3D was written — *"Capability Engine owns
reusable building blocks only, consumed by both [Planning and Action]"*
is prior architectural doctrine this fork's Option A honors, not a new
proposal competing on equal footing with Option B. The `GoalsPort`/
`DigitalTwinPort` precedent is confirmed real in shipped code (not just
documented): `GoalsPort` is independently defined in each *consuming*
engine's own `domain/ports.py`
(`services/reasoning-engine/.../domain/ports.py:106`,
`services/executive-cognition-engine/.../domain/ports.py:83`); `DigitalTwinPort`
is defined in `communication-engine`'s own `domain/ports.py:129` (the
consumer, not `digital-twin-engine` itself). `action-engine` defining its
own `CapabilityPort` under Option A is the same, already-proven pattern.

**Made precise (a required consequence of Option A, not a new
architectural choice — no viable alternative exists given ADR-004):**
ADR-004 (`docs/architecture/00-overview-and-decisions.md:188-193`) is
unconditional — *"never a raw HTTP call from one engine's code straight
into another engine's module"* — so `action-engine` cannot call
`capability-engine`'s `GET /v1/capabilities` REST surface directly (that
surface is a stopgap for external/gateway-fronted access only, same as
every other engine's stopgap REST endpoint). Consuming a capability under
Option A is therefore an event-bus request/reply RPC to
`capability-engine`'s own process, mirroring the already-established
`ai_model.generate.request` pattern — **which also means
`capability-engine`'s own process is the one that actually executes each
adapter operation** (the real `git`/filesystem/terminal/`http` call
happens inside `capability-engine`, not `action-engine`). This reading is
independently corroborated by §9's existing `capability_invocation_total`/
`capability_invocation_duration_ms` metrics, which only make sense if
`capability-engine` itself performs (and can therefore instrument) every
invocation, not just capability resolution. At minimum two new
request/reply RPC subjects are required — illustratively,
`capability.resolve.request`/`.reply` (Prepare-Resources-stage
resolution + `health_status` check, TDD 3D §6 stage 5) and
`capability.invoke.request`/`.reply` (the actual adapter call, TDD 3D §6
stage 6) — **exact subject names and payload field shapes are
implementation-time work, not fixed here**, same discipline already
applied to every other new payload in this TDD package (§11). Both are
new, additive `nova_contracts` types per ADR-024 (`schema_version: int = 1`,
no existing consumer to break).

**Correction, Phase 3D research pass (this note, not a re-opening of Fork
3C-1/3D-1):** the RPC subjects and payloads described above as
"illustrative... not fixed here" were, in fact, implemented and tested
during Phase 3C's own implementation (PR #8) — see
`nova_contracts.events.capability` and
`services/capability-engine/src/nova_capability_engine/main.py`'s
`_make_resolve_request_handler`/`_make_invoke_request_handler`. The
illustrative names above match exactly what shipped:
`capability.resolve.request`/`.reply` and
`capability.invoke.request`/`.reply` are both live, served, and covered by
a real integration test
(`tests/integration/test_events_capability_resolve_and_invoke.py`).
Phase 3D's `action-engine` implements the consumer side against this
existing, canonical server contract — it does not redesign it. See
`docs/design/phase-3/13-3d-action-engine-research.md` §4 for the full
verification.

**Not resolved by this fork as of the original reconciliation pass, since
resolved by the Phase 3D research pass (`13-3d-action-engine-research.md`
§5.1, approved):** `action-engine`'s own `Action` model (TDD 3D §3.1) had
no field that unambiguously named *which* `Capability`/adapter a given
`Action` resolves against — `execution_target: str` was the closest
candidate, but its exact semantics for capability-selection were not
spelled out anywhere in TDD 3D's text. **Now resolved:** `execution_target`
holds the target capability's stable `name` field, resolved via a
backward-compatible additive extension to `CapabilityResolveRequestPayload`
(`name: str | None`, alongside the existing `capability_id: UUID | None`) —
approved by the user, not a Phase 3C architectural question (there was no
competing architecture here, only a missing field-level specification).

---

### Fork 3C-2 — `AgentContext.granted_capabilities` population mechanism — **RESOLVED: Option C, declared-intent only — approved**

Full 14-point analysis in `docs/design/phase-3/12-3c-architecture-research.md`
§22 (Fork 3C-2). Re-investigated during the reconciliation pass against
fresh reads of this TDD and TDD 3E in full: TDD 3E's Kernel Scheduler
dispatch sequence (§4 there) never mentioned `capability-engine` or
`granted_capabilities` anywhere — confirmed by exhaustive grep, zero
matches. TDD 3E's own citation of
`01-tdd-preparation-and-fork-resolutions.md` §5.5 "Fact 4" for the
`inprocess`-backend/`AgentContext`-as-live-object reasoning was also
unsupported (§5.5 contains no "Fact 4" enumeration and never mentions
`AgentContext` — the same class of citation error already found in this
TDD's own §2.2, also found in TDD 3E).

**Options**, reproduced from the research document:
- **A.** `agent-os`'s Kernel Scheduler queries `capability-engine`
  eagerly, at dispatch time, before the agent instance starts.
- **B.** Capability grants are static, declared in the Agent Package
  manifest, resolved once at agent-*install* time.
- **C (resolved, approved).** `AgentContext.granted_capabilities` holds
  only declared-intent identifiers; the only live, authoritative
  resolution stays exactly where it already is today — `action-engine`'s
  stage 5.

**RESOLVED: Option C, approved by explicit user decision.** The
architectural rule, stated plainly per the approval's own terms:
`action-engine`'s stage 5 (TDD 3D §6) remains the **sole live authority**
for capability authorization/checking at execution time.
`AgentContext.granted_capabilities` **must not become a second, competing
source of truth** — no synchronization mechanism, population mechanism,
registry cache, event subscription, or additional authority is introduced
for this field by this resolution, and none is required: the Fork 3C-1
resolution above already established that `action-engine` performs a
live, per-invocation RPC resolution + `health_status` check regardless of
what this field contains, so an eager dispatch-time query (Option A) or
an install-time snapshot (Option B) would only add a second, redundant
resolution path that stage 5's own check makes unnecessary. If the field
remains useful as declared-intent/contextual information for future
`agent-os` work, that is a separate, later, undecided design question —
not resolved and not invented here. **No new architectural principle or
ADR is introduced by this resolution.** See TDD 3E §4 for the strictly
necessary note recording this decision's consequence for the Kernel
Scheduler.

---

### Fork 3C-3 — Rollback/snapshot ownership for destructive capability operations — **RESOLVED: Option B**

**Evidence.** TDD 3D §2 (`07-tdd-3d-action-engine.md:47-57`) discloses
that its own Rollback Strategy requires some destructive
filesystem/terminal operations to be reversible, and states that *if*
Fork 3C-1 resolves to Option A, `capability-engine`'s filesystem adapter
"must support a pre-operation snapshot/backup primitive for destructive
calls" — a requirement this TDD's §3 (as originally written) did not
specify, flagged by TDD 3D as needing reconciliation "before either
[TDD's implementation] begins."

**Options**, reproduced from the research document:
- **A.** `capability-engine`'s filesystem (and terminal/git) adapter
  itself implements a snapshot/backup primitive, exposed as part of the
  adapter's own interface.
- **B (resolved).** `action-engine` owns all rollback logic itself,
  entirely outside `capability-engine` — capturing its own pre-state via
  `capability-engine`'s existing, ordinary read/list operations before
  invoking a destructive call, restoring it itself on failure.
- **C.** No automated rollback for capability-invoked destructive
  operations in Phase 3; TDD 3D's Rollback Strategy is rescoped.

**RESOLVED (reconciliation pass): Option B.** Fork 3C-1's resolution
above makes this precise rather than speculative: since `capability-engine`'s
own process is the actual executor of every adapter call (RPC-invoked),
`action-engine` has no direct filesystem access of its own to the target
resource — under Option B, `action-engine` captures pre-state the *only*
way it architecturally can, by invoking `capability-engine`'s existing,
already-scoped, non-destructive read/list operations (the same
`capability.invoke.request` RPC already required by Fork 3C-1, just
targeting a non-destructive operation first) before issuing the
destructive call, then restoring via the same mechanism on failure. This
requires **no new capability on `capability-engine`'s adapter interface
at all** — confirming Option B, not Option A. This also matches this
TDD's own already-written Fork-3C-1 reasoning more literally than Option
A would have: *"`action-engine`'s own contribution is the
risk/approval/rollback/audit wrapper around an invocation, not a second
copy of 'how to run git.'"* — rollback was already framed as
`action-engine`'s wrapper responsibility in this document's own original
text, before this pass.

- **`capability-engine` does not need to expose any snapshot/restore
  primitive under Option B** — confirmed above.
- **TDD 3D's Rollback Strategy does not need to be rewritten or
  narrowed** — its existing `RollbackStrategy.kind: Literal["restore_file", ...]`
  shape (TDD 3D §3.1) is unaffected; only the *mechanism* by which
  `action-engine` captures pre-state for `"restore_file"` is now
  concrete (read-before-write via the resolved Fork 3C-1 RPC), not the
  model itself.
- **Destructive filesystem/terminal operations still satisfy the
  intended rollback guarantee** — `action-engine`'s own read-before-write
  discipline is sufficient, since `capability-engine`'s adapters remain
  the sole executor either way.
- **No new problem was found.** Resolving Option B did not surface any
  architectural contradiction; it is reported and resolved, not worked
  around.
- **Phase 3C's acceptance criteria are unaffected** — see §13's updated
  criterion 5, below.
- **Phase 3D's acceptance criteria are unaffected in substance** — TDD
  3D's own criterion 6 required reconciliation "before either
  implementation begins"; that reconciliation is this resolution itself
  (also updated in TDD 3D directly, per the reconciliation pass on that
  document).

---

### Fork 3C-4 — Installation/bootstrap idempotency — **RESOLVED: Option B**

**Evidence.** This TDD, as originally written, contained no idempotency
discussion anywhere, despite `POST /v1/capabilities/install` being a
mutating, self-triggered-at-every-boot endpoint (§2.3's bootstrap
design).

**Options**, reproduced from the research document:
- **A.** Standard idempotency-key pattern (caller-supplied key, dedup
  store).
- **B (resolved).** Natural-key idempotency: `(name, version)` uniqueness
  is the dedup mechanism; a `POST` for an already-installed
  `(name, version)` returns the existing record as a success, without
  re-running the pipeline.
- **C.** No special handling; the caller (bootstrap code) pre-checks via
  `GET` before every `POST`.

**RESOLVED (reconciliation pass): Option B.** Verified against every
dimension requested:
- **Database schema:** `capability.capability` gains a `UNIQUE (name, version)`
  constraint (§6, updated) — matching `07-database-architecture.md`'s own
  pre-existing sketch for this exact table, genuine pre-existing
  precedent, not invented.
- **`POST /v1/capabilities/install` behavior (§7, updated):** a `POST`
  whose `(name, version)` already exists returns the existing record
  (HTTP 200), never re-running the 8-stage pipeline and never erroring.
- **Bootstrap / repeated first-boot installation:** solved by
  construction — every subsequent boot's seed call for the four built-ins
  is a fast, idempotent no-op against the constraint above; no
  crash-loop risk.
- **Concurrent installation:** the `UNIQUE (name, version)` constraint is
  the actual safety net — a race between two concurrent inserts is
  resolved at the transaction level; the pipeline's registration step
  must treat a uniqueness-violation on insert as the same idempotent
  no-op outcome as a pre-existing-row check, not surface it as a hard
  failure.
- **Transaction / installation-event-table behavior:** an idempotent
  no-op `POST` does **not** append new `capability_installation_event`
  rows — the log's own stated purpose ("audit trail of every install's
  path through the 8 stages") stays accurate, since a no-op never
  re-traverses the stages.
- **`GET`-before-`POST` is no longer necessary** — this is the direct
  benefit of Option B over Option C; the bootstrap caller (and any future
  caller) may call `POST` unconditionally and safely.
- **Matches existing database conventions** — confirmed via the same
  `07-database-architecture.md` precedent above, and via this project's
  general preference for small, precedented, unsurprising mechanisms over
  a bespoke idempotency-key framework (rejected per this pass's own
  instruction not to introduce one unless required — it is not required
  here).

---

## 5. Ports

- **`CapabilityPort` is not defined by `capability-engine` itself** (it
  is the engine being called, not a caller) — it is defined by
  `action-engine` (TDD 3D, per Fork 3C-1/3D-1's resolution, §4). **Updated
  (reconciliation pass, Fork 3C-2 resolved as Option C, §4): `agent-os/kernel`
  does not need its own `CapabilityPort`** — `action-engine`'s stage 5
  remains the sole live authority for capability resolution, and
  `AgentContext.granted_capabilities` is populated with no runtime
  mechanism (declared-intent only, if populated at all). `CapabilityPort`
  has exactly one caller in Phase 3: `action-engine`.
- No new upstream port needed for `capability-engine` itself — the
  installation pipeline's "Permission Review" stage surfaces to a human
  via the existing `communication.intent.deliver.request` gate (same
  precedent as Fork D/TDD 3D — a new capability's permission grant is a
  disclosure-worthy event), not a new mechanism.

---

## 6. Persistence

New `capability` Postgres schema: `capability` table (the `Capability`
model, §2.1, plus `permissions_reviewed_at`/`sandbox_test_passed_at`
timestamps recording pipeline-stage completion), `capability_installation_event`
(append-only log of pipeline-stage transitions per install — mirrors
`ConversationDecisionTraceORM`'s append-only precedent from
`communication-engine`, giving a full audit trail of every install's
path through the 8 stages).

**Added, reconciliation pass (Fork 3C-4, §4):** `capability` gains a
`UNIQUE (name, version)` constraint — the mechanism `POST /v1/capabilities/install`'s
idempotent behavior (§7) is built on, and the actual safety net for
concurrent install attempts (a uniqueness violation on insert is handled
as the same idempotent no-op as a pre-existing-row check, never a hard
failure). This constraint is genuine pre-existing precedent, not
invented here — it already appears in `docs/architecture/07-database-architecture.md:42`'s
own (otherwise superseded, see §11) sketch of this table.

**Authoritative schema note (reconciliation pass):** this section, not
`docs/architecture/07-database-architecture.md`'s own "highlights"-level
sketch of `capability.capability`, is the authoritative schema for Phase
3C implementation — see §11 for the reconciliation.

---

## 7. API surface

Per Bible Part 15's named API verbs (`part-15-capability-engine.md:533-555`)
and `docs/architecture/11-api-architecture.md:59-61`:

```
GET    /v1/capabilities
POST   /v1/capabilities/install
DELETE /v1/capabilities/{id}
```

Exposed directly (no `api-gateway` yet — same stopgap precedent as TDD
3B/3D). Bible's additional verbs (Register/Update/Search/Execute/
Benchmark/Validate/Monitor) are **not** all separately exposed as REST
endpoints in Phase 3 — `Execute` happens via `action-engine`'s
RPC-mediated invocation (§4, Fork 3C-1's resolution), not a public REST
call or a direct in-process call; `Benchmark` has no defined metric to
benchmark against yet (§14; corrected during the reconciliation pass —
the original cross-reference pointed at §9); the rest are internal
pipeline stages, not independently callable.

**Added, reconciliation pass (Fork 3C-4, §4): `POST /v1/capabilities/install`
is idempotent on `(name, version)`.** A request for an already-installed
`(name, version)` returns the existing record (HTTP 200), does not
re-run the 8-stage pipeline, and does not append new
`capability_installation_event` rows. Callers — including
`capability-engine`'s own first-boot bootstrap seed (§2.3) — never need
to `GET`-before-`POST`.

---

## 8. Failure and degraded behavior

| Condition | Behavior |
|---|---|
| Sandbox test fails during install | Capability never reaches `Registration`/`Activation` — install pipeline halts, recorded in `capability_installation_event`, no partial registration. |
| A registered capability's adapter fails at invocation time (e.g., git command exits non-zero) | Structured failure returned to the caller (agent or `action-engine`) — `capability-engine` itself never retries silently; retry policy is the caller's own concern (mirrors `action-engine`'s own retry-policy field, TDD 3D). |
| Sandboxing scope violation attempted (e.g., filesystem path outside allow-list) | Hard refusal at the adapter boundary, logged, `health_status` unaffected (a blocked attempt is not evidence of an unhealthy capability) — never a silent partial-execution. |
| Postgres unavailable | Registry reads fail loudly; no capability is invokable without a confirmed-healthy registry entry — never falls back to an unvalidated in-memory default. |

---

## 9. Observability

- `capability_install_pipeline_stage_total{stage=...}` (counter, one
  label per of the 8 stages).
- `capability_sandbox_violation_blocked_total{adapter=...}` (counter) —
  the direct metric proving the roadmap's own acceptance bar.
- `capability_invocation_total{adapter=..., outcome=...}` (counter).
- `capability_invocation_duration_ms` (histogram, per adapter).
- Standard health/readiness/metrics via `nova-service-kit`, unmodified.

---

## 10. Security boundaries

This TDD **is** a security-boundary-defining TDD — §3's sandboxing
mechanisms are the enforced boundary. `required_permissions` reuses the
established `PermissionGrant`/`PermissionAction` shape referenced in
`docs/architecture/13-auth-and-security.md:45-66` conceptually, though
`nova-auth` itself does not exist yet (confirmed: no `services/nova-auth`,
only a placeholder comment in `nova-core`'s `boot.py:85`) — so Phase 3's
permission checks are necessarily local/self-contained, consistent with
the same conclusion already reached for `action-engine` (TDD 3D §7).
ADR-032 does not bind `capability-engine` directly (it binds
privileged-capability-*gating* engines — `action-engine`, `autonomy-engine`
— not the registry that catalogs what exists).

---

## 11. Required workspace/contract changes

- New `services/capability-engine` (standard `-engine` scaffold, no
  tooling change needed).
- `nova_contracts.events.capability` (new file): `Capability`,
  `CapabilityHandle` (entities — never independently published; embedded
  in-process in `AgentContext` per the `inprocess`-backend reasoning),
  plus whatever install/health-change payloads are needed if
  `capability-engine` publishes state changes (e.g.
  `CapabilityRegisteredPayload`) — exact publish-worthy events are a
  TDD-implementation-time decision, not fixed here, since no document
  names a required subscriber for capability-state-change notifications
  in Phase 3. **This remains correct and is distinct from the two
  request/reply RPC payloads below** — no capability-named event subject
  is invented by this pass; ADR-004's request/reply RPC pattern is not a
  publish/subscribe event stream (§4).
- **Added, reconciliation pass (Fork 3C-1/3D-1, §4):** at minimum two new
  request/reply RPC payload pairs in `nova_contracts.events.capability`
  (or a shared module both `capability-engine` and `action-engine`
  import — implementation-time decision), serving `action-engine`'s
  `CapabilityPort` — illustratively `CapabilityResolveRequestPayload`/
  `.ReplyPayload` and `CapabilityInvokeRequestPayload`/`.ReplyPayload`,
  each `schema_version: int = 1` per ADR-024. Exact field shapes are
  implementation-time work, not fixed here, same discipline as every
  other new payload in this document. **Correction, Phase 3D research
  pass:** these field shapes were fixed during Phase 3C's own
  implementation (PR #8) and now ship exactly as illustrated above, plus
  one additive extension approved during Phase 3D's research pass
  (`CapabilityResolveRequestPayload.name: str | None`, `13-3d-action-engine-research.md`
  §5.1) — not a re-opening of this section, an implementation-time
  precision this section explicitly deferred, now closed.
- Root `pyproject.toml`/import-linter contracts gain
  `nova_capability_engine` (automatic via `scaffold-engine.py` for
  `root_packages`/the ADR-004 independence contract/ADR-006/ADR-007 —
  **the ADR-020 forbidden-import contract is not auto-registered by
  `scaffold-engine.py` and needs the same manual step `planning-engine`
  required during its own implementation** — recorded here as an
  implementation prerequisite, not applied to `pyproject.toml` by this
  research/reconciliation pass).
- `infra/docker/docker-compose.local.yml`, `build-and-scan.yml` matrix —
  new entries, same pattern as every prior engine.
- **Reconciliation pass, database schema authority:**
  `docs/architecture/07-database-architecture.md:32-43`'s
  `capability.capability` sketch predates this TDD and diverges from it
  (a `confidence REAL` column this TDD explicitly excludes; a singular
  `permissions JSONB` column instead of `required_permissions: list[str]`;
  no `description`/`dependencies`/`required_resources`/`input_schema`/
  `output_schema`/`execution_adapter`/`installed_at` columns). That
  document's own §2 is titled "Relational schema highlights" and states
  "every table has a corresponding SQLAlchemy model in
  `services/<engine>/...` and an Alembic migration chain scoped to that
  engine's schema" (`07-database-architecture.md:75-78`) — i.e., it is
  an early, illustrative, pre-implementation sketch superseded by each
  engine's own detailed schema once written, the same relationship its
  `planning.task_graph`/`planning.task_node` sketch already has to
  `planning-engine`'s real, shipped schema, without ever needing
  correction. **`06-tdd-3c-capability-engine.md` §6, not doc07, is
  authoritative for Phase 3C's `capability.capability` schema.** A
  minimal traceability note has been added to doc07 itself pointing back
  here (see that document).
- **Not resolved by this TDD:** `executive-cognition-engine`'s
  docstring-only `CapabilityPort` mention (`domain/ports.py:12`) is
  **not** promoted to a real Protocol — per that engine's own stated
  boundary (`docs/design/phase-2c/00-executive-cognition-engine.md` §5.8:
  *"arbitrating between two AI-layer engines' resource requests does not
  require knowing what NOVA can do"*), it has no functional need for
  capability awareness even once `capability-engine` exists. Not silently
  dropped — explicitly confirmed out of scope.

---

## 12. Testing strategy

**Unit (fake-backed):** all 8 installation-pipeline stages, including
failure at each stage (sandbox-test-fails halts correctly, etc.).
Sandboxing-scope-violation unit tests for each of the 4 adapters
(path-prefix escape attempt, executable-not-on-allow-list attempt,
host-not-on-allow-list attempt) — these are the direct proof of the
roadmap's acceptance bar and must be adversarial, not just happy-path.

**Contract:** payload round-trip tests for whatever `nova-contracts`
additions land (§11).

**Integration:** full install-to-invoke round trip for each of the 4
built-in capabilities against a real (but throwaway/sandboxed) git repo,
filesystem temp directory, subprocess, and a loopback HTTP endpoint.

**Real-infrastructure:** real-Postgres persistence test for the registry
and the append-only installation-event log; a real (not mocked) subprocess/
filesystem/git sandbox-violation test proving the OS-level scoping
actually blocks an escape attempt in a real process, not just in a fake
port's simulated logic — this specific test class cannot be meaningfully
faked, since the property being proven is about real OS-level
enforcement.

---

## 13. Acceptance criteria

1. All four built-in capabilities install successfully through the real
   8-stage pipeline at first boot, and a repeated boot/bootstrap call
   remains idempotent (Fork 3C-4, §4) — no duplicate pipeline run, no
   duplicate `capability_installation_event` rows.
2. A scripted sandbox-escape attempt for each adapter is blocked and
   logged, never silently succeeds — including a `../`/symlink-traversal
   attempt against the `filesystem` adapter specifically (§3, tightened
   during the reconciliation pass).
3. `DELETE /v1/capabilities/{id}` reverses an install cleanly (Bible's
   own *"every installation should be reversible"* requirement,
   `part-15-capability-engine.md:275`).
4. Registry state survives a real-Postgres restart simulation unchanged.
5. **Updated, reconciliation pass:** all four Phase 3C architectural
   forks are **resolved and approved** (§4) — Fork 3C-1/3D-1 (Option A),
   Fork 3C-2 (Option C), Fork 3C-3 (Option B), Fork 3C-4 (Option B). This
   criterion is satisfied for all of `3C`, `3D`, and `3E`: the
   coordination consequence TDD 3D's §2 originally flagged is reconciled
   by Fork 3C-3's resolution, and Fork 3C-2's resolution means no
   `agent-os`/`3E` implementation dependency on this decision remains
   either. No architectural fork blocks `3C`'s implementation start.

---

## 14. Non-goals / explicitly deferred

- Any third-party/marketplace capability discovery or installation
  (Bible's own "MARKETPLACE READY" section, `:557-575` — deferred by
  analogy to doc 12 §15's Agent-Registry marketplace timeline, Phase 8+).
- `reasoning-engine`'s `ReasoningTrace.selected_capabilities` being
  wired to a real `CapabilityPort`, **and** the related
  `PromptAssembly.available_capabilities` read-path
  (`docs/architecture/06-ai-layer-architecture.md:126`) and ADR-026's
  inclusion of "Available Capabilities" as a reasoning input
  (`docs/architecture/adr/ADR-026-reasoning-engine-cognitive-bridge-not-isolated.md:60-61,75-76`)
  — found during the reconciliation pass as a related, previously-undisclosed
  half of the same gap; neither is named as a Phase 3 roadmap deliverable;
  both are properly `reasoning-engine`'s own future Level 3/4 work
  (`ENGINEERING_ROADMAP.md`'s "Implementation order" step 7, already
  sequenced after `3C` exists) — `GET /v1/capabilities` is already
  sufficient for whichever read-path that future work designs; no
  constraint on Phase 3C's own implementation.
- `confidence`/`performance_metrics`/`documentation`/`example_workflows`/
  `author`/`Supported Platforms` fields on the `Capability` model (§2.1;
  `Supported Platforms` added to this list during the reconciliation
  pass — previously a silent, undisclosed gap).
- Any execution backend beyond direct in-process adapter invocation —
  no `container`/`subprocess`-isolated capability execution (Fork E3;
  Phase 7+ for `container`-grade isolation per doc 12 §8).
- **Added, reconciliation pass:** subscribing to `perception.filesystem.observed`
  to "refresh dependency graph"
  (`docs/architecture/10-inter-engine-communication.md:90`'s Event Bus
  scenario table, row 11) — found during the reconciliation pass as a
  real, previously-undisclosed architecture-doc-level expectation this
  TDD never engaged with. Has no functional purpose for Phase 3's four
  static, first-party, hardcoded-dependency built-ins (their
  `dependencies: list[str]` do not change based on repository content);
  it becomes relevant only once capability discovery beyond the four
  built-ins exists, which is already deferred above. Nothing about
  deferring this closes off subscribing later — NATS subject strings are
  not pre-allocated or otherwise scarce.
- **Added, reconciliation pass:** the Bible's "VISUAL CAPABILITY CENTER"
  (`part-15-capability-engine.md:577-601`) — no capability panel exists
  anywhere in Phase 3's `apps/web-client` scope
  (`03-gateway-web-prerequisite.md`, which names only Conversation,
  Planning, and Agent Activity panels); deferred alongside the
  marketplace itself, previously a silent gap, now disclosed.
- **Added, reconciliation pass:** registry search/indexing at scale
  (Bible's "thousands of installed capabilities" performance target,
  `part-15-capability-engine.md:619-627`; `docs/architecture/19-scalability-strategy.md:28`'s
  anticipated Postgres-full-text/OpenSearch mechanism). Phase 3 ships
  exactly four known capabilities — no search mechanism is needed; this
  becomes relevant only once catalog size approaches the scale that
  document anticipates, itself downstream of the marketplace deferral
  above.
- **Added, reconciliation pass:** closing the `terminal`/`git` adapters'
  cross-adapter network-escape gap (§3) — a spawned subprocess's own
  outbound network calls are not currently contained by any adapter
  mechanism. Closing it fully requires process-level network isolation,
  a heavier mechanism than Fork E3's approved lighter OS-level scoping;
  disclosed as a known, accepted limitation of Phase 3's security
  boundary (§3), not silently implied to be full isolation.
