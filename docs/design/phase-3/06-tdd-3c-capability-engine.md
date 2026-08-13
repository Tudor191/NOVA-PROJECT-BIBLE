# TDD 3C — `capability-engine`

**Status: design only, awaiting approval. No production code authorized.**

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
facing fields, deferred alongside the marketplace itself per §9's Non-
goals). **Flagged for explicit approval** — this subset is proposed, not
extracted from an authoritative narrower-scope statement.

### 2.2 `CapabilityHandle` — referenced by doc 12, never defined

`AgentContext.granted_capabilities: list[CapabilityHandle]`
(`12-agent-architecture.md:136`) references a type never given a field
list anywhere in the documentation (same gap class as `Estimate`/
`RiskLevel` in TDD 3B). Proposed, minimal, in-process-only (per the
`inprocess`-execution-backend reasoning already established for
`AgentContext` in `01-tdd-preparation-and-fork-resolutions.md` §5.5):

```python
class CapabilityHandle(BaseModel):
    capability_id: UUID
    name: str
    execution_adapter: str
```

Deliberately minimal — just enough for an agent to identify and invoke a
granted capability; the full `Capability` record stays in
`capability-engine`'s own registry, never duplicated into every
`AgentContext`. **Flagged for explicit approval.**

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
in Phase 3 (§9).

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
| `filesystem` | Path-prefix allow-list validated before every read/write/list call against the capability's `required_resources` declaration — no operation outside the declared root(s). |
| `terminal` | Executable allow-list (only explicitly declared binaries), restricted working directory, restricted/minimal environment variables, hard timeout, `asyncio.create_subprocess_exec` (never `shell=True`, eliminating shell-injection as a class of escape). |
| `git` | Same mechanism as `terminal`, additionally scoped to a declared repository root path — git operations are terminal+filesystem operations under this model, not a fourth distinct sandboxing primitive. |
| `http` | Outbound-host allow-list (declared domains only), per-request timeout, no arbitrary redirect-following beyond the allow-list. |

This is a genuinely new, disclosed proposal — no prior document specifies
these exact mechanisms. **Flagged for explicit approval**, distinguished
clearly from `docs/architecture/13-auth-and-security.md:90-92`'s
gVisor/Firecracker language, which this design deliberately does not
implement (per Fork E3).

---

## 4. Open architectural forks

### Fork 3C-1 — Relationship to `action-engine`'s adapters (shared with TDD 3D Fork 3D-1)

**Evidence.** The roadmap names overlapping adapter categories for both
engines: `capability-engine` gets *"a first batch of built-in
capabilities (git, filesystem, terminal, HTTP)"* (`:516`); `action-engine`
gets *"terminal + filesystem + git adapters"* (`:515`). No document
states whether these are the same underlying adapter code or two
independent implementations.

**Options.**
- **Option A (recommended).** `capability-engine` owns the one, real
  adapter implementation for each target (git/filesystem/terminal/HTTP).
  `action-engine` **consumes** `capability-engine`'s registered
  capabilities (via its own `CapabilityPort`, mirroring the
  `GoalsPort`/`DigitalTwinPort` per-calling-engine convention) rather
  than reimplementing adapter logic — `action-engine`'s own contribution
  is the risk/approval/rollback/audit wrapper around an invocation, not a
  second copy of "how to run git."
- **Option B.** Each engine implements and owns its own separate
  adapters — matches the roadmap's literal per-engine phrasing more
  directly, at the cost of duplicated OS-interaction code and two
  independent places a sandboxing bug could hide.

**Recommendation: Option A** — grounded in the ownership boundary
already established in `01-tdd-preparation-and-fork-resolutions.md`
(*"Capability Engine owns reusable building blocks only, consumed by
both [Planning and Action]"*) and in `Capability Object Model`'s own
`execution_adapter` field being the actual invocation mechanism (Bible
Part 15) — a second, independent adapter implementation would duplicate
exactly the "reusable building block" Capability Engine exists to
centralize. **This is presented as a recommendation, not a decided
fact — requires explicit approval**, and the final decision belongs in
whichever TDD is approved for implementation first (`3C` or `3D`).

---

## 5. Ports

- **`CapabilityPort` is not defined by `capability-engine` itself** (it
  is the engine being called, not a caller) — it is defined by
  `action-engine` (TDD 3D, pending Fork 3C-1/3D-1's resolution) and
  potentially by `agent-os/kernel` (TDD 3E, for populating
  `AgentContext.granted_capabilities`).
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
endpoints in Phase 3 — `Execute` happens via agent/`action-engine`
in-process invocation (§4), not a public REST call; `Benchmark` has no
defined metric to benchmark against yet (§9); the rest are internal
pipeline stages, not independently callable.

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
  in Phase 3.
- Root `pyproject.toml`/import-linter contracts gain
  `nova_capability_engine` (automatic via `scaffold-engine.py`).
- `infra/docker/docker-compose.local.yml`, `build-and-scan.yml` matrix —
  new entries, same pattern as every prior engine.
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
   8-stage pipeline at first boot.
2. A scripted sandbox-escape attempt for each adapter is blocked and
   logged, never silently succeeds.
3. `DELETE /v1/capabilities/{id}` reverses an install cleanly (Bible's
   own *"every installation should be reversible"* requirement,
   `part-15-capability-engine.md:275`).
4. Registry state survives a real-Postgres restart simulation unchanged.
5. Fork 3C-1/3D-1 is resolved (by the user) before `action-engine`
   (TDD 3D) implementation begins, since `action-engine`'s own adapter
   design depends on the answer.

---

## 14. Non-goals / explicitly deferred

- Any third-party/marketplace capability discovery or installation
  (Bible's own "MARKETPLACE READY" section, `:557-575` — deferred by
  analogy to doc 12 §15's Agent-Registry marketplace timeline, Phase 8+).
- `reasoning-engine`'s `ReasoningTrace.selected_capabilities` being
  wired to a real `CapabilityPort` — not named as a Phase 3 roadmap
  deliverable; left as the honest placeholder it already is.
- `confidence`/`performance_metrics`/`documentation`/`example_workflows`
  fields on the `Capability` model (§2.1).
- Any execution backend beyond direct in-process adapter invocation —
  no `container`/`subprocess`-isolated capability execution (Fork E3;
  Phase 7+ for `container`-grade isolation per doc 12 §8).
